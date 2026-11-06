"""快速写作（P4.2）。

目标：打开小说 → 输入想写的内容 → 选风格/模型 → 生成正文 → 阅读修改保存。

与 P4.1.2 剧情计划工作流并存但完全独立：
- 不创建剧情计划，不审核重大决定；
- 分段按需生成，失败保留已完成内容，可继续、可重写；
- 只有用户显式确认才写入 chapters 正式章节。

上下文复用 context_builder 与 token 预算，绝不无条件注入整部小说全文。
连续性检查与记忆提取不在本服务中自动执行，只把开关状态返回给前端，
由用户手动触发 P4.1.3 的接口。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import QUICK_CONTEXT_MODES, get_connection
from . import (
    ai_generation_service,
    ai_task_service,
    chapter_service,
    context_builder,
    writing_preset_service,
)
from .errors import ServiceError

logger = logging.getLogger(__name__)

_SEGMENT_CALL_TIMEOUT = 240.0
_GENERATING_GUARD_SECONDS = 300
_MAX_SEGMENTS = 30
_MAX_CONTENT_CHARS = 200000

_DEFAULT_WRITER_SYSTEM = (
    "你是一部长篇小说的正文作者。你的文字风格稳定，严格遵循给定的世界观、"
    "人物设定与剧情走向。你只能使用上下文中提供的信息，"
    "不得编造与设定冲突的情节，不得让人物知道他们在故事中不可能知道的秘密。"
)
_WRITER_CONSTRAINT = """
你只输出小说正文本身，不要输出任何解释、标题、JSON 或自我评价。
不要用思维链替代正文。不要重复已经写过的内容。
"""

# 可被「自定义上下文」单独选中的内置分区 key（与 context_builder 保持一致）
CONTEXT_SECTION_KEYS = (
    "core_settings",
    "current_task",
    "characters",
    "character_states",
    "character_relations",
    "character_secrets",
    "plot_history",
)

_RECENT_MODE_EXCLUDES = (
    "core_settings",
    "characters",
    "character_states",
    "character_relations",
    "character_secrets",
)


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


def _parse_json_object(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _ensure_novel(conn, novel_id: str) -> None:
    row = conn.execute("SELECT id FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")


def _session_row(conn, novel_id: str, session_id: str):
    row = conn.execute(
        "SELECT * FROM quick_writing_sessions WHERE id = ? AND novel_id = ?",
        (session_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "快速写作会话不存在")
    return row


def _segments(conn, session_id: str) -> list:
    return conn.execute(
        "SELECT * FROM quick_writing_segments WHERE session_id = ? ORDER BY seq ASC",
        (session_id,),
    ).fetchall()


def _segment_to_out(row) -> dict:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "seq": row["seq"],
        "content": row["content"],
        "word_count": row["word_count"],
        "status": row["status"],
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "task_id": row["task_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _preset_name(conn, preset_id: str | None) -> str:
    if not preset_id:
        return ""
    row = conn.execute(
        "SELECT name FROM prompt_templates WHERE id = ?", (preset_id,)
    ).fetchone()
    return row["name"] if row else ""


def _to_session(conn, row) -> dict:
    segments = _segments(conn, row["id"])
    completed = [s for s in segments if s["status"] == "completed" and s["content"].strip()]
    return {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "chapter_id": row["chapter_id"],
        "title": row["title"],
        "user_requirement": row["user_requirement"],
        "preset_id": row["preset_id"],
        "preset_name": _preset_name(conn, row["preset_id"]),
        "model_id": row["model_id"],
        "model_label": row["model_label"],
        "context_mode": row["context_mode"],
        "context_options": _parse_json_object(row["context_options"]),
        "style_overrides": _parse_json_object(row["style_overrides"]),
        "target_word_count": row["target_word_count"],
        "segment_words": row["segment_words"],
        "auto_continuity": bool(row["auto_continuity"]),
        "auto_memory": bool(row["auto_memory"]),
        "remind_memory": bool(row["remind_memory"]),
        "status": row["status"],
        "content": row["content"],
        "word_count": row["word_count"],
        "edited": bool(row["edited"]),
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "generating_seq": row["generating_seq"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "confirmed_at": row["confirmed_at"],
        "segments": [_segment_to_out(item) for item in segments],
        "progress": {
            "completed_segments": len(completed),
            "total_segments": len(segments),
            "target_word_count": row["target_word_count"],
            "remaining_words": max(0, int(row["target_word_count"]) - int(row["word_count"] or 0)),
        },
    }


def _validate_preset(preset_id: str | None) -> dict | None:
    if not preset_id:
        return None
    try:
        preset = writing_preset_service.get_preset(preset_id)
    except ServiceError as exc:
        raise ServiceError(400, "指定的写作预设不存在") from exc
    if not preset["is_active"]:
        raise ServiceError(400, "指定的写作预设已停用")
    return preset


def _validate_model(conn, model_id: str | None) -> tuple[str | None, str]:
    """校验模型可用性并返回 (model_id, 展示名称)。不接触任何密钥。"""
    if not model_id:
        return None, ""
    row = conn.execute(
        """
        SELECT m.id, m.name, m.model_id, m.enabled, p.enabled AS provider_enabled
          FROM models m
          JOIN providers p ON p.id = m.provider_id
         WHERE m.id = ?
        """,
        (model_id,),
    ).fetchone()
    if row is None:
        raise ServiceError(400, "指定的模型不存在")
    if not row["enabled"] or not row["provider_enabled"]:
        raise ServiceError(400, "指定的模型或供应商已停用")
    return row["id"], (row["name"] or row["model_id"])


def _check_context_mode(mode: str) -> str:
    if mode not in QUICK_CONTEXT_MODES:
        raise ServiceError(400, "不支持的上下文注入方式")
    return mode


def _validate_chapter(conn, novel_id: str, chapter_id: str | None) -> str | None:
    if not chapter_id:
        return None
    row = conn.execute(
        "SELECT id FROM chapters WHERE id = ? AND novel_id = ?",
        (chapter_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "章节不存在或不属于当前小说")
    return chapter_id


def create_session(novel_id: str, payload: dict) -> dict:
    now = _now()
    session_id = uuid4().hex
    # 显式预设 > 小说指定 > 全局默认；创建时固化到会话，后续不会静默漂移
    preset_id = str(payload.get("preset_id") or "").strip() or None
    if preset_id:
        _validate_preset(preset_id)
    else:
        resolved = writing_preset_service.resolve_preset(novel_id, None)
        preset_id = resolved["id"] if resolved else None
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        chapter_id = _validate_chapter(conn, novel_id, payload.get("chapter_id"))
        model_id, model_label = _validate_model(conn, payload.get("model_id"))
        mode = _check_context_mode(str(payload.get("context_mode") or "auto"))
        conn.execute(
            """
            INSERT INTO quick_writing_sessions
                (id, novel_id, chapter_id, title, user_requirement, preset_id,
                 model_id, model_label, context_mode, context_options,
                 style_overrides, target_word_count, segment_words,
                 auto_continuity, auto_memory, remind_memory, status, content,
                 word_count, edited, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'drafting',
                    '', 0, 0, ?, ?)
            """,
            (
                session_id,
                novel_id,
                chapter_id,
                str(payload.get("title") or "").strip(),
                str(payload.get("user_requirement") or "").strip(),
                preset_id,
                model_id,
                model_label,
                mode,
                json.dumps(payload.get("context_options") or {}, ensure_ascii=False),
                json.dumps(payload.get("style_overrides") or {}, ensure_ascii=False),
                int(payload.get("target_word_count") or 1500),
                int(payload.get("segment_words") or 700),
                1 if payload.get("auto_continuity") else 0,
                1 if payload.get("auto_memory") else 0,
                1 if payload.get("remind_memory", True) else 0,
                now,
                now,
            ),
        )
        row = _session_row(conn, novel_id, session_id)
        return _to_session(conn, row)


def list_sessions(novel_id: str, *, status: str | None = None) -> list[dict]:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        sql = ["SELECT * FROM quick_writing_sessions WHERE novel_id = ?"]
        params: list[object] = [novel_id]
        if status:
            if status not in ("drafting", "ready", "confirmed", "discarded", "failed"):
                raise ServiceError(400, "不支持的会话状态")
            sql.append(" AND status = ?")
            params.append(status)
        sql.append(" ORDER BY updated_at DESC, created_at DESC")
        rows = conn.execute("\n".join(sql), params).fetchall()
        return [_to_session(conn, row) for row in rows]


def get_session(novel_id: str, session_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        return _to_session(conn, _session_row(conn, novel_id, session_id))


_EDITABLE_FIELDS = (
    "title",
    "user_requirement",
    "target_word_count",
    "segment_words",
    "context_mode",
    "context_options",
    "style_overrides",
    "auto_continuity",
    "auto_memory",
    "remind_memory",
)


def update_session(novel_id: str, session_id: str, fields: dict) -> dict:
    now = _now()
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        if row["status"] in ("confirmed", "discarded"):
            raise ServiceError(409, "会话已结束，不能再修改配置")
        updates: dict[str, object] = {}
        for key in _EDITABLE_FIELDS:
            if key not in fields:
                continue
            if key == "title":
                updates[key] = str(fields[key] or "").strip()
            elif key == "user_requirement":
                updates[key] = str(fields[key] or "").strip()
            elif key in ("target_word_count", "segment_words"):
                updates[key] = int(fields[key])
            elif key == "context_mode":
                updates[key] = _check_context_mode(str(fields[key]))
            elif key in ("context_options", "style_overrides"):
                updates[key] = json.dumps(fields[key] or {}, ensure_ascii=False)
            else:
                updates[key] = 1 if fields[key] else 0
        if "preset_id" in fields:
            preset_id = str(fields.get("preset_id") or "").strip() or None
            if preset_id:
                _validate_preset(preset_id)
            updates["preset_id"] = preset_id
        if "model_id" in fields:
            model_id, model_label = _validate_model(conn, fields.get("model_id"))
            updates["model_id"] = model_id
            updates["model_label"] = model_label
        if "chapter_id" in fields:
            updates["chapter_id"] = _validate_chapter(
                conn, novel_id, str(fields.get("chapter_id") or "").strip() or None
            )
        if not updates:
            return _to_session(conn, row)
        updates["updated_at"] = now
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE quick_writing_sessions SET {assignments} WHERE id = ?",
            list(updates.values()) + [session_id],
        )
        return _to_session(conn, _session_row(conn, novel_id, session_id))


def discard_session(novel_id: str, session_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        _session_row(conn, novel_id, session_id)
        conn.execute(
            "UPDATE quick_writing_sessions SET status = 'discarded', updated_at = ? WHERE id = ?",
            (_now(), session_id),
        )
        return _to_session(conn, _session_row(conn, novel_id, session_id))


def delete_session(novel_id: str, session_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        _session_row(conn, novel_id, session_id)
        # 分段通过 session_id 外键级联清理；已确认写入的章节不受影响
        conn.execute("DELETE FROM quick_writing_sessions WHERE id = ?", (session_id,))
    return {"deleted": True}


# ----------------------------- 上下文注入 -----------------------------

def _recent_chapter_tails(
    conn, novel_id: str, *, exclude_chapter_id: str | None, count: int, tail_chars: int
) -> str:
    rows = conn.execute(
        """
        SELECT chapter_number, title, content
          FROM chapters
         WHERE novel_id = ? AND content != '' AND id != ?
         ORDER BY chapter_number DESC
         LIMIT ?
        """,
        (novel_id, exclude_chapter_id or "", max(1, min(count, 5))),
    ).fetchall()
    blocks: list[str] = []
    for row in reversed(rows):
        text = (row["content"] or "").strip()
        if not text:
            continue
        tail = text[-tail_chars:] if len(text) > tail_chars else text
        blocks.append(f"第 {row['chapter_number']} 章《{row['title']}》结尾：\n{tail}")
    return "\n\n".join(blocks)


def _build_context(session_row, *, extra_requirement: str) -> dict:
    mode = session_row["context_mode"]
    options = _parse_json_object(session_row["context_options"])
    novel_id = session_row["novel_id"]
    exclude: list[str] = []
    extras: list[dict] = []

    with get_connection() as conn:
        if mode == "recent":
            exclude = list(_RECENT_MODE_EXCLUDES)
            text = _recent_chapter_tails(
                conn, novel_id,
                exclude_chapter_id=session_row["chapter_id"],
                count=1, tail_chars=2000,
            )
            if text:
                extras.append(
                    {"key": "recent_chapter", "title": "最近章节正文",
                     "content": text, "priority": 96, "required": True}
                )
        elif mode == "auto":
            text = _recent_chapter_tails(
                conn, novel_id,
                exclude_chapter_id=session_row["chapter_id"],
                count=1, tail_chars=1200,
            )
            if text:
                extras.append(
                    {"key": "recent_chapter", "title": "最近章节结尾",
                     "content": text, "priority": 72}
                )
        elif mode == "full":
            text = _recent_chapter_tails(
                conn, novel_id,
                exclude_chapter_id=session_row["chapter_id"],
                count=int(options.get("recent_chapters") or 2),
                tail_chars=int(options.get("recent_chapter_chars") or 1500),
            )
            if text:
                extras.append(
                    {"key": "recent_chapter", "title": "最近章节正文",
                     "content": text, "priority": 72}
                )
        elif mode == "custom":
            selected = options.get("sections")
            if isinstance(selected, list) and selected:
                chosen = {str(item) for item in selected}
                exclude = [key for key in CONTEXT_SECTION_KEYS if key not in chosen]
            if options.get("include_recent_chapter"):
                text = _recent_chapter_tails(
                    conn, novel_id,
                    exclude_chapter_id=session_row["chapter_id"],
                    count=int(options.get("recent_chapters") or 1),
                    tail_chars=int(options.get("recent_chapter_chars") or 1500),
                )
                if text:
                    extras.append(
                        {"key": "recent_chapter", "title": "最近章节正文",
                         "content": text, "priority": 72}
                    )

    requirement = session_row["user_requirement"] or ""
    if extra_requirement:
        requirement = f"{requirement}\n{extra_requirement}".strip()
    return context_builder.build_context(
        novel_id,
        task_type="writer",
        chapter_id=session_row["chapter_id"],
        pov="author",
        user_requirement=requirement,
        extra_sections=extras,
        exclude_sections=exclude,
    )


def _segment_task(session_row, seq: int, remaining: int) -> str:
    target = int(session_row["target_word_count"])
    written = int(session_row["word_count"] or 0)
    segment_words = int(session_row["segment_words"])
    parts: list[str] = []
    if session_row["user_requirement"]:
        parts.append(f"作者写作要求：{session_row['user_requirement']}")
    parts.append(f"本章目标字数约 {target} 字，当前已写 {written} 字。")
    parts.append(f"本次生成第 {seq} 段。")
    if remaining <= segment_words:
        parts.append(
            f"这是本章最后一段，约 {max(200, remaining)} 字，请自然收束本章，"
            "不要留下明显未完成的悬念。"
        )
    else:
        parts.append(f"本段约 {segment_words} 字，不要写到后续内容，结尾自然衔接下一段。")
    content = (session_row["content"] or "").strip()
    if content:
        parts.append(f"已写内容的结尾（仅用于衔接，禁止重复）：\n{content[-500:]}")
    return "\n".join(parts)


def preview_context(novel_id: str, session_id: str, extra_requirement: str = "") -> dict:
    """只组装上下文并返回分区结果，不发起任何模型调用。"""
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        session_row = _session_row(conn, novel_id, session_id)
    return _build_context(session_row, extra_requirement=extra_requirement)


def _compose_system(session_row) -> str:
    preset = None
    if session_row["preset_id"]:
        try:
            preset = writing_preset_service.get_preset(session_row["preset_id"])
        except ServiceError:
            preset = None
    overrides = _parse_json_object(session_row["style_overrides"])
    base = writing_preset_service.build_system_prompt(preset, overrides)
    if not base.strip():
        base = _DEFAULT_WRITER_SYSTEM
    return f"{base}\n{_WRITER_CONSTRAINT}"


def _next_seq(conn, session_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM quick_writing_segments WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return int(row["n"])


def _join_segments(segments) -> str:
    return "\n\n".join(
        item["content"].strip()
        for item in segments
        if item["status"] == "completed" and item["content"].strip()
    )


def _mark_generating(conn, session_id: str, seq: int, now: str) -> None:
    conn.execute(
        "UPDATE quick_writing_sessions SET generating_seq = ?, generating_at = ?,"
        " error_code = NULL, error_message = NULL, updated_at = ? WHERE id = ?",
        (seq, now, now, session_id),
    )


def _clear_generating(conn, session_id: str, now: str, *, error_code: str | None = None,
                      error_message: str | None = None) -> None:
    conn.execute(
        "UPDATE quick_writing_sessions SET generating_seq = NULL, generating_at = NULL,"
        " error_code = ?, error_message = ?, updated_at = ? WHERE id = ?",
        (error_code, (error_message or "")[:300] or None, now, session_id),
    )


async def generate_segment(novel_id: str, session_id: str, payload: dict) -> dict:
    """生成一段正文；失败保留已完成内容并记录错误原因。"""
    now = _now()
    requested_seq = payload.get("seq")
    if requested_seq is not None:
        try:
            requested_seq = int(requested_seq)
        except (TypeError, ValueError) as exc:
            raise ServiceError(400, "段落序号不合法") from exc
        if requested_seq < 1:
            raise ServiceError(400, "段落序号不合法")

    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        session_row = _session_row(conn, novel_id, session_id)
        if session_row["status"] in ("confirmed", "discarded"):
            raise ServiceError(409, "会话已结束，不能继续生成")
        if session_row["generating_seq"] is not None:
            if _age_seconds(session_row["generating_at"]) < _GENERATING_GUARD_SECONDS:
                raise ServiceError(409, "已有段落正在生成中，请等待完成")
            # 超时遗留任务允许接管
            _clear_generating(conn, session_id, now)

        segments = _segments(conn, session_id)
        existing = {item["seq"]: item for item in segments}
        # 未显式指定时优先重试失败的段落，失败不会额外占用段号
        failed = next((item for item in segments if item["status"] == "failed"), None)
        if requested_seq is None and failed is not None:
            requested_seq = failed["seq"]
        is_rewrite = requested_seq is not None and requested_seq in existing
        if requested_seq is not None and not is_rewrite and requested_seq != _next_seq(
            conn, session_id
        ):
            raise ServiceError(404, "段落不存在")
        seq = requested_seq or _next_seq(conn, session_id)
        if seq > _MAX_SEGMENTS:
            raise ServiceError(409, "分段数量已达上限，请编辑正文或保存章节")

        remaining = int(session_row["target_word_count"]) - int(session_row["word_count"] or 0)
        if requested_seq is None and remaining <= 0:
            raise ServiceError(409, "已达到目标字数，如需继续请先在设置中提高目标字数")

        _mark_generating(conn, session_id, seq, now)
        session_row = _session_row(conn, novel_id, session_id)

    context = _build_context(
        session_row, extra_requirement=str(payload.get("extra_instruction") or "").strip()
    )
    task_text = _segment_task(session_row, seq, remaining)
    system = _compose_system(session_row)
    user_prompt = f"以下是小说的上下文资料：\n{context['context_text']}\n\n请创作本段正文。\n{task_text}"
    template_id = session_row["preset_id"] if session_row["preset_id"] else None
    template_version = None
    if template_id:
        try:
            template_version = writing_preset_service.get_preset(template_id)["version"]
        except ServiceError:
            template_id = None

    result: dict = {}
    try:
        result = await ai_generation_service.generate(
            {
                "novel_id": novel_id,
                "task_type": "writer",
                "system_prompt": system,
                "user_prompt": user_prompt,
                "prompt_template_id": template_id,
                "template_version": template_version,
                "model_id": session_row["model_id"],
                "temperature": float(payload.get("temperature", 0.8)),
                "max_tokens": int(payload.get("max_tokens") or 8192),
                "timeout": _SEGMENT_CALL_TIMEOUT,
                "include_reasoning": False,
            }
        )
    except ServiceError as exc:
        with get_connection() as conn:
            _clear_generating(
                conn, session_id, _now(),
                error_code="request_error", error_message=exc.message,
            )
        raise
    except Exception:
        logger.exception("快速写作生成异常")
        with get_connection() as conn:
            _clear_generating(
                conn, session_id, _now(),
                error_code="server_error", error_message="生成过程出现异常",
            )
        raise ServiceError(500, "生成过程出现异常，已保留已完成内容")

    ai_task_service.touch_task(result.get("task_id") or "")

    if not result.get("success"):
        code = result.get("error_code") or "ai_error"
        message = result.get("error_message") or "模型调用失败"
        _record_failure(novel_id, session_id, seq, code, message, result.get("task_id"), now)
        raise ServiceError(502, f"生成失败：{message}（{code}）")
    if result.get("truncated"):
        message = "输出达到 max_tokens 上限被截断，未保存该段，请增大 max_tokens 后重试"
        _record_failure(
            novel_id, session_id, seq, "truncated", message, result.get("task_id"), now
        )
        raise ServiceError(502, message)

    chunk = str(result.get("content") or "")
    if not chunk.strip():
        _record_failure(
            novel_id, session_id, seq, "empty_content", "模型返回空正文，未保存该段",
            result.get("task_id"), now,
        )
        raise ServiceError(502, "模型返回空正文，未保存该段")

    now = _now()
    with get_connection() as conn:
        if is_rewrite:
            conn.execute(
                "UPDATE quick_writing_segments SET content = ?, word_count = ?,"
                " status = 'completed', error_code = NULL, error_message = NULL,"
                " task_id = ?, updated_at = ? WHERE session_id = ? AND seq = ?",
                (
                    chunk, chapter_service.count_words(chunk), result.get("task_id"),
                    now, session_id, seq,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO quick_writing_segments
                    (id, novel_id, session_id, seq, content, word_count, status,
                     task_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?)
                """,
                (
                    uuid4().hex, novel_id, session_id, seq, chunk,
                    chapter_service.count_words(chunk), result.get("task_id"), now, now,
                ),
            )
        all_segments = _segments(conn, session_id)
        discarded_edits = bool(is_rewrite and session_row["edited"])
        if session_row["edited"] and session_row["content"].strip() and not is_rewrite:
            # 用户手工编辑过的正文继续向后追加，不覆盖其编辑内容
            content = f"{session_row['content'].rstrip()}\n\n{chunk.strip()}"
            edited_flag = 1
        else:
            content = _join_segments(all_segments)
            # 重写段落会按分段重建正文，此时手工编辑已被丢弃（响应中明确告知）
            edited_flag = 0
        words = chapter_service.count_words(content)
        status = "ready" if words >= int(session_row["target_word_count"]) else "drafting"
        conn.execute(
            "UPDATE quick_writing_sessions SET content = ?, word_count = ?, status = ?,"
            " edited = ?, error_code = NULL, error_message = NULL,"
            " generating_seq = NULL, generating_at = NULL, updated_at = ? WHERE id = ?",
            (content, words, status, edited_flag, now, session_id),
        )
        session_out = _to_session(conn, _session_row(conn, novel_id, session_id))

    return {
        "session": session_out,
        "segment_seq": seq,
        "usage": result.get("usage") or {},
        "latency_ms": result.get("latency_ms"),
        "task_id": result.get("task_id"),
        "model": result.get("model") or "",
        "provider": result.get("provider") or "",
        "resolved_from": result.get("resolved_from"),
        "context_estimated_tokens": context["estimated_tokens"],
        "context_token_budget": context["token_budget"],
        "context_omitted_sections": context["omitted_sections"],
        "context_warnings": context["warnings"],
        "discarded_manual_edits": discarded_edits,
    }


def _record_failure(
    novel_id: str, session_id: str, seq: int, code: str, message: str,
    task_id: str | None, now: str,
) -> None:
    """失败分段保留记录（含服务商拒绝原因），已完成内容不受影响。"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM quick_writing_segments WHERE session_id = ? AND seq = ?",
            (session_id, seq),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO quick_writing_segments
                    (id, novel_id, session_id, seq, content, word_count, status,
                     error_code, error_message, task_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, '', 0, 'failed', ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex, novel_id, session_id, seq, code, message[:300],
                    task_id, now, now,
                ),
            )
        else:
            conn.execute(
                "UPDATE quick_writing_segments SET status = 'failed', error_code = ?,"
                " error_message = ?, task_id = ?, updated_at = ?"
                " WHERE session_id = ? AND seq = ?",
                (code, message[:300], task_id, now, session_id, seq),
            )
        _clear_generating(conn, session_id, now, error_code=code, error_message=message)


def update_content(novel_id: str, session_id: str, content: str) -> dict:
    """手工编辑草稿：内容成为当前草稿的唯一来源，保存时原样写入章节。"""
    content = str(content or "")
    if len(content) > _MAX_CONTENT_CHARS:
        raise ServiceError(400, "正文过长，请分段保存")
    now = _now()
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        if row["status"] in ("confirmed", "discarded"):
            raise ServiceError(409, "会话已结束，不能再编辑正文")
        words = chapter_service.count_words(content)
        conn.execute(
            "UPDATE quick_writing_sessions SET content = ?, word_count = ?, edited = 1,"
            " status = ?, updated_at = ? WHERE id = ?",
            (content, words, "ready" if content.strip() else "drafting", now, session_id),
        )
        return _to_session(conn, _session_row(conn, novel_id, session_id))


# ----------------------------- 保存为正式章节 -----------------------------

def _summary(content: str, provided: str) -> str:
    text = str(provided or "").strip()
    if text:
        return text[:200]
    return " ".join(content.split())[:120]


def confirm_session(novel_id: str, session_id: str, payload: dict) -> dict:
    """把快速写作正文写入正式章节。

    - 默认另存为新章节（章节号 max+1），绝不覆盖其它章节；
    - replace_existing 只能覆盖本会话关联的章节；
    - 整个过程单事务完成，失败不会留下半写状态。
    """
    mode = str(payload.get("mode") or "new_chapter").strip()
    if mode not in ("new_chapter", "replace_existing"):
        raise ServiceError(400, "不支持的写入模式")
    now = _now()
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _session_row(conn, novel_id, session_id)
        if row["status"] in ("confirmed", "discarded"):
            raise ServiceError(409, "会话已结束，不能重复保存")
        content = row["content"] or ""
        if not content.strip():
            raise ServiceError(400, "正文为空，不能保存为章节")
        words = chapter_service.count_words(content)
        summary = _summary(content, str(payload.get("summary") or "")[:500])
        title = str(payload.get("chapter_title") or row["title"] or "").strip()

        chapter_id = row["chapter_id"]
        if mode == "replace_existing":
            if not chapter_id:
                raise ServiceError(400, "该会话没有关联章节，无法覆盖，请另存为新章节")
            chapter = conn.execute(
                "SELECT * FROM chapters WHERE id = ? AND novel_id = ?",
                (chapter_id, novel_id),
            ).fetchone()
            if chapter is None:
                raise ServiceError(404, "关联章节已不存在，请另存为新章节")
            conn.execute(
                """
                UPDATE chapters
                   SET title = ?, content = ?, summary = ?, status = 'completed',
                       word_count = ?, updated_at = ?
                 WHERE id = ? AND novel_id = ?
                """,
                (
                    title or chapter["title"], content, summary, words, now,
                    chapter_id, novel_id,
                ),
            )
        else:
            seq_row = conn.execute(
                "SELECT COALESCE(MAX(chapter_number), 0) + 1 AS n,"
                "       COALESCE(MAX(sort_order), 0) + 1 AS s"
                "  FROM chapters WHERE novel_id = ?",
                (novel_id,),
            ).fetchone()
            number = int(seq_row["n"])
            sort_order = int(seq_row["s"])
            chapter_id = uuid4().hex
            conn.execute(
                """
                INSERT INTO chapters
                    (id, novel_id, chapter_number, volume_number, title, content,
                     summary, status, word_count, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, NULL, ?, ?, ?, 'completed', ?, ?, ?, ?)
                """,
                (
                    chapter_id, novel_id, number, title or f"第 {number} 章", content,
                    summary, words, sort_order, now, now,
                ),
            )
        conn.execute(
            "UPDATE quick_writing_sessions SET status = 'confirmed', chapter_id = ?,"
            " content = ?, word_count = ?, confirmed_at = ?, updated_at = ? WHERE id = ?",
            (chapter_id, content, words, now, now, session_id),
        )
        conn.execute("UPDATE novels SET updated_at = ? WHERE id = ?", (now, novel_id))
        chapter_row = conn.execute(
            "SELECT * FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()
        session_out = _to_session(conn, _session_row(conn, novel_id, session_id))

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
        "mode": mode,
        "session": session_out,
        "reminders": {
            "auto_continuity": session_out["auto_continuity"],
            "auto_memory": session_out["auto_memory"],
            "remind_memory": session_out["remind_memory"],
        },
    }
