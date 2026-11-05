"""世界观设定业务逻辑。

数据隔离：
- 所有分类与条目都以 novel_id 归属到具体小说；
- 任何查询、修改、删除都会同时校验 novel_id，禁止跨小说访问；
- 分类、父级条目均要求属于同一本小说。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import (
    DEFAULT_WORLD_CATEGORIES,
    get_connection,
)
from .errors import ServiceError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_array(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _json_object(raw: str | None) -> dict[str, object]:
    try:
        value = json.loads(raw or "{}")
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _dump_json(value: object, label: str) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ServiceError(400, f"{label}格式不正确") from exc


def _ensure_novel(novel_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")


def _category_row(
    conn: sqlite3.Connection, novel_id: str, category_id: str
) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM world_categories WHERE id = ? AND novel_id = ?",
        (category_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "世界观分类不存在")
    return row


def _entry_row(conn: sqlite3.Connection, novel_id: str, entry_id: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT e.*, c.name AS category_name, p.name AS parent_name
        FROM world_entries e
        JOIN world_categories c ON c.id = e.category_id
        LEFT JOIN world_entries p ON p.id = e.parent_id
        WHERE e.novel_id = ? AND e.id = ?
        """,
        (novel_id, entry_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "世界观设定不存在")
    return row


def _to_category_out(row: sqlite3.Row) -> dict:
    keys = row.keys()
    return {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "name": row["name"],
        "description": row["description"],
        "sort_order": row["sort_order"],
        "entry_count": row["entry_count"] if "entry_count" in keys else 0,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _to_entry_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "category_id": row["category_id"],
        "category_name": row["category_name"],
        "name": row["name"],
        "summary": row["summary"],
        "content": row["content"],
        "tags": _json_array(row["tags"]),
        "attributes": _json_object(row["attributes"]),
        "parent_id": row["parent_id"],
        "parent_name": row["parent_name"],
        "sort_order": row["sort_order"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ----------------------------- 分类 -----------------------------
def list_categories(novel_id: str) -> list[dict]:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM world_entries e WHERE e.category_id = c.id) AS entry_count
            FROM world_categories c
            WHERE c.novel_id = ?
            ORDER BY c.sort_order ASC, c.created_at ASC
            """,
            (novel_id,),
        ).fetchall()
    return [_to_category_out(row) for row in rows]


def get_category(novel_id: str, category_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM world_entries e WHERE e.category_id = c.id) AS entry_count
            FROM world_categories c
            WHERE c.id = ? AND c.novel_id = ?
            """,
            (category_id, novel_id),
        ).fetchone()
    if row is None:
        raise ServiceError(404, "世界观分类不存在")
    return _to_category_out(row)


def create_category(
    novel_id: str, *, name: str, description: str = "", sort_order: int = 0
) -> dict:
    _ensure_novel(novel_id)
    now = _now()
    category_id = uuid4().hex
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO world_categories
                    (id, novel_id, name, description, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (category_id, novel_id, name, description, sort_order, now, now),
            )
    except sqlite3.IntegrityError as exc:
        raise ServiceError(400, "该小说下已存在同名分类") from exc
    return get_category(novel_id, category_id)


def update_category(novel_id: str, category_id: str, fields: dict) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _category_row(conn, novel_id, category_id)
    updates: dict[str, object] = {}
    for key in ("name", "description", "sort_order"):
        value = fields.get(key)
        if value is not None:
            updates[key] = value
    if not updates:
        return get_category(novel_id, category_id)
    updates["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    try:
        with get_connection() as conn:
            conn.execute(
                f"UPDATE world_categories SET {assignments} WHERE id = ? AND novel_id = ?",
                list(updates.values()) + [category_id, novel_id],
            )
    except sqlite3.IntegrityError as exc:
        raise ServiceError(400, "该小说下已存在同名分类") from exc
    return get_category(novel_id, category_id)


def delete_category(novel_id: str, category_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM world_categories WHERE id = ? AND novel_id = ?",
            (category_id, novel_id),
        ).fetchone()
        if row is None:
            raise ServiceError(404, "世界观分类不存在")
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM world_entries WHERE category_id = ? AND novel_id = ?",
            (category_id, novel_id),
        ).fetchone()["n"]
        if count:
            raise ServiceError(
                400,
                f"该分类下仍有 {count} 个设定条目，请先将条目迁移到其他分类后再删除",
            )
        conn.execute(
            "DELETE FROM world_categories WHERE id = ? AND novel_id = ?",
            (category_id, novel_id),
        )
    return {"deleted": True}


def seed_default_categories(novel_id: str) -> None:
    """为新创建的小说初始化通用分类模板（幂等，仅在该小说尚无分类时执行）。"""
    now = _now()
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM novels WHERE id = ?", (novel_id,)
        ).fetchone()
        if exists is None:
            return
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM world_categories WHERE novel_id = ?", (novel_id,)
        ).fetchone()["n"]
        if count:
            return
        for index, name in enumerate(DEFAULT_WORLD_CATEGORIES):
            conn.execute(
                """
                INSERT INTO world_categories
                    (id, novel_id, name, description, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (uuid4().hex, novel_id, name, "", index * 10, now, now),
            )


# ----------------------------- 条目 -----------------------------
def _validate_parent(
    conn: sqlite3.Connection,
    novel_id: str,
    parent_id: str | None,
    entry_id: str | None = None,
) -> None:
    if not parent_id:
        return
    row = conn.execute(
        "SELECT id, parent_id FROM world_entries WHERE id = ? AND novel_id = ?",
        (parent_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "父级设定不存在")
    if entry_id and parent_id == entry_id:
        raise ServiceError(400, "不能将设定设置为自己的父级")

    visited: set[str] = {parent_id}
    current = row["parent_id"]
    depth = 0
    while current:
        if entry_id and current == entry_id:
            raise ServiceError(400, "不能形成循环的父子引用")
        if current in visited:
            raise ServiceError(400, "父子引用存在循环，请重新选择父级")
        visited.add(current)
        depth += 1
        if depth > 100:
            raise ServiceError(400, "设定层级过深，请重新选择父级")
        ancestor = conn.execute(
            "SELECT parent_id FROM world_entries WHERE id = ? AND novel_id = ?",
            (current, novel_id),
        ).fetchone()
        current = ancestor["parent_id"] if ancestor else None


def list_entries(
    novel_id: str,
    *,
    search: str | None = None,
    category_id: str | None = None,
    tag: str | None = None,
    parent_id: str | None = None,
) -> list[dict]:
    _ensure_novel(novel_id)
    sql = """
        SELECT e.*, c.name AS category_name, p.name AS parent_name
        FROM world_entries e
        JOIN world_categories c ON c.id = e.category_id
        LEFT JOIN world_entries p ON p.id = e.parent_id
        WHERE e.novel_id = ?
    """
    params: list[object] = [novel_id]

    if category_id:
        with get_connection() as conn:
            _category_row(conn, novel_id, category_id)
        sql += " AND e.category_id = ?"
        params.append(category_id)
    if parent_id:
        sql += " AND e.parent_id = ?"
        params.append(parent_id)
    if search and search.strip():
        keyword = f"%{search.strip()}%"
        sql += " AND (e.name LIKE ? OR e.summary LIKE ? OR e.content LIKE ?)"
        params.extend([keyword, keyword, keyword])
    sql += " ORDER BY e.sort_order ASC, e.updated_at DESC, e.created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    result = [_to_entry_out(row) for row in rows]
    if tag and tag.strip():
        wanted = tag.strip()
        result = [item for item in result if wanted in item["tags"]]
    return result


def get_entry(novel_id: str, entry_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = _entry_row(conn, novel_id, entry_id)
    return _to_entry_out(row)


def create_entry(novel_id: str, payload: dict) -> dict:
    _ensure_novel(novel_id)
    now = _now()
    entry_id = uuid4().hex
    with get_connection() as conn:
        _category_row(conn, novel_id, payload["category_id"])
        _validate_parent(conn, novel_id, payload.get("parent_id"))
        conn.execute(
            """
            INSERT INTO world_entries
                (id, novel_id, category_id, name, summary, content, tags,
                 attributes, parent_id, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                novel_id,
                payload["category_id"],
                payload["name"],
                payload.get("summary", ""),
                payload.get("content", ""),
                _dump_json(payload.get("tags") or [], "标签"),
                _dump_json(payload.get("attributes") or {}, "自定义属性"),
                payload.get("parent_id"),
                payload.get("sort_order", 0),
                now,
                now,
            ),
        )
    return get_entry(novel_id, entry_id)


def update_entry(novel_id: str, entry_id: str, fields: dict) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _entry_row(conn, novel_id, entry_id)

        updates: dict[str, object] = {}
        for key in ("name", "summary", "content", "sort_order"):
            value = fields.get(key)
            if value is not None:
                updates[key] = value
        if fields.get("category_id") is not None:
            _category_row(conn, novel_id, fields["category_id"])
            updates["category_id"] = fields["category_id"]
        if "parent_id" in fields:
            parent_id = fields["parent_id"]
            _validate_parent(conn, novel_id, parent_id, entry_id)
            updates["parent_id"] = parent_id
        if fields.get("tags") is not None:
            updates["tags"] = _dump_json(fields["tags"], "标签")
        if fields.get("attributes") is not None:
            updates["attributes"] = _dump_json(fields["attributes"], "自定义属性")

        if not updates:
            row = _entry_row(conn, novel_id, entry_id)
            return _to_entry_out(row)

        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE world_entries SET {assignments} WHERE id = ? AND novel_id = ?",
            list(updates.values()) + [entry_id, novel_id],
        )
        row = _entry_row(conn, novel_id, entry_id)
    return _to_entry_out(row)


def delete_entry(novel_id: str, entry_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _entry_row(conn, novel_id, entry_id)
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM world_entries WHERE parent_id = ? AND novel_id = ?",
            (entry_id, novel_id),
        ).fetchone()["n"]
        if count:
            raise ServiceError(
                400,
                f"该设定下存在 {count} 个子设定，请先移动或删除子设定后再删除",
            )
        conn.execute(
            "DELETE FROM world_entries WHERE id = ? AND novel_id = ?",
            (entry_id, novel_id),
        )
    return {"deleted": True}


def count_entries(novel_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM world_entries WHERE novel_id = ?", (novel_id,)
        ).fetchone()
    return int(row["n"]) if row else 0


def get_stats(novel_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM world_entries WHERE novel_id = ?", (novel_id,)
        ).fetchone()["n"]
        category_count = conn.execute(
            "SELECT COUNT(*) AS n FROM world_categories WHERE novel_id = ?", (novel_id,)
        ).fetchone()["n"]
        rows = conn.execute(
            """
            SELECT c.id AS category_id, c.name AS name, COUNT(e.id) AS count
            FROM world_categories c
            LEFT JOIN world_entries e
                ON e.category_id = c.id AND e.novel_id = c.novel_id
            WHERE c.novel_id = ?
            GROUP BY c.id
            ORDER BY c.sort_order ASC, c.created_at ASC
            """,
            (novel_id,),
        ).fetchall()
        relation_total = conn.execute(
            "SELECT COUNT(*) AS n FROM world_relations WHERE novel_id = ?", (novel_id,)
        ).fetchone()["n"]
        relation_types = conn.execute(
            """
            SELECT relation_type, COUNT(*) AS count
            FROM world_relations
            WHERE novel_id = ?
            GROUP BY relation_type
            ORDER BY count DESC, relation_type ASC
            """,
            (novel_id,),
        ).fetchall()
        related_entries = conn.execute(
            """
            SELECT COUNT(*) AS n FROM (
                SELECT source_entry_id AS entry_id
                FROM world_relations WHERE novel_id = ?
                UNION
                SELECT target_entry_id AS entry_id
                FROM world_relations WHERE novel_id = ?
            )
            """,
            (novel_id, novel_id),
        ).fetchone()["n"]
        latest = conn.execute(
            """
            SELECT MAX(updated_at) AS latest FROM (
                SELECT updated_at FROM world_entries WHERE novel_id = ?
                UNION ALL
                SELECT updated_at FROM world_categories WHERE novel_id = ?
                UNION ALL
                SELECT updated_at FROM world_relations WHERE novel_id = ?
            )
            """,
            (novel_id, novel_id, novel_id),
        ).fetchone()["latest"]
    return {
        "total_entries": int(total),
        "category_count": int(category_count),
        "by_category": [
            {
                "category_id": row["category_id"],
                "name": row["name"],
                "count": int(row["count"]),
            }
            for row in rows
        ],
        "total_relations": int(relation_total),
        "relation_type_count": len(relation_types),
        "relation_by_type": [
            {"relation_type": row["relation_type"], "count": int(row["count"])}
            for row in relation_types
        ],
        "related_entry_count": int(related_entries),
        "latest_updated_at": latest,
    }
