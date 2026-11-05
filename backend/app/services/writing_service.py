"""单章节创作工作流服务（P4.1.2）。

流程：创建会话 → 剧情导演生成结构化计划 → 用户处理重大决定并确认计划
→ 正文作者分段写作 → 草稿编辑 → 用户确认写入正式章节。

边界：
1. 只有用户显式调用确认接口后，草稿才会写入 chapters 表；
2. AI 不直接修改人物档案、人物关系、世界观与剧情事件；
3. 所有读写都以 novel_id 校验归属，跨小说访问一律 404；
4. 必需重大决定未解决时禁止进入正文写作；
5. 截断（finish_reason=length）的段落不视为完成段落，也不拼进草稿。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import (
    WRITING_SESSION_STATUSES,
    WRITING_SESSION_TERMINAL_STATUSES,
    get_connection,
)
from . import (
    ai_generation_service,
    ai_task_service,
    context_builder,
    prompt_template_service,
)
from .chapter_service import count_words
from .errors import ServiceError
from .writing_plan_schema import (
    PlanValidationError,
    extract_json_object,
    validate_plan,
)

# 段落生成中状态的保护期：超过该时长视为异常遗留，可被新的生成请求接管
_SEGMENT_GENERATING_GUARD_SECONDS = 300

_ACTIVE_STATUSES = ("planning", "failed", "awaiting_plan_approval")

_DEFAULT_PLANNER_SYSTEM = (
    "你是一部长篇小说的剧情导演。你的职责是基于既有设定与剧情历史，"
    "提出合理、连贯、有张力的章节剧情计划。不得违背已确定的世界观、"
    "人物设定与已发生的故事事实。"
)
_DEFAULT_WRITER_SYSTEM = (
    "你是一部长篇小说的正文作者。你的文字风格稳定，严格遵循给定的世界观、"
    "人物设定与剧情走向。你只能使用上下文中提供的信息，"
    "不得编造与设定冲突的情节，不得让人物知道他们在故事中不可能知道的秘密。"
)

_PLAN_JSON_INSTRUCTION = """
你必须只输出一个 JSON 对象，不允许输出解释文字、Markdown 代码块或任何额外内容。
JSON 结构必须严格如下（字段不可缺失，数组不可为 null）：
{
  "chapter_goal": "本章目标",
  "opening": "开场",
  "scenes": [
    {
      "name": "场景名称",
      "location": "地点",
      "characters": ["出场人物"],
      "purpose": "场景目的",
      "actions": "主要行动",
      "conflict": "冲突",
      "result": "场景结果",
      "transition": "与下一场景的衔接"
    }
  ],
  "character_actions": ["人物行动"],
  "conflicts": ["冲突"],
  "plot_events": [{"title": "事件标题", "description": "事件描述"}],
  "foreshadowing": ["伏笔"],
  "ending": "章节结尾",
  "estimated_word_count": 3000,
  "major_decisions": [
    {
      "decision_id": "d1",
      "title": "决定标题",
      "description": "决定描述",
      "context": "背景",
      "options": ["选项A", "选项B"],
      "recommended_option": "选项A",
      "consequences": "后果",
      "is_required": true
    }
  ]
}
规则：
1. 至少包含 2 个场景，场景按叙事顺序排列；
2. major_decisions 只收录会改变长期剧情的重大决定（例如杀死重要人物、
   是否加入势力、是否暴露身份或秘密、是否决裂、不可逆的重大选择）。
   普通场景行动不要放进 major_decisions；
3. 若本次章节没有重大决定，major_decisions 必须为空数组 []；
4. is_required=true 表示开始写作前必须由用户确认。
"""

_WRITER_CONSTRAINT = """
你只输出小说正文本身，不要输出任何解释、标题、JSON 或自我评价。
不要用思维链替代正文。不要重复已经写过的内容，也不要提前写后续场景。
"""

_SEGMENT_WORDS = 700


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _age_seconds(value: str | None) -> float:
    if not value:
        return 1e9
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return 1e9
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - stamp).total_seconds()


def _ensure_novel(conn, novel_id: str) -> None:
    row = conn.execute("SELECT id FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")


def _session_row(conn, novel_id: str, session_id: str):
    row = conn.execute(
        "SELECT * FROM writing_sessions WHERE id = ? AND novel_id = ?",
        (session_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "创作会话不存在")
    return row


def _to_session(row) -> dict:
    return {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "chapter_id": row["chapter_id"],
        "title": row["title"],
        "status": row["status"],
        "task_type": row["task_type"],
        "user_instruction": row["user_instruction"],
        "pov_character_id": row["pov_character_id"],
        "target_word_count": row["target_word_count"],
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
    }


def _decision_to_out(row) -> dict:
    return {
        "id": row["id"],
        "plan_id": row["plan_id"],
        "decision_key": row["decision_key"],
        "title": row["title"],
        "description": row["description"],
        "context": row["context"],
        "options": json.loads(row["options"] or "[]"),
        "recommended_option": row["recommended_option"],
        "consequences": row["consequences"],
        "is_required": bool(row["is_required"]),
        "selected_option": row["selected_option"],
        "custom_answer": row["custom_answer"],
        "resolved": row["resolved_at"] is not None,
        "resolved_at": row["resolved_at"],
        "sort_order": row["sort_order"],
    }


def _plan_to_out(row) -> dict:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "novel_id": row["novel_id"],
        "version": row["version"],
        "is_current": bool(row["is_current"]),
        "chapter_goal": row["chapter_goal"],
        "opening": row["opening"],
        "scenes": json.loads(row["scenes"] or "[]"),
        "character_actions": json.loads(row["character_actions"] or "[]"),
        "conflicts": json.loads(row["conflicts"] or "[]"),
        "plot_events": json.loads(row["plot_events"] or "[]"),
        "foreshadowing": json.loads(row["foreshadowing"] or "[]"),
        "ending": row["ending"],
        "estimated_word_count": row["estimated_word_count"],
        "major_decisions": json.loads(row["major_decisions"] or "[]"),
        "source_model": row["source_model"],
        "source_task_id": row["source_task_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _segment_to_out(row) -> dict:
    return {
        "id": row["id"],
        "draft_id": row["draft_id"],
        "scene_index": row["scene_index"],
        "sequence": row["sequence"],
        "content": row["content"],
        "status": row["status"],
        "word_count": row["word_count"],
        "attempt": row["attempt"],
        "truncated": bool(row["truncated"]),
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _draft_row(conn, novel_id: str, session_id: str):
    row = conn.execute(
        "SELECT * FROM writing_drafts WHERE session_id = ? AND novel_id = ?",
        (session_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "创作会话还没有草稿")
    return row


def _draft_payload(conn, draft_row, session_row) -> dict:
    segments = conn.execute(
        "SELECT * FROM writing_draft_segments WHERE draft_id = ? ORDER BY sequence ASC",
        (draft_row["id"],),
    ).fetchall()
    completed = sum(1 for s in segments if s["status"] == "completed")
    return {
        "id": draft_row["id"],
        "novel_id": draft_row["novel_id"],
        "session_id": draft_row["session_id"],
        "plan_id": draft_row["plan_id"],
        "chapter_id": draft_row["chapter_id"],
        "title": draft_row["title"],
        "content": draft_row["content"],
        "word_count": draft_row["word_count"],
        "status": draft_row["status"],
        "edited": bool(draft_row["edited"]),
        "created_at": draft_row["created_at"],
        "updated_at": draft_row["updated_at"],
        "confirmed_at": draft_row["confirmed_at"],
        "segments": [_segment_to_out(s) for s in segments],
        "progress": {
            "completed_segments": completed,
            "total_segments": len(segments),
            "word_count": draft_row["word_count"],
            "target_word_count": session_row["target_word_count"],
        },
    }


def _current_plan_row(conn, session_id: str):
    return conn.execute(
        "SELECT * FROM writing_plans WHERE session_id = ? AND is_current = 1"
        " ORDER BY version DESC LIMIT 1",
        (session_id,),
    ).fetchone()


def _require_status(row, allowed: tuple[str, ...], message: str) -> None:
    if row["status"] not in allowed:
        raise ServiceError(409, message)


def _touch_session(conn, session_id: str, now: str) -> None:
    conn.execute(
        "UPDATE writing_sessions SET updated_at = ? WHERE id = ?", (now, session_id)
    )


# ----------------------------- 创作会话 -----------------------------

def create_session(novel_id: str, payload: dict) -> dict:
    title = str(payload.get("title") or "").strip()
    user_instruction = str(payload.get("user_instruction") or "").strip()
    chapter_id = (payload.get("chapter_id") or "").strip() or None
    pov_character_id = (payload.get("pov_character_id") or "").strip() or None
    target_word_count = int(payload.get("target_word_count") or 3000)
    if not 500 <= target_word_count <= 10000:
        raise ServiceError(400, "目标字数必须在 500 到 10000 之间")

    now = _now()
    session_id = uuid4().hex
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        if chapter_id:
            chapter = conn.execute(
                "SELECT * FROM chapters WHERE id = ? AND novel_id = ?",
                (chapter_id, novel_id),
            ).fetchone()
            if chapter is None:
                raise ServiceError(404, "章节不存在")
            title = title or chapter["title"]
        if pov_character_id:
            pov = conn.execute(
                "SELECT id FROM characters WHERE id = ? AND novel_id = ?",
                (pov_character_id, novel_id),
            ).fetchone()
            if pov is None:
                raise ServiceError(404, "视角人物不存在")
        if not title:
            row = conn.execute(
                "SELECT COALESCE(MAX(chapter_number), 0) + 1 AS n"
                "  FROM chapters WHERE novel_id = ?",
                (novel_id,),
            ).fetchone()
            title = f"第 {int(row['n'])} 章"
        conn.execute(
            """
            INSERT INTO writing_sessions
                (id, novel_id, chapter_id, title, status, task_type,
                 user_instruction, pov_character_id, target_word_count,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, 'planning', 'writer', ?, ?, ?, ?, ?)
            """,
            (
                session_id, novel_id, chapter_id, title, user_instruction,
                pov_character_id, target_word_count, now, now,
            ),
        )
    return get_session(novel_id, session_id)


def list_sessions(novel_id: str, *, status: str | None = None) -> list[dict]:
    if status and status.strip() and status.strip() not in WRITING_SESSION_STATUSES:
        raise ServiceError(400, "不支持的创作会话状态")
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        sql = "SELECT * FROM writing_sessions WHERE novel_id = ?"
        params: list[object] = [novel_id]
        if status and status.strip():
            sql += " AND status = ?"
            params.append(status.strip())
        sql += " ORDER BY updated_at DESC, created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            item = _to_session(row)
            plan = _current_plan_row(conn, row["id"])
            item["plan_version"] = plan["version"] if plan else None
            draft = conn.execute(
                "SELECT status, word_count FROM writing_drafts WHERE session_id = ?",
                (row["id"],),
            ).fetchone()
            item["draft_status"] = draft["status"] if draft else None
            item["draft_word_count"] = draft["word_count"] if draft else 0
            result.append(item)
    return result


def get_session(novel_id: str, session_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        data = _to_session(row)
        plan = _current_plan_row(conn, session_id)
        if plan:
            data["plan"] = _plan_to_out(plan)
            decisions = conn.execute(
                "SELECT * FROM writing_decisions WHERE plan_id = ?"
                " ORDER BY sort_order ASC, created_at ASC",
                (plan["id"],),
            ).fetchall()
            data["decisions"] = [_decision_to_out(d) for d in decisions]
        else:
            data["plan"] = None
            data["decisions"] = []
        draft = conn.execute(
            "SELECT * FROM writing_drafts WHERE session_id = ?", (session_id,)
        ).fetchone()
        data["draft"] = _draft_payload(conn, draft, row) if draft else None
    return data


def update_session(novel_id: str, session_id: str, fields: dict) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        if row["status"] in WRITING_SESSION_TERMINAL_STATUSES:
            raise ServiceError(409, "已结束的创作会话不能再修改")
        updates: dict[str, object] = {}
        if fields.get("title") is not None:
            title = str(fields["title"]).strip()
            if not title:
                raise ServiceError(400, "会话标题不能为空")
            updates["title"] = title
        if fields.get("user_instruction") is not None:
            updates["user_instruction"] = str(fields["user_instruction"])
        if fields.get("pov_character_id") is not None:
            pov_id = str(fields["pov_character_id"]).strip() or None
            if pov_id:
                pov = conn.execute(
                    "SELECT id FROM characters WHERE id = ? AND novel_id = ?",
                    (pov_id, novel_id),
                ).fetchone()
                if pov is None:
                    raise ServiceError(404, "视角人物不存在")
            updates["pov_character_id"] = pov_id
        if fields.get("target_word_count") is not None:
            target = int(fields["target_word_count"])
            if not 500 <= target <= 10000:
                raise ServiceError(400, "目标字数必须在 500 到 10000 之间")
            updates["target_word_count"] = target
        if not updates:
            return get_session(novel_id, session_id)
        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE writing_sessions SET {assignments} WHERE id = ?",
            list(updates.values()) + [session_id],
        )
    return get_session(novel_id, session_id)


def delete_session(novel_id: str, session_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        _session_row(conn, novel_id, session_id)
        # 计划、决定、草稿、段落通过外键级联清理
        conn.execute(
            "DELETE FROM writing_sessions WHERE id = ? AND novel_id = ?",
            (session_id, novel_id),
        )
    return {"deleted": True}


def pause_session(novel_id: str, session_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        _require_status(row, ("writing",), "只有写作中的会话可以暂停")
        now = _now()
        conn.execute(
            "UPDATE writing_sessions SET status = 'paused_for_user', updated_at = ?"
            " WHERE id = ?",
            (now, session_id),
        )
    return get_session(novel_id, session_id)


def resume_session(novel_id: str, session_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        _require_status(row, ("paused_for_user",), "只有已暂停的会话可以继续")
        now = _now()
        conn.execute(
            "UPDATE writing_sessions SET status = 'writing', error_code = NULL,"
            " error_message = NULL, updated_at = ? WHERE id = ?",
            (now, session_id),
        )
    return get_session(novel_id, session_id)


def cancel_session(novel_id: str, session_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        if row["status"] in WRITING_SESSION_TERMINAL_STATUSES:
            raise ServiceError(409, "该创作会话已结束")
        now = _now()
        conn.execute(
            "UPDATE writing_sessions SET status = 'cancelled', completed_at = ?,"
            " updated_at = ? WHERE id = ?",
            (now, now, session_id),
        )
        # 取消时把生成中的段落标记失败，避免留下永久 generating 状态
        conn.execute(
            "UPDATE writing_draft_segments SET status = 'failed',"
            " error_code = 'cancelled', error_message = '用户取消了创作会话', updated_at = ?"
            " WHERE draft_id IN (SELECT id FROM writing_drafts WHERE session_id = ?)"
            "   AND status = 'generating'",
            (now, session_id),
        )
    return get_session(novel_id, session_id)


# ----------------------------- 剧情计划 -----------------------------

def _template_prompts(task_type: str, variables: dict[str, str], fallback_system: str,
                      fallback_user: str) -> tuple[str, str, str | None, int | None]:
    template = prompt_template_service.get_active_for_task(task_type)
    if template:
        try:
            system = prompt_template_service.render_text(template["system_prompt"], variables)
            user = prompt_template_service.render_text(
                template["user_prompt_template"], variables
            )
            return system, user, template["id"], template["version"]
        except ServiceError:
            # 模板变量与服务当前提供的变量不匹配时回退到内置模板，
            # 不阻塞整个创作流程
            pass
    return fallback_system, fallback_user, None, None


def _plan_requirement(session_row, extra: str) -> str:
    parts = []
    if session_row["chapter_id"]:
        parts.append("本次需要为已有章节续写/重写正文。")
    else:
        parts.append("本次需要规划一个新章节。")
    if session_row["user_instruction"]:
        parts.append(f"作者要求：{session_row['user_instruction']}")
    parts.append(f"目标章节字数约 {session_row['target_word_count']} 个非空白字符。")
    if extra:
        parts.append(f"补充要求：{extra}")
    return "\n".join(parts)


def _build_context(session_row, *, task_type: str, extra_requirement: str) -> dict:
    pov = "author"
    character_ids: list[str] | None = None
    if session_row["pov_character_id"]:
        pov = "character"
        character_ids = [session_row["pov_character_id"]]
    return context_builder.build_context(
        session_row["novel_id"],
        task_type=task_type,
        chapter_id=session_row["chapter_id"],
        character_ids=character_ids,
        pov=pov,
        user_requirement=_plan_requirement(session_row, extra_requirement),
    )


async def generate_plan(novel_id: str, session_id: str, payload: dict) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        session_row = _session_row(conn, novel_id, session_id)
        if session_row["status"] not in _ACTIVE_STATUSES:
            raise ServiceError(409, "当前会话阶段不能生成剧情计划")
        draft_exists = conn.execute(
            "SELECT id FROM writing_drafts WHERE session_id = ?", (session_id,)
        ).fetchone()
        if draft_exists:
            raise ServiceError(409, "该会话已经进入写作阶段，不能重新生成计划")
    extra = str(payload.get("extra_instruction") or "").strip()
    context = _build_context(session_row, task_type="planner", extra_requirement=extra)
    variables = {"context": context["context_text"], "task": _plan_requirement(session_row, extra)}
    system, user, template_id, template_version = _template_prompts(
        "planner",
        variables,
        _DEFAULT_PLANNER_SYSTEM,
        "以下是小说上下文：\n{context}\n\n请生成章节剧情计划。\n{task}",
    )
    system = f"{system}\n{_PLAN_JSON_INSTRUCTION}"
    if template_id is None:
        # 内置模板同样需要变量替换
        user = f"以下是小说上下文：\n{context['context_text']}\n\n请生成章节剧情计划。\n{variables['task']}"

    result = await ai_generation_service.generate(
        {
            "novel_id": novel_id,
            "task_type": "planner",
            "system_prompt": system,
            "user_prompt": user,
            "prompt_template_id": template_id,
            "template_version": template_version,
            "temperature": float(payload.get("temperature", 0.6)),
            "max_tokens": int(payload.get("max_tokens") or 4096),
            "include_reasoning": False,
        }
    )
    if not result["success"]:
        _mark_session_failed(
            novel_id, session_id, result.get("error_code") or "ai_error",
            result.get("error_message") or "剧情导演调用失败",
        )
        raise ServiceError(
            502,
            f"剧情导演调用失败：{result.get('error_message') or result.get('error_code')}",
        )
    if result.get("truncated"):
        _mark_session_failed(
            novel_id, session_id, "truncated", "剧情计划输出被截断，请增大 max_tokens 后重试"
        )
        raise ServiceError(502, "剧情计划输出被截断，请增大 max_tokens 后重试")

    task_id = result.get("task_id")
    ai_task_service.touch_task(task_id or "")

    try:
        plan_data = _parse_plan(result["content"])
    except PlanValidationError as first_error:
        # 有限次修复：只请求一次，仍失败则明确报错，不做无限重试
        plan_data = await _repair_plan(
            novel_id, session_id, system, user, template_id, template_version,
            result["content"], first_error, payload,
        )

    plan_payload = _save_plan(
        novel_id, session_id, plan_data,
        source_model=result.get("model") or "",
        source_task_id=task_id,
    )
    decisions = plan_payload.pop("decisions")
    return {
        "plan": plan_payload,
        "decisions": decisions,
        "warnings": context["warnings"],
        "context_estimated_tokens": context["estimated_tokens"],
        "context_omitted_sections": context["omitted_sections"],
        "usage": result.get("usage") or {},
        "latency_ms": result.get("latency_ms"),
        "task_id": task_id,
    }


def _parse_plan(content: str) -> dict:
    return validate_plan(extract_json_object(content))


async def _repair_plan(novel_id, session_id, system, user, template_id,
                       template_version, raw_content, error, payload) -> dict:
    feedback = "\n".join(f"- {item}" for item in error.errors[:20])
    repair_user = (
        f"{user}\n\n你上一次的输出不是合法计划，问题如下：\n{feedback}\n\n"
        f"上一次输出片段（仅供修正参考）：\n{raw_content[:2000]}\n\n"
        "请只输出修正后的完整 JSON 对象。"
    )
    repair = await ai_generation_service.generate(
        {
            "novel_id": novel_id,
            "task_type": "planner",
            "system_prompt": system,
            "user_prompt": repair_user,
            "prompt_template_id": template_id,
            "template_version": template_version,
            "temperature": 0.3,
            "max_tokens": int(payload.get("max_tokens") or 4096),
        }
    )
    if not repair["success"] or repair.get("truncated"):
        _mark_session_failed(
            novel_id, session_id, "invalid_plan_json",
            "剧情计划 JSON 校验失败，且修复请求未能得到合法结构",
        )
        raise ServiceError(
            502, "剧情计划格式不合法，自动修复一次后仍未通过校验，请重新生成或修改模型"
        )
    try:
        return _parse_plan(repair["content"])
    except PlanValidationError as exc:
        _mark_session_failed(
            novel_id, session_id, "invalid_plan_json",
            "剧情计划 JSON 校验失败：" + "；".join(exc.errors[:5]),
        )
        raise ServiceError(
            502,
            "剧情计划格式不合法："
            + "；".join(exc.errors[:5])
            + "。请重新生成或修改模型后重试",
        ) from exc


def _save_plan(novel_id, session_id, plan_data, *, source_model, source_task_id) -> dict:
    now = _now()
    with get_connection() as conn:
        latest = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS v FROM writing_plans WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        version = int(latest["v"]) + 1
        conn.execute(
            "UPDATE writing_plans SET is_current = 0 WHERE session_id = ?",
            (session_id,),
        )
        plan_id = uuid4().hex
        conn.execute(
            """
            INSERT INTO writing_plans
                (id, novel_id, session_id, version, is_current, chapter_goal,
                 opening, scenes, character_actions, conflicts, plot_events,
                 foreshadowing, ending, estimated_word_count, major_decisions,
                 source_model, source_task_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id, novel_id, session_id, version,
                plan_data["chapter_goal"], plan_data["opening"],
                json.dumps(plan_data["scenes"], ensure_ascii=False),
                json.dumps(plan_data["character_actions"], ensure_ascii=False),
                json.dumps(plan_data["conflicts"], ensure_ascii=False),
                json.dumps(plan_data["plot_events"], ensure_ascii=False),
                json.dumps(plan_data["foreshadowing"], ensure_ascii=False),
                plan_data["ending"], plan_data["estimated_word_count"],
                json.dumps(plan_data["major_decisions"], ensure_ascii=False),
                source_model, source_task_id, now, now,
            ),
        )
        _sync_decisions(conn, novel_id, session_id, plan_id, plan_data["major_decisions"], now)
        conn.execute(
            "UPDATE writing_sessions SET status = 'awaiting_plan_approval',"
            " error_code = NULL, error_message = NULL, updated_at = ? WHERE id = ?",
            (now, session_id),
        )
    return get_current_plan(novel_id, session_id)


def _sync_decisions(conn, novel_id, session_id, plan_id, decisions, now) -> None:
    """写入/更新决定；按 decision_key 保留用户已做出的选择。"""
    existing = {
        row["decision_key"]: row
        for row in conn.execute(
            "SELECT * FROM writing_decisions WHERE plan_id = ?", (plan_id,)
        ).fetchall()
    }
    new_keys = {d["decision_id"] for d in decisions}
    for key, row in existing.items():
        if key not in new_keys:
            conn.execute("DELETE FROM writing_decisions WHERE id = ?", (row["id"],))
    for index, item in enumerate(decisions):
        row = existing.get(item["decision_id"])
        if row is None:
            conn.execute(
                """
                INSERT INTO writing_decisions
                    (id, novel_id, session_id, plan_id, decision_key, title,
                     description, context, options, recommended_option,
                     consequences, is_required, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex, novel_id, session_id, plan_id, item["decision_id"],
                    item["title"], item["description"], item["context"],
                    json.dumps(item["options"], ensure_ascii=False),
                    item["recommended_option"], item["consequences"],
                    1 if item["is_required"] else 0, index, now, now,
                ),
            )
        else:
            # 选项变化后，原有选择若不再合法则视为未解决
            old_selected = row["selected_option"]
            still_valid = old_selected in item["options"] if old_selected else False
            conn.execute(
                """
                UPDATE writing_decisions
                   SET title = ?, description = ?, context = ?, options = ?,
                       recommended_option = ?, consequences = ?, is_required = ?,
                       sort_order = ?, updated_at = ?,
                       selected_option = ?, resolved_at = ?
                 WHERE id = ?
                """,
                (
                    item["title"], item["description"], item["context"],
                    json.dumps(item["options"], ensure_ascii=False),
                    item["recommended_option"], item["consequences"],
                    1 if item["is_required"] else 0, index, now,
                    old_selected if still_valid else None,
                    row["resolved_at"] if still_valid else None,
                    row["id"],
                ),
            )


def get_current_plan(novel_id: str, session_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        plan = _current_plan_row(conn, session_id)
        if plan is None:
            raise ServiceError(404, "该创作会话还没有剧情计划")
        decisions = conn.execute(
            "SELECT * FROM writing_decisions WHERE plan_id = ?"
            " ORDER BY sort_order ASC, created_at ASC",
            (plan["id"],),
        ).fetchall()
    data = _plan_to_out(plan)
    data["decisions"] = [_decision_to_out(d) for d in decisions]
    data["session_status"] = row["status"]
    return data


def list_plan_versions(novel_id: str, session_id: str) -> list[dict]:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        _session_row(conn, novel_id, session_id)
        rows = conn.execute(
            "SELECT * FROM writing_plans WHERE session_id = ? ORDER BY version DESC",
            (session_id,),
        ).fetchall()
    return [_plan_to_out(row) for row in rows]


def update_plan(novel_id: str, session_id: str, payload: dict) -> dict:
    """用户手工修改计划：在当前版本上更新，并同步决定项。"""
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        _require_status(row, ("awaiting_plan_approval", "planning"), "当前阶段不能修改计划")
        plan = _current_plan_row(conn, session_id)
        if plan is None:
            raise ServiceError(404, "该创作会话还没有剧情计划")
    try:
        plan_data = validate_plan(payload)
    except PlanValidationError as exc:
        raise ServiceError(400, "剧情计划不合法：" + "；".join(exc.errors[:10])) from exc
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE writing_plans
               SET chapter_goal = ?, opening = ?, scenes = ?, character_actions = ?,
                   conflicts = ?, plot_events = ?, foreshadowing = ?, ending = ?,
                   estimated_word_count = ?, major_decisions = ?, updated_at = ?
             WHERE id = ?
            """,
            (
                plan_data["chapter_goal"], plan_data["opening"],
                json.dumps(plan_data["scenes"], ensure_ascii=False),
                json.dumps(plan_data["character_actions"], ensure_ascii=False),
                json.dumps(plan_data["conflicts"], ensure_ascii=False),
                json.dumps(plan_data["plot_events"], ensure_ascii=False),
                json.dumps(plan_data["foreshadowing"], ensure_ascii=False),
                plan_data["ending"], plan_data["estimated_word_count"],
                json.dumps(plan_data["major_decisions"], ensure_ascii=False),
                now, plan["id"],
            ),
        )
        _sync_decisions(
            conn, novel_id, session_id, plan["id"], plan_data["major_decisions"], now
        )
        _touch_session(conn, session_id, now)
    return get_current_plan(novel_id, session_id)


def resolve_decision(novel_id: str, session_id: str, decision_key: str, payload: dict) -> dict:
    selected = str(payload.get("selected_option") or "").strip()
    custom = str(payload.get("custom_answer") or "").strip()
    if not selected and not custom:
        raise ServiceError(400, "请选择选项或填写自定义选择")
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        session_row = _session_row(conn, novel_id, session_id)
        _require_status(
            session_row, ("awaiting_plan_approval",), "只有等待计划确认阶段可以选择重大决定"
        )
        plan = _current_plan_row(conn, session_id)
        if plan is None:
            raise ServiceError(404, "该创作会话还没有剧情计划")
        row = conn.execute(
            "SELECT * FROM writing_decisions WHERE plan_id = ? AND decision_key = ?",
            (plan["id"], decision_key),
        ).fetchone()
        if row is None:
            raise ServiceError(404, "重大决定不存在")
        options = json.loads(row["options"] or "[]")
        if selected and selected not in options:
            raise ServiceError(400, "所选选项不在该决定的选项列表中")
        now = _now()
        conn.execute(
            "UPDATE writing_decisions SET selected_option = ?, custom_answer = ?,"
            " resolved_at = ?, updated_at = ? WHERE id = ?",
            (selected or None, custom, now, now, row["id"]),
        )
        _touch_session(conn, session_id, now)
    return get_current_plan(novel_id, session_id)


def _unresolved_required(conn, plan_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT title FROM writing_decisions WHERE plan_id = ?"
        " AND is_required = 1 AND resolved_at IS NULL ORDER BY sort_order",
        (plan_id,),
    ).fetchall()
    return [row["title"] for row in rows]


def approve_plan(novel_id: str, session_id: str, payload: dict) -> dict:
    now = _now()
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        _require_status(
            row, ("awaiting_plan_approval",), "只有等待计划确认的会话可以确认计划"
        )
        plan = _current_plan_row(conn, session_id)
        if plan is None:
            raise ServiceError(404, "该创作会话还没有剧情计划")
        pending = _unresolved_required(conn, plan["id"])
        if pending:
            raise ServiceError(
                400, "存在未解决的必需重大决定，不能开始写作：" + "、".join(pending)
            )
        if conn.execute(
            "SELECT id FROM writing_drafts WHERE session_id = ?", (session_id,)
        ).fetchone():
            raise ServiceError(409, "该会话已经进入写作阶段")

        plan_data = json.loads(plan["scenes"] or "[]")
        draft_id = uuid4().hex
        draft_title = str(payload.get("draft_title") or row["title"]).strip() or row["title"]
        conn.execute(
            """
            INSERT INTO writing_drafts
                (id, novel_id, session_id, plan_id, chapter_id, title, content,
                 word_count, status, edited, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, '', 0, 'drafting', 0, ?, ?)
            """,
            (
                draft_id, novel_id, session_id, plan["id"], row["chapter_id"],
                draft_title, now, now,
            ),
        )
        for index, _scene in enumerate(plan_data, start=1):
            conn.execute(
                """
                INSERT INTO writing_draft_segments
                    (id, novel_id, draft_id, scene_index, sequence, content,
                     status, word_count, attempt, truncated, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, '', 'pending', 0, 1, 0, ?, ?)
                """,
                (uuid4().hex, novel_id, draft_id, index, index, now, now),
            )
        conn.execute(
            "UPDATE writing_sessions SET status = 'writing', error_code = NULL,"
            " error_message = NULL, updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        draft_row = conn.execute(
            "SELECT * FROM writing_drafts WHERE id = ?", (draft_id,)
        ).fetchone()
        session_row = _session_row(conn, novel_id, session_id)
        draft = _draft_payload(conn, draft_row, session_row)
    return {"session": get_session(novel_id, session_id), "draft": draft}


# ----------------------------- 正文写作 -----------------------------

def get_draft(novel_id: str, session_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        session_row = _session_row(conn, novel_id, session_id)
        draft_row = _draft_row(conn, novel_id, session_id)
        return _draft_payload(conn, draft_row, session_row)


def update_draft(novel_id: str, session_id: str, fields: dict) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        session_row = _session_row(conn, novel_id, session_id)
        draft_row = _draft_row(conn, novel_id, session_id)
        if draft_row["status"] == "confirmed":
            raise ServiceError(409, "草稿已确认写入章节，不能再编辑")
        if session_row["status"] in ("cancelled", "failed", "completed"):
            raise ServiceError(409, "当前会话阶段不能编辑草稿")
        updates: dict[str, object] = {}
        if fields.get("title") is not None:
            title = str(fields["title"]).strip()
            if not title:
                raise ServiceError(400, "草稿标题不能为空")
            updates["title"] = title
        if fields.get("content") is not None:
            content = str(fields["content"])
            updates["content"] = content
            updates["word_count"] = count_words(content)
            updates["edited"] = 1
            updates["status"] = "ready" if content.strip() else "drafting"
        if not updates:
            return _draft_payload(conn, draft_row, session_row)
        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE writing_drafts SET {assignments} WHERE id = ?",
            list(updates.values()) + [draft_row["id"]],
        )
        # 手工编辑后会话进入 draft_ready，允许直接确认或继续生成
        if session_row["status"] == "writing" and str(updates.get("status")) == "ready":
            conn.execute(
                "UPDATE writing_sessions SET status = 'draft_ready', updated_at = ?"
                " WHERE id = ?",
                (_now(), session_id),
            )
        elif session_row["status"] == "draft_ready" and str(updates.get("status")) == "drafting":
            conn.execute(
                "UPDATE writing_sessions SET status = 'writing', updated_at = ?"
                " WHERE id = ?",
                (_now(), session_id),
            )
        updated = conn.execute(
            "SELECT * FROM writing_drafts WHERE id = ?", (draft_row["id"],)
        ).fetchone()
        session_now = _session_row(conn, novel_id, session_id)
        return _draft_payload(conn, updated, session_now)


def _segment_prompt(session_row, plan_row, segment_row, segments, extra_instruction) -> str:
    scenes = json.loads(plan_row["scenes"] or "[]")
    scene = scenes[segment_row["scene_index"] - 1] if segment_row["scene_index"] - 1 < len(scenes) else {}
    previous = [
        s for s in segments
        if s["status"] == "completed" and s["sequence"] < segment_row["sequence"] and s["content"].strip()
    ]
    tail = previous[-1]["content"].strip() if previous else ""
    tail = tail[-300:] if tail else ""
    lines = [
        f"本章目标：{plan_row['chapter_goal']}",
        f"开场：{plan_row['opening']}",
        f"结尾规划：{plan_row['ending']}",
        "",
        f"当前是第 {segment_row['sequence']} / {len(segments)} 段，对应场景：",
        f"场景名称：{scene.get('name', '')}",
        f"地点：{scene.get('location', '')}",
        f"出场人物：{'、'.join(scene.get('characters') or [])}",
        f"场景目的：{scene.get('purpose', '')}",
        f"主要行动：{scene.get('actions', '')}",
        f"冲突：{scene.get('conflict', '')}",
        f"场景结果：{scene.get('result', '')}",
        f"与下一场景的衔接：{scene.get('transition', '')}",
    ]
    if tail:
        lines += ["", f"已写内容的结尾（仅用于衔接，禁止重复）：\n{tail}"]
    if session_row["user_instruction"] or extra_instruction:
        lines += ["", f"作者要求：{session_row['user_instruction']} {extra_instruction}".strip()]
    lines += [
        "",
        f"只写本段内容，约 {_SEGMENT_WORDS} 个非空白字符；不要写到后续场景，"
        "不要重复已写内容，结尾自然衔接下一场景。",
    ]
    return "\n".join(lines)


async def _generate_one_segment(novel_id, session_row, draft_row, segment_row,
                                segments, payload) -> dict:
    plan_row = None
    with get_connection() as conn:
        if draft_row["plan_id"]:
            plan_row = conn.execute(
                "SELECT * FROM writing_plans WHERE id = ?", (draft_row["plan_id"],)
            ).fetchone()
    if plan_row is None:
        raise ServiceError(409, "草稿没有关联的剧情计划，无法生成正文")

    extra = str(payload.get("extra_instruction") or "").strip()
    context = _build_context(
        session_row, task_type="writer",
        extra_requirement=_segment_prompt(session_row, plan_row, segment_row, segments, extra),
    )
    task_text = _segment_prompt(session_row, plan_row, segment_row, segments, extra)
    variables = {"context": context["context_text"], "task": task_text}
    system, user, template_id, template_version = _template_prompts(
        "writer", variables, _DEFAULT_WRITER_SYSTEM,
        "以下是小说的上下文资料：\n{context}\n\n请创作本段正文。\n{task}",
    )
    system = f"{system}\n{_WRITER_CONSTRAINT}"
    if template_id is None:
        user = f"以下是小说的上下文资料：\n{context['context_text']}\n\n请创作本段正文。\n{task_text}"

    result = await ai_generation_service.generate(
        {
            "novel_id": novel_id,
            "task_type": "writer",
            "system_prompt": system,
            "user_prompt": user,
            "prompt_template_id": template_id,
            "template_version": template_version,
            "temperature": float(payload.get("temperature", 0.8)),
            "max_tokens": int(payload.get("max_tokens") or 4096),
            "include_reasoning": False,
        }
    )
    ai_task_service.touch_task(result.get("task_id") or "")
    return result, context


def _mark_segment_failed(conn, segment_id: str, code: str, message: str, now: str,
                         *, truncated: bool = False) -> None:
    conn.execute(
        """
        UPDATE writing_draft_segments
           SET status = 'failed', content = '', word_count = 0,
               error_code = ?, error_message = ?, truncated = ?, updated_at = ?
         WHERE id = ?
        """,
        (code, message[:300], 1 if truncated else 0, now, segment_id),
    )


def _recompute_draft(conn, draft_row, now: str) -> tuple[bool, bool]:
    """按已完成段落重建草稿正文；返回 (是否全部完成, 是否丢弃了手工编辑)。"""
    segments = conn.execute(
        "SELECT * FROM writing_draft_segments WHERE draft_id = ? ORDER BY sequence ASC",
        (draft_row["id"],),
    ).fetchall()
    completed = [s for s in segments if s["status"] == "completed" and s["content"].strip()]
    content = "\n\n".join(s["content"].strip() for s in completed)
    all_done = bool(segments) and all(s["status"] == "completed" for s in segments)
    discarded = bool(draft_row["edited"]) and bool(content)
    conn.execute(
        "UPDATE writing_drafts SET content = ?, word_count = ?, status = ?,"
        " edited = 0, updated_at = ? WHERE id = ?",
        (
            content, count_words(content),
            "ready" if all_done else "drafting", now, draft_row["id"],
        ),
    )
    return all_done, discarded


async def generate_segment(novel_id: str, session_id: str, payload: dict) -> dict:
    sequence = payload.get("sequence")
    now = _now()
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        session_row = _session_row(conn, novel_id, session_id)
        if session_row["status"] != "writing":
            raise ServiceError(409, "只有写作中的会话可以生成正文（已暂停请先继续）")
        draft_row = _draft_row(conn, novel_id, session_id)
        if draft_row["status"] == "confirmed":
            raise ServiceError(409, "草稿已确认写入章节")
        segments = conn.execute(
            "SELECT * FROM writing_draft_segments WHERE draft_id = ? ORDER BY sequence ASC",
            (draft_row["id"],),
        ).fetchall()
        if not segments:
            raise ServiceError(409, "草稿没有可生成的段落")
        # 防重复：只要有段落正在生成（且未超过保护期），拒绝新的生成请求，
        # 保证叙事按顺序推进，避免多个并发请求写乱顺序
        generating = [s for s in segments if s["status"] == "generating"]
        blocking = [
            s for s in generating
            if _age_seconds(s["updated_at"]) < _SEGMENT_GENERATING_GUARD_SECONDS
        ]
        if blocking:
            raise ServiceError(409, "已有段落正在生成中，请等待完成后再继续")
        for stale in generating:
            # 超时未完成视为异常遗留，允许新的请求接管
            conn.execute(
                "UPDATE writing_draft_segments SET status = 'failed',"
                " error_code = 'stale_generating',"
                " error_message = '段落生成超时未完成，已允许重新生成', updated_at = ?"
                " WHERE id = ?",
                (now, stale["id"]),
            )
        if generating:
            segments = conn.execute(
                "SELECT * FROM writing_draft_segments WHERE draft_id = ?"
                " ORDER BY sequence ASC",
                (draft_row["id"],),
            ).fetchall()
        target = None
        if sequence is not None:
            try:
                seq = int(sequence)
            except (TypeError, ValueError) as exc:
                raise ServiceError(400, "段落序号不合法") from exc
            target = next((s for s in segments if s["sequence"] == seq), None)
            if target is None:
                raise ServiceError(404, "段落不存在")
            if target["status"] == "completed":
                raise ServiceError(409, "该段落已完成，如需重写请使用重新生成接口")
        else:
            target = next(
                (s for s in segments if s["status"] in ("pending", "failed")), None
            )
            if target is None:
                raise ServiceError(409, "全部段落已完成，请编辑草稿或确认写入章节")
        # 标记为生成中，attempt 递增用于审计重复尝试
        conn.execute(
            "UPDATE writing_draft_segments SET status = 'generating', error_code = NULL,"
            " error_message = NULL, attempt = attempt + 1, updated_at = ? WHERE id = ?",
            (now, target["id"]),
        )
        target = conn.execute(
            "SELECT * FROM writing_draft_segments WHERE id = ?", (target["id"],)
        ).fetchone()
        session_row = _session_row(conn, novel_id, session_id)
        draft_row = _draft_row(conn, novel_id, session_id)
        segments = conn.execute(
            "SELECT * FROM writing_draft_segments WHERE draft_id = ? ORDER BY sequence ASC",
            (draft_row["id"],),
        ).fetchall()

    try:
        result, context = await _generate_one_segment(
            novel_id, session_row, draft_row, target, segments, payload
        )
    except Exception:
        with get_connection() as conn:
            _mark_segment_failed(conn, target["id"], "server_error", "生成过程出现异常", _now())
        raise

    if not result["success"]:
        with get_connection() as conn:
            _mark_segment_failed(
                conn, target["id"],
                result.get("error_code") or "ai_error",
                result.get("error_message") or "模型调用失败",
                _now(),
            )
        raise ServiceError(
            502, f"段落生成失败：{result.get('error_message') or result.get('error_code')}"
        )
    if result.get("truncated"):
        # 截断内容不得当作完整段落，也不拼进草稿
        with get_connection() as conn:
            _mark_segment_failed(
                conn, target["id"], "truncated",
                "输出达到 max_tokens 上限被截断，未保存该段；请增大 max_tokens 后重试",
                _now(), truncated=True,
            )
        raise ServiceError(502, "段落输出被截断，未保存，请增大 max_tokens 后重试")

    now = _now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE writing_draft_segments SET status = 'completed', content = ?,"
            " word_count = ?, truncated = 0, error_code = NULL, error_message = NULL,"
            " updated_at = ? WHERE id = ?",
            (result["content"], count_words(result["content"]), now, target["id"]),
        )
        session_row = _session_row(conn, novel_id, session_id)
        draft_row = _draft_row(conn, novel_id, session_id)
        all_done, discarded = _recompute_draft(conn, draft_row, now)
        conn.execute(
            "UPDATE writing_sessions SET status = ?, updated_at = ? WHERE id = ?",
            ("draft_ready" if all_done else "writing", now, session_id),
        )
        draft_row = _draft_row(conn, novel_id, session_id)
        session_row = _session_row(conn, novel_id, session_id)
        draft = _draft_payload(conn, draft_row, session_row)
        segment = conn.execute(
            "SELECT * FROM writing_draft_segments WHERE id = ?", (target["id"],)
        ).fetchone()
    return {
        "segment": _segment_to_out(segment),
        "draft": draft,
        "usage": result.get("usage") or {},
        "latency_ms": result.get("latency_ms"),
        "task_id": result.get("task_id"),
        "context_estimated_tokens": context["estimated_tokens"],
        "discarded_manual_edits": discarded,
    }


async def regenerate_segment(novel_id: str, session_id: str, sequence: int, payload: dict) -> dict:
    new_payload = dict(payload)
    new_payload["sequence"] = sequence
    return await generate_segment(novel_id, session_id, new_payload)


def confirm_draft(novel_id: str, session_id: str, payload: dict) -> dict:
    """用户确认后，事务内把草稿写入正式章节；默认不覆盖原章节。"""
    mode = str(payload.get("mode") or "").strip()
    if mode not in ("", "new_chapter", "replace_existing"):
        raise ServiceError(400, "不支持的写入模式")
    now = _now()
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        session_row = _session_row(conn, novel_id, session_id)
        if session_row["status"] in ("cancelled", "failed", "completed"):
            raise ServiceError(409, "当前会话阶段不能确认写入章节")
        draft_row = _draft_row(conn, novel_id, session_id)
        if draft_row["status"] == "confirmed":
            raise ServiceError(409, "草稿已经确认写入章节")
        rows = conn.execute(
            "SELECT status FROM writing_draft_segments WHERE draft_id = ?",
            (draft_row["id"],),
        ).fetchall()
        incomplete = [r for r in rows if r["status"] != "completed"]
        if incomplete:
            raise ServiceError(409, "仍有未完成的段落，请先生成完毕或取消这些段落")
        content = draft_row["content"]
        if not content.strip():
            raise ServiceError(400, "草稿正文为空，不能写入章节")

        chapter_id = draft_row["chapter_id"]
        replace = mode == "replace_existing"
        if replace and not chapter_id:
            raise ServiceError(400, "该会话没有关联章节，无法覆盖，请使用另存为新章节")
        if replace:
            chapter = conn.execute(
                "SELECT * FROM chapters WHERE id = ? AND novel_id = ?",
                (chapter_id, novel_id),
            ).fetchone()
            if chapter is None:
                raise ServiceError(404, "关联章节已不存在，请另存为新章节")
            title = str(payload.get("chapter_title") or chapter["title"]).strip()
            conn.execute(
                """
                UPDATE chapters
                   SET title = ?, content = ?, summary = ?, status = 'completed',
                       word_count = ?, updated_at = ?
                 WHERE id = ? AND novel_id = ?
                """,
                (
                    title, content, _summary_for(conn, draft_row), count_words(content),
                    now, chapter_id, novel_id,
                ),
            )
            target_chapter_id = chapter_id
        else:
            # 默认另存为新章节，绝不覆盖原章节
            row = conn.execute(
                "SELECT COALESCE(MAX(chapter_number), 0) + 1 AS n,"
                "       COALESCE(MAX(sort_order), 0) + 1 AS s"
                "  FROM chapters WHERE novel_id = ?",
                (novel_id,),
            ).fetchone()
            number = int(row["n"])
            sort_order = int(row["s"])
            title = str(
                payload.get("chapter_title") or draft_row["title"] or session_row["title"]
            ).strip() or f"第 {number} 章"
            target_chapter_id = uuid4().hex
            conn.execute(
                """
                INSERT INTO chapters
                    (id, novel_id, chapter_number, volume_number, title, content,
                     summary, status, word_count, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, NULL, ?, ?, ?, 'completed', ?, ?, ?, ?)
                """,
                (
                    target_chapter_id, novel_id, number, title, content,
                    _summary_for(conn, draft_row), count_words(content),
                    sort_order, now, now,
                ),
            )
        conn.execute(
            "UPDATE writing_drafts SET status = 'confirmed', chapter_id = ?, title = ?,"
            " confirmed_at = ?, updated_at = ? WHERE id = ?",
            (target_chapter_id, title, now, now, draft_row["id"]),
        )
        conn.execute(
            "UPDATE writing_sessions SET status = 'completed', chapter_id = ?,"
            " completed_at = ?, updated_at = ? WHERE id = ?",
            (target_chapter_id, now, now, session_id),
        )
        conn.execute("UPDATE novels SET updated_at = ? WHERE id = ?", (now, novel_id))
        chapter_row = conn.execute(
            "SELECT * FROM chapters WHERE id = ?", (target_chapter_id,)
        ).fetchone()
    return {
        "chapter": {
            "id": chapter_row["id"],
            "novel_id": chapter_row["novel_id"],
            "chapter_number": chapter_row["chapter_number"],
            "title": chapter_row["title"],
            "summary": chapter_row["summary"],
            "status": chapter_row["status"],
            "word_count": chapter_row["word_count"],
            "created_at": chapter_row["created_at"],
            "updated_at": chapter_row["updated_at"],
        },
        "mode": "replace_existing" if replace else "new_chapter",
        "session_id": session_id,
    }


def _summary_for(conn, draft_row) -> str:
    plan = None
    if draft_row["plan_id"]:
        plan = conn.execute(
            "SELECT chapter_goal FROM writing_plans WHERE id = ?",
            (draft_row["plan_id"],),
        ).fetchone()
    if plan and plan["chapter_goal"]:
        return plan["chapter_goal"][:200]
    return " ".join((draft_row["content"] or "").split())[:120]


def _mark_session_failed(novel_id: str, session_id: str, code: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE writing_sessions SET status = 'failed', error_code = ?,"
            " error_message = ?, updated_at = ? WHERE id = ? AND novel_id = ?",
            (code, message[:300], _now(), session_id, novel_id),
        )


def recover_interrupted_sessions() -> dict:
    """启动时调用：服务重启前不可能仍有在执行的生成请求，标记为可恢复的暂停。"""
    now = _now()
    with get_connection() as conn:
        segments = conn.execute(
            "UPDATE writing_draft_segments SET status = 'failed',"
            " error_code = 'interrupted_by_restart',"
            " error_message = '服务重启导致段落生成中断，请重新生成该段', updated_at = ?"
            " WHERE status = 'generating'",
            (now,),
        ).rowcount
        sessions = conn.execute(
            "UPDATE writing_sessions SET status = 'paused_for_user',"
            " error_code = 'interrupted_by_restart',"
            " error_message = '服务重启导致写作中断，可继续生成未完成段落', updated_at = ?"
            " WHERE status = 'writing'",
            (now,),
        ).rowcount
    return {"segments": segments, "sessions": sessions}
