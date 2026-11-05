"""小说项目业务逻辑。

数据隔离约定：后续章节、人物、世界观、剧情记忆等表都必须以 novel_id
外键关联 novels.id，并声明 ON DELETE CASCADE，使删除小说时关联数据一并清理。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import (
    DEFAULT_NOVEL_KEY,
    NOVEL_STATUSES,
    get_connection,
)
from . import character_relation_service, character_service, world_service
from .errors import ServiceError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_tags(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _serialize_tags(tags: list[str]) -> str:
    return json.dumps(tags, ensure_ascii=False)


def _default_novel_id() -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (DEFAULT_NOVEL_KEY,)
        ).fetchone()
    return row["value"] if row and row["value"] else None


def _to_out(row: sqlite3.Row, default_id: str | None) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "subtitle": row["subtitle"],
        "description": row["description"],
        "genre": row["genre"],
        "tags": _parse_tags(row["tags"]),
        "status": row["status"],
        "cover_color": row["cover_color"],
        "target_word_count": row["target_word_count"],
        # 章节系统在后续阶段实现，当前字数固定为 0
        "current_word_count": 0,
        "is_default": row["id"] == default_id,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _fetch_row(novel_id: str) -> sqlite3.Row:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")
    return row


def list_novels(search: str | None = None, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM novels"
    clauses: list[str] = []
    params: list[object] = []
    if search and search.strip():
        clauses.append("title LIKE ?")
        params.append(f"%{search.strip()}%")
    if status:
        if status not in NOVEL_STATUSES:
            raise ServiceError(400, "不支持的创作状态")
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY updated_at DESC, created_at DESC"

    default_id = _default_novel_id()
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_to_out(row, default_id) for row in rows]


def get_novel(novel_id: str) -> dict:
    row = _fetch_row(novel_id)
    data = _to_out(row, _default_novel_id())
    data["stats"] = {
        "chapter_count": 0,
        "character_count": character_service.count_characters(novel_id),
        "character_relation_count": character_relation_service.count_relations(novel_id),
        "word_count": 0,
        "world_entry_count": world_service.count_entries(novel_id),
    }
    return data


def get_default_novel() -> dict | None:
    default_id = _default_novel_id()
    if not default_id:
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM novels WHERE id = ?", (default_id,)).fetchone()
    if row is None:
        # 数据不一致时清理失效引用，保证默认小说始终指向真实存在的记录
        _clear_default()
        return None
    return _to_out(row, default_id)


def create_novel(*, title: str, **fields) -> dict:
    now = _now()
    novel_id = uuid4().hex
    payload = {
        "id": novel_id,
        "title": title.strip(),
        "subtitle": fields.get("subtitle", ""),
        "description": fields.get("description", ""),
        "genre": fields.get("genre", ""),
        "tags": _serialize_tags(fields.get("tags") or []),
        "status": fields.get("status", "planning"),
        "cover_color": fields.get("cover_color", ""),
        "target_word_count": fields.get("target_word_count", 100000),
        "created_at": now,
        "updated_at": now,
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO novels
                (id, title, subtitle, description, genre, tags, status,
                 cover_color, target_word_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(payload.values()),
        )
    # 为新小说初始化通用世界观分类模板（幂等）
    world_service.seed_default_categories(novel_id)
    return get_novel(novel_id)


def update_novel(novel_id: str, fields: dict) -> dict:
    _fetch_row(novel_id)

    updates: dict[str, object] = {}
    for key in ("title", "subtitle", "description", "genre", "status", "cover_color",
                "target_word_count"):
        if fields.get(key) is not None:
            updates[key] = fields[key]
    if fields.get("tags") is not None:
        updates["tags"] = _serialize_tags(fields["tags"])

    if not updates:
        return get_novel(novel_id)

    updates["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE novels SET {assignments} WHERE id = ?",
            list(updates.values()) + [novel_id],
        )
    return get_novel(novel_id)


def delete_novel(novel_id: str) -> dict:
    _fetch_row(novel_id)
    default_cleared = False
    with get_connection() as conn:
        # 明确清理该小说的世界观数据：先清理关系，再解除父子引用，最后删除条目与分类。
        # 这些数据表同时声明了 novel_id ON DELETE CASCADE，此处显式清理确保
        # 分类/父级的 RESTRICT 约束不会阻断小说删除。
        conn.execute("DELETE FROM world_relations WHERE novel_id = ?", (novel_id,))
        conn.execute(
            "UPDATE world_entries SET parent_id = NULL WHERE novel_id = ?", (novel_id,)
        )
        conn.execute("DELETE FROM world_entries WHERE novel_id = ?", (novel_id,))
        conn.execute("DELETE FROM world_categories WHERE novel_id = ?", (novel_id,))
        # 人物相关：先清理秘密与状态，再清理人物关系（含其事件历史），最后删除人物
        # character_relation_events 通过 relation_id ON DELETE CASCADE 自动清理
        conn.execute("DELETE FROM character_secrets WHERE character_id IN (SELECT id FROM characters WHERE novel_id = ?)", (novel_id,))
        conn.execute("DELETE FROM character_states WHERE character_id IN (SELECT id FROM characters WHERE novel_id = ?)", (novel_id,))
        conn.execute("DELETE FROM character_relations WHERE novel_id = ?", (novel_id,))
        conn.execute("DELETE FROM characters WHERE novel_id = ?", (novel_id,))
        conn.execute("DELETE FROM novels WHERE id = ?", (novel_id,))
        deleted = conn.execute(
            "DELETE FROM app_settings WHERE key = ? AND value = ?",
            (DEFAULT_NOVEL_KEY, novel_id),
        ).rowcount
        default_cleared = deleted > 0
    return {"deleted": True, "default_cleared": default_cleared}


def set_default_novel(novel_id: str) -> dict:
    row = _fetch_row(novel_id)
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (DEFAULT_NOVEL_KEY, novel_id, now),
        )
    return _to_out(row, novel_id)


def _clear_default() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM app_settings WHERE key = ?", (DEFAULT_NOVEL_KEY,))
