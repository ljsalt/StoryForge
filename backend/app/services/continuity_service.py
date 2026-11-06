"""章节连续性检查服务（P4.1.3）。

设计要点：
1. 每次检查生成一条独立记录，历史检查永不覆盖，可追溯。
2. 上下文通过 context_builder 组装：当前章节正文以高优先级必需分区注入，
   保证正文优先于非必要历史信息保留；裁剪情况记入 context_meta，
   避免把模型没看到的信息误判为不存在。
3. 报告 JSON 必须通过本地校验；校验失败仅修复一次，仍失败则检查记为 failed，
   不允许把半个解析结果当成正式检查结论。
4. AI 只输出检查报告，不得修改章节正文或任何正式记忆数据。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import get_connection
from . import ai_generation_service, ai_task_service, context_builder
from .continuity_report_schema import ReportValidationError, parse_report
from .errors import ServiceError

_CHECK_CALL_TIMEOUT = 240.0

_CHECK_SYSTEM = (
    "你是一部长篇小说的连续性审校编辑。你的职责是核对指定章节与既有设定、"
    "人物状态、人物关系、时间线、剧情历史与世界观之间是否一致。"
    "你必须基于上下文提供的材料进行判断：不允许仅凭主观感觉认定冲突；"
    "必须区分真正的矛盾、可能的矛盾和合理的新剧情发展；"
    "没有发现问题时也必须返回明确的通过结论。你不得修改或重写章节正文。"
)

_CHECK_JSON_INSTRUCTION = """
你必须只输出一个 JSON 对象，不允许输出解释文字、Markdown 代码块或任何额外内容。
JSON 结构必须严格如下：
{
  "overall": "pass | warning | conflict",
  "issues": [
    {
      "severity": "info | warning | conflict",
      "category": "人物状态 | 人物关系 | 时间线 | 剧情与伏笔 | 世界观 | 其他",
      "description": "问题描述",
      "evidence": "当前章节正文中的原文证据（原文引用）",
      "reference": "冲突的历史设定或历史章节依据",
      "suggestion": "建议处理方式"
    }
  ]
}
规则：
1. 没有发现问题时 overall 必须为 "pass"，issues 为空数组 []；
2. 仅提示性观察用 info，可能矛盾用 warning，确定矛盾用 conflict；
3. 每条问题必须给出章节原文证据 evidence；引用历史依据时说明它来自上下文中的哪条设定；
4. 如果上下文中缺少判断所需的资料，在 suggestion 中说明"上下文未提供相关依据"，
   不得把没看到的内容当作不存在的事实来报冲突；
5. 至少检查：人物状态（地点/身体状态/受伤死亡/能力物品知识）、人物关系、
   时间线、剧情与伏笔（已发生事件是否被遗忘、已揭露秘密是否又被当作未知）、世界观一致性。
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_novel(conn, novel_id: str) -> None:
    row = conn.execute("SELECT id FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")


def _chapter_row(conn, novel_id: str, chapter_id: str):
    row = conn.execute(
        "SELECT * FROM chapters WHERE id = ? AND novel_id = ?",
        (chapter_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "章节不存在")
    return row


def _detect_character_ids(conn, novel_id: str, content: str) -> tuple[list[str], list[str]]:
    """按姓名/别名在正文中出现自动检测关联人物，返回 (id 列表, 姓名列表)。"""
    rows = conn.execute(
        "SELECT id, name, aliases FROM characters WHERE novel_id = ?"
        " ORDER BY sort_order ASC, created_at ASC",
        (novel_id,),
    ).fetchall()
    ids: list[str] = []
    names: list[str] = []
    for row in rows:
        candidates = [row["name"]]
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except (ValueError, TypeError):
            aliases = []
        if isinstance(aliases, list):
            candidates.extend(str(item) for item in aliases)
        if any(candidate and candidate in content for candidate in candidates):
            ids.append(row["id"])
            names.append(row["name"])
    return ids, names


def _load_json(raw: str | None) -> object:
    try:
        return json.loads(raw or "{}")
    except (ValueError, TypeError):
        return {}


def _to_check_out(row) -> dict:
    return {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "chapter_id": row["chapter_id"],
        "status": row["status"],
        "overall_result": row["overall_result"],
        "report": _load_json(row["report_json"]),
        "context_meta": _load_json(row["context_meta"]),
        "model_id": row["model_id"],
        "task_id": row["task_id"],
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }


def _check_row(conn, novel_id: str, check_id: str):
    row = conn.execute(
        "SELECT * FROM continuity_checks WHERE id = ? AND novel_id = ?",
        (check_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "连续性检查记录不存在")
    return row


def _fail_check(novel_id: str, check_id: str, code: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE continuity_checks
               SET status = 'failed', error_code = ?, error_message = ?, completed_at = ?
             WHERE id = ? AND novel_id = ?
            """,
            (code, message, _now(), check_id, novel_id),
        )


def get_check(novel_id: str, check_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _check_row(conn, novel_id, check_id)
    return _to_check_out(row)


def list_checks(novel_id: str, chapter_id: str) -> list[dict]:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        _chapter_row(conn, novel_id, chapter_id)
        rows = conn.execute(
            """
            SELECT * FROM continuity_checks
             WHERE novel_id = ? AND chapter_id = ?
             ORDER BY created_at DESC, id DESC
            """,
            (novel_id, chapter_id),
        ).fetchall()
    return [_to_check_out(row) for row in rows]


async def create_check(novel_id: str, chapter_id: str, payload: dict) -> dict:
    """创建并执行一次连续性检查（同步等待 AI 结果）。"""
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        chapter = _chapter_row(conn, novel_id, chapter_id)
    content = (chapter["content"] or "").strip()
    if not content:
        raise ServiceError(400, "章节正文为空，无法进行连续性检查")

    model_id = str(payload.get("model_id") or "").strip() or None
    token_budget = payload.get("token_budget")
    explicit_ids = payload.get("character_ids")

    now = _now()
    check_id = uuid4().hex
    with get_connection() as conn:
        if explicit_ids is not None:
            char_ids = [str(item) for item in explicit_ids if str(item).strip()]
            detected_names: list[str] = []
        else:
            char_ids, detected_names = _detect_character_ids(conn, novel_id, content)
        conn.execute(
            """
            INSERT INTO continuity_checks
                (id, novel_id, chapter_id, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (check_id, novel_id, chapter_id, now),
        )
        conn.execute(
            "UPDATE continuity_checks SET status = 'running' WHERE id = ?",
            (check_id,),
        )

    context = context_builder.build_context(
        novel_id,
        task_type="assistant",
        chapter_id=chapter_id,
        character_ids=char_ids or None,
        token_budget=token_budget,
        pov="author",
        user_requirement="对指定章节进行剧情连续性检查",
        extra_sections=[
            {
                "key": "chapter_content",
                "title": f"待检查章节正文（第{chapter['chapter_number']}章 {chapter['title']}）",
                "content": content,
                "priority": 98,
                "required": True,
            }
        ],
    )
    context_meta = {
        "estimated_tokens": context["estimated_tokens"],
        "token_budget": context["token_budget"],
        "omitted_sections": context["omitted_sections"],
        "warnings": context["warnings"],
        "character_ids": char_ids,
        "auto_detected_characters": detected_names,
        "explicit_character_ids": explicit_ids is not None,
    }

    system = f"{_CHECK_SYSTEM}\n{_CHECK_JSON_INSTRUCTION}"
    user = (
        "以下是与本章节相关的小说上下文，其中包含待检查章节正文：\n"
        f"{context['context_text']}\n\n"
        "请对待检查章节进行连续性检查，只输出符合要求的 JSON 报告。"
    )

    result = await ai_generation_service.generate(
        {
            "novel_id": novel_id,
            "task_type": "assistant",
            "system_prompt": system,
            "user_prompt": user,
            "temperature": float(payload.get("temperature", 0.3)),
            "max_tokens": int(payload.get("max_tokens") or 4096),
            "timeout": _CHECK_CALL_TIMEOUT,
            "model_id": model_id,
            "include_reasoning": False,
        }
    )
    if not result["success"]:
        message = result.get("error_message") or result.get("error_code") or "AI 调用失败"
        _fail_check(novel_id, check_id, result.get("error_code") or "ai_error", message)
        raise ServiceError(502, f"连续性检查调用失败：{message}")
    if result.get("truncated"):
        _fail_check(novel_id, check_id, "truncated", "检查报告输出被截断，请增大 max_tokens 后重试")
        raise ServiceError(502, "检查报告输出被截断，请增大 max_tokens 后重试")

    task_id = result.get("task_id")
    ai_task_service.touch_task(task_id or "")

    try:
        report = parse_report(result["content"])
    except ReportValidationError as first_error:
        report = await _repair_report(
            novel_id, check_id, system, user, result["content"], first_error, payload,
        )

    finished = _now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE continuity_checks
               SET status = 'completed', overall_result = ?, report_json = ?,
                   context_meta = ?, model_id = ?, task_id = ?,
                   error_code = NULL, error_message = NULL, completed_at = ?
             WHERE id = ? AND novel_id = ?
            """,
            (
                report["overall"],
                json.dumps(report, ensure_ascii=False),
                json.dumps(context_meta, ensure_ascii=False),
                result.get("model") or model_id or "",
                task_id,
                finished,
                check_id,
                novel_id,
            ),
        )
    return get_check(novel_id, check_id)


async def _repair_report(
    novel_id: str,
    check_id: str,
    system: str,
    user: str,
    raw_content: str,
    error: ReportValidationError,
    payload: dict,
) -> dict:
    """报告 JSON 校验失败后的有限修复：只请求一次，仍失败则检查记为 failed。"""
    feedback = "\n".join(f"- {item}" for item in error.errors[:20])
    repair_user = (
        f"{user}\n\n你上一次的输出不是合法的检查报告，问题如下：\n{feedback}\n\n"
        f"上一次输出片段（仅供修正参考）：\n{raw_content[:2000]}\n\n"
        "请只输出修正后的完整 JSON 对象。"
    )
    repair = await ai_generation_service.generate(
        {
            "novel_id": novel_id,
            "task_type": "assistant",
            "system_prompt": system,
            "user_prompt": repair_user,
            "temperature": 0.2,
            "max_tokens": int(payload.get("max_tokens") or 4096),
            "timeout": _CHECK_CALL_TIMEOUT,
        }
    )
    if not repair["success"] or repair.get("truncated"):
        _fail_check(
            novel_id, check_id, "invalid_report_json",
            "检查报告 JSON 校验失败，且修复请求未能得到合法结构",
        )
        raise ServiceError(502, "检查报告格式不合法，自动修复一次后仍未通过校验，请重新检查")
    ai_task_service.touch_task(repair.get("task_id") or "")
    try:
        return parse_report(repair["content"])
    except ReportValidationError as exc:
        _fail_check(
            novel_id, check_id, "invalid_report_json",
            "检查报告 JSON 校验失败：" + "；".join(exc.errors[:5]),
        )
        raise ServiceError(
            502,
            "检查报告格式不合法：" + "；".join(exc.errors[:5]) + "。请重新检查后重试",
        ) from exc
