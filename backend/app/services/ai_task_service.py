"""AI 生成任务记录：审计与排错用途。

原则：
1. 只记录摘要（前若干字符）与 Token 数据，不记录完整提示词和完整正文。
2. 绝不记录 API Key 或任何加密材料。
3. 任务记录不等同于章节草稿，不能替代章节数据。
4. 删除小说时由 novel_id 外键 CASCADE 清理（novel_service 同时显式删除）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import AI_TASK_STATUSES, AI_TASK_TYPES, get_connection
from .errors import ServiceError

_SUMMARY_MAX = 200

# 任务记录的过期判定阈值：正常情况下一次调用远小于该时长
# （适配器自身还有 timeout），超过即视为异常遗留记录
STALE_TASK_MINUTES = 15


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def interrupt_running_tasks() -> int:
    """启动时调用：进程重启前不可能仍有真实执行中的调用，遗留记录一律标记失败。

    这样「真实执行中」与「异常遗留」在语义上被明确区分，不需要后台调度系统。
    """
    now = _now()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM ai_generation_tasks WHERE status IN ('running', 'pending')"
        ).fetchall()
        if not rows:
            return 0
        conn.execute(
            """
            UPDATE ai_generation_tasks
               SET status = 'failed',
                   error_code = 'interrupted_by_restart',
                   error_message = '服务重启导致任务中断，未产生可用结果',
                   completed_at = ?
             WHERE status IN ('running', 'pending')
            """,
            (now,),
        )
    return len(rows)


def reap_stale_tasks(max_age_minutes: int = STALE_TASK_MINUTES) -> int:
    """惰性回收长时间没有心跳的 running/pending 记录（无后台调度器）。

    判定依据优先使用 heartbeat_at：长任务只要持续上报心跳就不会被误判；
    没有心跳的老记录回退到 started_at / created_at。
    """
    cutoff = datetime.now(timezone.utc).timestamp() - max(1, max_age_minutes) * 60
    now = _now()
    reaped = 0
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, started_at, created_at, heartbeat_at FROM ai_generation_tasks"
            " WHERE status IN ('running', 'pending')"
        ).fetchall()
        for row in rows:
            stamp = (
                _parse_time(row["heartbeat_at"])
                or _parse_time(row["started_at"])
                or _parse_time(row["created_at"])
            )
            if stamp is None or stamp.timestamp() >= cutoff:
                continue
            conn.execute(
                """
                UPDATE ai_generation_tasks
                   SET status = 'failed',
                       error_code = 'stale_timeout',
                       error_message = ?,
                       completed_at = ?
                 WHERE id = ? AND status = 'running'
                """,
                (
                    f"任务超过 {max_age_minutes} 分钟没有心跳，已按异常遗留记录终止",
                    now,
                    row["id"],
                ),
            )
            reaped += 1
    return reaped


def touch_task(task_id: str) -> None:
    """刷新任务心跳：长任务执行过程中定期调用，避免被惰性回收误判。"""
    if not task_id:
        return
    with get_connection() as conn:
        conn.execute(
            "UPDATE ai_generation_tasks SET heartbeat_at = ?"
            " WHERE id = ? AND status = 'running'",
            (_now(), task_id),
        )


def summarize(text: str, limit: int = _SUMMARY_MAX) -> str:
    """生成输入/输出摘要：压缩空白并截断，保证不保存完整内容。"""
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "…"


def create_task(
    *,
    novel_id: str,
    task_type: str,
    model_id: str | None,
    model_identifier: str,
    provider_id: str | None,
    prompt_template_id: str | None,
    template_version: int | None,
    input_summary: str,
    estimated_tokens: int | None,
) -> str:
    if task_type not in AI_TASK_TYPES:
        raise ServiceError(400, "不支持的任务类型")
    task_id = uuid4().hex
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ai_generation_tasks
                (id, novel_id, task_type, model_id, model_identifier, provider_id,
                 status, input_summary, output_summary, error_code, error_message,
                 prompt_template_id, template_version, input_tokens, output_tokens,
                 estimated_tokens, truncated, latency_ms, started_at, completed_at,
                 heartbeat_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'running', ?, '', NULL, NULL, ?, ?, NULL, NULL,
                    ?, 0, NULL, ?, NULL, ?, ?)
            """,
            (
                task_id,
                novel_id,
                task_type,
                model_id,
                model_identifier,
                provider_id,
                input_summary,
                prompt_template_id,
                template_version,
                estimated_tokens,
                now,
                now,
                now,
            ),
        )
    return task_id


def complete_task(
    task_id: str,
    *,
    output_summary: str,
    input_tokens: int | None,
    output_tokens: int | None,
    truncated: bool,
    latency_ms: int | None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE ai_generation_tasks
               SET status = 'completed', output_summary = ?,
                   input_tokens = ?, output_tokens = ?, truncated = ?,
                   latency_ms = ?, completed_at = ?
             WHERE id = ?
            """,
            (
                output_summary,
                input_tokens,
                output_tokens,
                1 if truncated else 0,
                latency_ms,
                _now(),
                task_id,
            ),
        )


def fail_task(
    task_id: str,
    *,
    error_code: str,
    error_message: str,
    output_summary: str = "",
    latency_ms: int | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE ai_generation_tasks
               SET status = 'failed', output_summary = ?, error_code = ?,
                   error_message = ?, latency_ms = ?, completed_at = ?
             WHERE id = ?
            """,
            (
                output_summary,
                error_code,
                error_message[:300],
                latency_ms,
                _now(),
                task_id,
            ),
        )


def _to_out(row) -> dict:
    return {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "task_type": row["task_type"],
        "model_id": row["model_id"],
        "model_identifier": row["model_identifier"],
        "provider_id": row["provider_id"],
        "status": row["status"],
        "input_summary": row["input_summary"],
        "output_summary": row["output_summary"],
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "prompt_template_id": row["prompt_template_id"],
        "template_version": row["template_version"],
        "input_tokens": row["input_tokens"],
        "output_tokens": row["output_tokens"],
        "estimated_tokens": row["estimated_tokens"],
        "truncated": bool(row["truncated"]),
        "latency_ms": row["latency_ms"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "created_at": row["created_at"],
    }


def list_tasks(
    novel_id: str,
    *,
    status: str | None = None,
    task_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    # 查询前惰性回收异常遗留记录，避免永久 running
    reap_stale_tasks()
    with get_connection() as conn:
        novel = conn.execute(
            "SELECT id FROM novels WHERE id = ?", (novel_id,)
        ).fetchone()
        if novel is None:
            raise ServiceError(404, "小说不存在")

        sql = ["SELECT * FROM ai_generation_tasks WHERE novel_id = ?"]
        params: list[object] = [novel_id]
        if status and status.strip():
            if status.strip() not in AI_TASK_STATUSES:
                raise ServiceError(400, "不支持的任务状态")
            sql.append(" AND status = ?")
            params.append(status.strip())
        if task_type and task_type.strip():
            if task_type.strip() not in AI_TASK_TYPES:
                raise ServiceError(400, "不支持的任务类型")
            sql.append(" AND task_type = ?")
            params.append(task_type.strip())
        sql.append(" ORDER BY created_at DESC, id DESC LIMIT ?")
        params.append(max(1, min(int(limit or 100), 500)))
        rows = conn.execute("\n".join(sql), params).fetchall()
    return [_to_out(row) for row in rows]


def get_task(novel_id: str, task_id: str) -> dict:
    reap_stale_tasks()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ai_generation_tasks WHERE id = ? AND novel_id = ?",
            (task_id, novel_id),
        ).fetchone()
    if row is None:
        raise ServiceError(404, "AI 任务不存在")
    return _to_out(row)
