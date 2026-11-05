"""世界观条目关系业务逻辑。

关系是有向的：A → 管辖 → B 与 B → 管辖 → A 是两条独立关系。

数据隔离：
- 关系以 novel_id 归属到具体小说，所有查询/修改/删除都同时校验 novel_id；
- 起点与终点必须是同一本小说内的条目，禁止跨小说建立关系；
- 与 world_entries.parent_id 的树形层级互不替代，二者独立存在。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import get_connection
from .errors import ServiceError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_RELATION_SELECT = """
    SELECT r.*,
           s.name AS source_name,
           s.category_id AS source_category_id,
           sc.name AS source_category_name,
           t.name AS target_name,
           t.category_id AS target_category_id,
           tc.name AS target_category_name
    FROM world_relations r
    JOIN world_entries s ON s.id = r.source_entry_id
    JOIN world_categories sc ON sc.id = s.category_id
    JOIN world_entries t ON t.id = r.target_entry_id
    JOIN world_categories tc ON tc.id = t.category_id
"""


def _ensure_novel(novel_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")


def _entry_brief(
    conn: sqlite3.Connection, novel_id: str, entry_id: str, label: str
) -> sqlite3.Row:
    """校验条目存在且属于当前小说；跨小说一律按不存在处理。"""
    row = conn.execute(
        """
        SELECT e.id, e.name, e.category_id, c.name AS category_name
        FROM world_entries e
        JOIN world_categories c ON c.id = e.category_id
        WHERE e.id = ? AND e.novel_id = ?
        """,
        (entry_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, f"{label}不存在")
    return row


def _relation_row(
    conn: sqlite3.Connection, novel_id: str, relation_id: str
) -> sqlite3.Row:
    row = conn.execute(
        _RELATION_SELECT + " WHERE r.id = ? AND r.novel_id = ?",
        (relation_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "世界观关系不存在")
    return row


def _to_relation_out(row: sqlite3.Row, direction: str | None = None) -> dict:
    data = {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "source_entry_id": row["source_entry_id"],
        "target_entry_id": row["target_entry_id"],
        "relation_type": row["relation_type"],
        "description": row["description"],
        "source": {
            "id": row["source_entry_id"],
            "name": row["source_name"],
            "category_id": row["source_category_id"],
            "category_name": row["source_category_name"],
        },
        "target": {
            "id": row["target_entry_id"],
            "name": row["target_name"],
            "category_id": row["target_category_id"],
            "category_name": row["target_category_name"],
        },
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if direction:
        data["direction"] = direction
    return data


def _duplicate_exists(
    conn: sqlite3.Connection,
    novel_id: str,
    source_entry_id: str,
    target_entry_id: str,
    relation_type: str,
    exclude_id: str | None = None,
) -> bool:
    sql = """
        SELECT id FROM world_relations
        WHERE novel_id = ? AND source_entry_id = ?
          AND target_entry_id = ? AND relation_type = ?
    """
    params: list[object] = [novel_id, source_entry_id, target_entry_id, relation_type]
    if exclude_id:
        sql += " AND id <> ?"
        params.append(exclude_id)
    return conn.execute(sql, params).fetchone() is not None


def list_relations(
    novel_id: str,
    *,
    relation_type: str | None = None,
    source_entry_id: str | None = None,
    target_entry_id: str | None = None,
    search: str | None = None,
) -> list[dict]:
    _ensure_novel(novel_id)
    sql = _RELATION_SELECT + " WHERE r.novel_id = ?"
    params: list[object] = [novel_id]

    if relation_type and relation_type.strip():
        sql += " AND r.relation_type = ?"
        params.append(relation_type.strip())
    if source_entry_id and source_entry_id.strip():
        sql += " AND r.source_entry_id = ?"
        params.append(source_entry_id.strip())
    if target_entry_id and target_entry_id.strip():
        sql += " AND r.target_entry_id = ?"
        params.append(target_entry_id.strip())
    if search and search.strip():
        sql += " AND r.description LIKE ?"
        params.append(f"%{search.strip()}%")

    sql += " ORDER BY r.created_at DESC, r.id DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_to_relation_out(row) for row in rows]


def get_relation(novel_id: str, relation_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = _relation_row(conn, novel_id, relation_id)
    return _to_relation_out(row)


def create_relation(novel_id: str, payload: dict) -> dict:
    _ensure_novel(novel_id)
    source_entry_id = payload["source_entry_id"].strip()
    target_entry_id = payload["target_entry_id"].strip()
    relation_type = (payload.get("relation_type") or "").strip()
    description = (payload.get("description") or "").strip()
    if not relation_type:
        raise ServiceError(400, "关系类型不能为空")
    if source_entry_id == target_entry_id:
        raise ServiceError(400, "起点和终点不能是同一条设定")

    relation_id = uuid4().hex
    now = _now()
    with get_connection() as conn:
        _entry_brief(conn, novel_id, source_entry_id, "起点设定")
        _entry_brief(conn, novel_id, target_entry_id, "终点设定")
        if _duplicate_exists(
            conn, novel_id, source_entry_id, target_entry_id, relation_type
        ):
            raise ServiceError(400, "相同起点、终点与关系类型的关系已存在")
        conn.execute(
            """
            INSERT INTO world_relations
                (id, novel_id, source_entry_id, target_entry_id, relation_type,
                 description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation_id,
                novel_id,
                source_entry_id,
                target_entry_id,
                relation_type,
                description,
                now,
                now,
            ),
        )
    return get_relation(novel_id, relation_id)


def update_relation(novel_id: str, relation_id: str, fields: dict) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = _relation_row(conn, novel_id, relation_id)

        source_entry_id = fields.get("source_entry_id") or row["source_entry_id"]
        target_entry_id = fields.get("target_entry_id") or row["target_entry_id"]
        relation_type = fields.get("relation_type")
        if relation_type is None:
            relation_type = row["relation_type"]
        relation_type = str(relation_type).strip()
        if not relation_type:
            raise ServiceError(400, "关系类型不能为空")
        description = (
            fields["description"] if fields.get("description") is not None
            else row["description"]
        )

        if source_entry_id == target_entry_id:
            raise ServiceError(400, "起点和终点不能是同一条设定")

        _entry_brief(conn, novel_id, source_entry_id, "起点设定")
        _entry_brief(conn, novel_id, target_entry_id, "终点设定")
        if _duplicate_exists(
            conn,
            novel_id,
            source_entry_id,
            target_entry_id,
            relation_type,
            exclude_id=relation_id,
        ):
            raise ServiceError(400, "相同起点、终点与关系类型的关系已存在")

        updates: dict[str, object] = {}
        if source_entry_id != row["source_entry_id"]:
            updates["source_entry_id"] = source_entry_id
        if target_entry_id != row["target_entry_id"]:
            updates["target_entry_id"] = target_entry_id
        if relation_type != row["relation_type"]:
            updates["relation_type"] = relation_type
        if description != row["description"]:
            updates["description"] = description

        if not updates:
            return _to_relation_out(row)

        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE world_relations SET {assignments} WHERE id = ? AND novel_id = ?",
            list(updates.values()) + [relation_id, novel_id],
        )
        row = _relation_row(conn, novel_id, relation_id)
    return _to_relation_out(row)


def delete_relation(novel_id: str, relation_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _relation_row(conn, novel_id, relation_id)
        conn.execute(
            "DELETE FROM world_relations WHERE id = ? AND novel_id = ?",
            (relation_id, novel_id),
        )
    return {"deleted": True}


def list_entry_relations(novel_id: str, entry_id: str) -> dict:
    """返回条目作为起点（outgoing）与终点（incoming）的关系，均限定同一本小说。"""
    _ensure_novel(novel_id)
    with get_connection() as conn:
        entry = conn.execute(
            "SELECT id FROM world_entries WHERE id = ? AND novel_id = ?",
            (entry_id, novel_id),
        ).fetchone()
        if entry is None:
            raise ServiceError(404, "世界观设定不存在")
        outgoing_rows = conn.execute(
            _RELATION_SELECT
            + " WHERE r.novel_id = ? AND r.source_entry_id = ?"
            + " ORDER BY r.created_at DESC, r.id DESC",
            (novel_id, entry_id),
        ).fetchall()
        incoming_rows = conn.execute(
            _RELATION_SELECT
            + " WHERE r.novel_id = ? AND r.target_entry_id = ?"
            + " ORDER BY r.created_at DESC, r.id DESC",
            (novel_id, entry_id),
        ).fetchall()
    return {
        "entry_id": entry_id,
        "outgoing": [_to_relation_out(row, "outgoing") for row in outgoing_rows],
        "incoming": [_to_relation_out(row, "incoming") for row in incoming_rows],
    }
