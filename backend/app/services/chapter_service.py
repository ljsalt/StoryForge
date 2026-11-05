"""章节业务逻辑。

设计要点：
1. 章节属于小说，所有读写都以 novel_id 校验归属，跨小说访问一律 404。
2. 排序不依赖数据库返回顺序：列表统一按 sort_order, chapter_number, created_at 排序。
3. chapter_number 在同一小说内唯一；调整顺序时同时重写 sort_order 与 chapter_number
   （两阶段更新，避免唯一约束在中间状态冲突）。
4. word_count 只由后端根据正文计算，接口不接受前端传入的字数。
5. 删除章节时在同一事务内把剧情事件与人物关系历史的 chapter_id 置空，历史数据保留。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import CHAPTER_STATUSES, get_connection
from .errors import ServiceError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def count_words(content: str) -> int:
    """按非空白字符计数（中文按字、英文按字符），与前端实时预览口径一致。"""
    return len("".join(content.split()))


def _ensure_novel(novel_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")


def _chapter_row(
    conn: sqlite3.Connection, novel_id: str, chapter_id: str
) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM chapters WHERE id = ? AND novel_id = ?",
        (chapter_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "章节不存在")
    return row


def _to_out(row: sqlite3.Row, *, include_content: bool) -> dict:
    data = {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "chapter_number": row["chapter_number"],
        "volume_number": row["volume_number"],
        "title": row["title"],
        "summary": row["summary"],
        "status": row["status"],
        "word_count": row["word_count"],
        "sort_order": row["sort_order"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_content:
        data["content"] = row["content"]
    return data


def _check_status(status: str) -> None:
    if status not in CHAPTER_STATUSES:
        raise ServiceError(400, "不支持的章节状态")


def list_chapters(
    novel_id: str,
    *,
    status: str | None = None,
    volume_number: int | None = None,
    search: str | None = None,
) -> list[dict]:
    _ensure_novel(novel_id)
    if status and status.strip():
        _check_status(status.strip())

    sql = "SELECT * FROM chapters WHERE novel_id = ?"
    params: list[object] = [novel_id]
    if status and status.strip():
        sql += " AND status = ?"
        params.append(status.strip())
    if volume_number is not None:
        sql += " AND volume_number = ?"
        params.append(volume_number)
    if search and search.strip():
        keyword = f"%{search.strip()}%"
        sql += " AND (title LIKE ? OR summary LIKE ?)"
        params.extend([keyword, keyword])
    sql += " ORDER BY sort_order ASC, chapter_number ASC, created_at ASC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_to_out(row, include_content=False) for row in rows]


def get_chapter(novel_id: str, chapter_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = _chapter_row(conn, novel_id, chapter_id)
    return _to_out(row, include_content=True)


def create_chapter(novel_id: str, payload: dict) -> dict:
    _ensure_novel(novel_id)
    now = _now()
    chapter_id = uuid4().hex
    content = payload.get("content") or ""
    status = payload.get("status") or "planned"
    _check_status(status)

    with get_connection() as conn:
        if payload.get("chapter_number") is not None:
            number = int(payload["chapter_number"])
            dup = conn.execute(
                "SELECT id FROM chapters WHERE novel_id = ? AND chapter_number = ?",
                (novel_id, number),
            ).fetchone()
            if dup is not None:
                raise ServiceError(400, f"第 {number} 章已存在")
            sort_order = number
        else:
            row = conn.execute(
                "SELECT COALESCE(MAX(chapter_number), 0) + 1 AS n,"
                "       COALESCE(MAX(sort_order), 0) + 1 AS s"
                "  FROM chapters WHERE novel_id = ?",
                (novel_id,),
            ).fetchone()
            number = int(row["n"])
            sort_order = int(row["s"])

        conn.execute(
            """
            INSERT INTO chapters
                (id, novel_id, chapter_number, volume_number, title, content,
                 summary, status, word_count, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chapter_id,
                novel_id,
                number,
                payload.get("volume_number"),
                payload["title"],
                content,
                payload.get("summary") or "",
                status,
                count_words(content),
                sort_order,
                now,
                now,
            ),
        )
        # 新建章节时同步更新小说更新时间，便于列表按活跃度排序
        conn.execute("UPDATE novels SET updated_at = ? WHERE id = ?", (now, novel_id))
    return get_chapter(novel_id, chapter_id)


def update_chapter(novel_id: str, chapter_id: str, fields: dict) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _chapter_row(conn, novel_id, chapter_id)

        updates: dict[str, object] = {}
        for key in ("title", "summary", "volume_number", "status"):
            if fields.get(key) is not None:
                updates[key] = fields[key]
        if fields.get("status") is not None:
            _check_status(str(fields["status"]))

        if fields.get("chapter_number") is not None:
            number = int(fields["chapter_number"])
            dup = conn.execute(
                "SELECT id FROM chapters"
                " WHERE novel_id = ? AND chapter_number = ? AND id != ?",
                (novel_id, number, chapter_id),
            ).fetchone()
            if dup is not None:
                raise ServiceError(400, f"第 {number} 章已存在")
            updates["chapter_number"] = number

        # 字数永远由后端根据正文重新计算，忽略前端传入的 word_count
        if fields.get("content") is not None:
            content = str(fields["content"])
            updates["content"] = content
            updates["word_count"] = count_words(content)

        if not updates:
            return get_chapter(novel_id, chapter_id)

        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE chapters SET {assignments} WHERE id = ? AND novel_id = ?",
            list(updates.values()) + [chapter_id, novel_id],
        )
        conn.execute(
            "UPDATE novels SET updated_at = ? WHERE id = ?",
            (_now(), novel_id),
        )
    return get_chapter(novel_id, chapter_id)


def delete_chapter(novel_id: str, chapter_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _chapter_row(conn, novel_id, chapter_id)
        # 剧情事件保留，仅解除章节关联
        conn.execute(
            "UPDATE plot_events SET chapter_id = NULL, updated_at = ?"
            " WHERE novel_id = ? AND chapter_id = ?",
            (_now(), novel_id, chapter_id),
        )
        # 人物关系变化历史同样保留，仅解除章节关联
        # （chapter_id 外键也声明了 ON DELETE SET NULL，此处显式更新保证行为一致）
        conn.execute(
            "UPDATE character_relation_events SET chapter_id = NULL"
            " WHERE novel_id = ? AND chapter_id = ?",
            (novel_id, chapter_id),
        )
        conn.execute(
            "DELETE FROM chapters WHERE id = ? AND novel_id = ?",
            (chapter_id, novel_id),
        )
    return {"deleted": True}


def reorder_chapters(novel_id: str, ordered_ids: list[str]) -> list[dict]:
    """按给定顺序重排章节，同时重写 sort_order 与 chapter_number。"""
    _ensure_novel(novel_id)
    ids = [str(item).strip() for item in ordered_ids if str(item).strip()]
    if not ids:
        raise ServiceError(400, "排序列表不能为空")
    if len(set(ids)) != len(ids):
        raise ServiceError(400, "排序列表存在重复章节")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM chapters WHERE novel_id = ?", (novel_id,)
        ).fetchall()
        existing = {row["id"] for row in rows}
        if set(ids) != existing:
            raise ServiceError(400, "排序列表必须包含当前小说的全部章节")

        # 第一阶段写入负数临时序号，避免 UNIQUE(novel_id, chapter_number) 中间冲突
        for index, cid in enumerate(ids):
            conn.execute(
                "UPDATE chapters SET chapter_number = ? WHERE id = ? AND novel_id = ?",
                (-(index + 1), cid, novel_id),
            )
        now = _now()
        for index, cid in enumerate(ids):
            conn.execute(
                "UPDATE chapters"
                "   SET chapter_number = ?, sort_order = ?, updated_at = ?"
                " WHERE id = ? AND novel_id = ?",
                (index + 1, index + 1, now, cid, novel_id),
            )
        conn.execute("UPDATE novels SET updated_at = ? WHERE id = ?", (now, novel_id))
    return list_chapters(novel_id)


def get_stats(novel_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) AS completed,
                   COALESCE(SUM(CASE WHEN status = 'drafting' THEN 1 ELSE 0 END), 0) AS drafting,
                   COALESCE(SUM(CASE WHEN status = 'planned' THEN 1 ELSE 0 END), 0) AS planned,
                   COALESCE(SUM(word_count), 0) AS words
              FROM chapters WHERE novel_id = ?
            """,
            (novel_id,),
        ).fetchone()
    return {
        "chapter_count": int(row["total"]),
        "completed_chapter_count": int(row["completed"]),
        "drafting_chapter_count": int(row["drafting"]),
        "planned_chapter_count": int(row["planned"]),
        "total_word_count": int(row["words"]),
    }


def count_chapters(novel_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM chapters WHERE novel_id = ?", (novel_id,)
        ).fetchone()
    return int(row["n"]) if row else 0


def novel_word_count(novel_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(word_count), 0) AS n FROM chapters WHERE novel_id = ?",
            (novel_id,),
        ).fetchone()
    return int(row["n"]) if row else 0
