"""人物档案业务逻辑。

数据隔离：
- 所有人物、当前状态、秘密均以 novel_id 归属到具体小说；
- 任何查询、修改、删除都会同时校验 novel_id，禁止跨小说访问；
- 人物创建时同一事务内自动初始化一条默认状态记录，确保始终有且仅有一条当前状态。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import get_connection
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


def _character_row(conn: sqlite3.Connection, novel_id: str, character_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM characters WHERE id = ? AND novel_id = ?",
        (character_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "人物不存在")
    return row


def _to_state_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "character_id": row["character_id"],
        "life_status": row["life_status"],
        "current_location": row["current_location"],
        "current_faction": row["current_faction"],
        "current_cultivation": row["current_cultivation"],
        "health_status": row["health_status"],
        "emotional_state": row["emotional_state"],
        "current_goal": row["current_goal"],
        "current_status": row["current_status"],
        "attributes": _json_object(row["attributes"]),
        "updated_at": row["updated_at"],
    }


def _to_character_list(row: sqlite3.Row) -> dict:
    state = row["life_status"] if "life_status" in row.keys() else None
    current_location = row["current_location"] if "current_location" in row.keys() else ""
    current_cultivation = (
        row["current_cultivation"] if "current_cultivation" in row.keys() else ""
    )
    return {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "name": row["name"],
        "aliases": _json_array(row["aliases"]),
        "identity": row["identity"],
        "role": row["role"],
        "tags": _json_array(row["tags"]),
        "avatar_color": row["avatar_color"],
        "life_status": state or "alive",
        "current_location": current_location or "",
        "current_cultivation": current_cultivation or "",
        "sort_order": row["sort_order"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _to_character_out(row: sqlite3.Row, state: dict | None) -> dict:
    result = {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "name": row["name"],
        "aliases": _json_array(row["aliases"]),
        "gender": row["gender"],
        "age": row["age"],
        "race": row["race"],
        "identity": row["identity"],
        "role": row["role"],
        "appearance": row["appearance"],
        "personality": row["personality"],
        "background": row["background"],
        "abilities": row["abilities"],
        "cultivation": row["cultivation"],
        "affiliation": row["affiliation"],
        "tags": _json_array(row["tags"]),
        "attributes": _json_object(row["attributes"]),
        "avatar_color": row["avatar_color"],
        "sort_order": row["sort_order"],
        "state": state,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    return result


def _to_secret_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "character_id": row["character_id"],
        "title": row["title"],
        "content": row["content"],
        "secrecy_level": row["secrecy_level"],
        "reveal_status": row["reveal_status"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ----------------------------- 人物档案 -----------------------------

def list_characters(
    novel_id: str,
    *,
    search: str | None = None,
    role: str | None = None,
    tag: str | None = None,
    sort: str | None = None,
) -> list[dict]:
    _ensure_novel(novel_id)
    sql = """
        SELECT c.*, s.life_status, s.current_location, s.current_cultivation
        FROM characters c
        LEFT JOIN character_states s ON s.character_id = c.id
        WHERE c.novel_id = ?
    """
    params: list[object] = [novel_id]

    if role and role.strip():
        sql += " AND c.role = ?"
        params.append(role.strip())
    if search and search.strip():
        keyword = f"%{search.strip()}%"
        sql += (
            " AND (c.name LIKE ? OR c.identity LIKE ?"
            " OR c.background LIKE ? OR c.aliases LIKE ?)"
        )
        params.extend([keyword, keyword, keyword, keyword])

    order = "ORDER BY c.sort_order ASC, c.updated_at DESC, c.created_at DESC"
    if sort == "name":
        order = "ORDER BY c.name COLLATE NOCASE ASC, c.updated_at DESC"
    elif sort == "created_desc":
        order = "ORDER BY c.created_at DESC"
    elif sort == "updated_desc":
        order = "ORDER BY c.updated_at DESC"
    sql += order

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    result = [_to_character_list(row) for row in rows]
    if tag and tag.strip():
        wanted = tag.strip()
        result = [item for item in result if wanted in item["tags"]]
    return result


def get_character(novel_id: str, character_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = _character_row(conn, novel_id, character_id)
        state_row = conn.execute(
            "SELECT * FROM character_states WHERE character_id = ?", (character_id,)
        ).fetchone()
    state = _to_state_out(state_row) if state_row else None
    return _to_character_out(row, state)


def create_character(novel_id: str, payload: dict) -> dict:
    _ensure_novel(novel_id)
    now = _now()
    character_id = uuid4().hex
    state_id = uuid4().hex
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO characters
                (id, novel_id, name, aliases, gender, age, race, identity, role,
                 appearance, personality, background, abilities, cultivation,
                 affiliation, tags, attributes, avatar_color, sort_order,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                novel_id,
                payload["name"],
                _dump_json(payload.get("aliases") or [], "别名"),
                payload.get("gender", ""),
                payload.get("age", ""),
                payload.get("race", ""),
                payload.get("identity", ""),
                payload.get("role", ""),
                payload.get("appearance", ""),
                payload.get("personality", ""),
                payload.get("background", ""),
                payload.get("abilities", ""),
                payload.get("cultivation", ""),
                payload.get("affiliation", ""),
                _dump_json(payload.get("tags") or [], "标签"),
                _dump_json(payload.get("attributes") or {}, "自定义属性"),
                payload.get("avatar_color", ""),
                payload.get("sort_order", 0),
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO character_states
                (id, character_id, life_status, current_location, current_faction,
                 current_cultivation, health_status, emotional_state, current_goal,
                 current_status, attributes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state_id,
                character_id,
                "alive",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "{}",
                now,
            ),
        )
    return get_character(novel_id, character_id)


def update_character(novel_id: str, character_id: str, fields: dict) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _character_row(conn, novel_id, character_id)

        updates: dict[str, object] = {}
        for key in (
            "name", "gender", "age", "race", "identity", "role",
            "appearance", "personality", "background", "abilities",
            "cultivation", "affiliation", "avatar_color", "sort_order",
        ):
            if fields.get(key) is not None:
                updates[key] = fields[key]
        if fields.get("aliases") is not None:
            updates["aliases"] = _dump_json(fields["aliases"], "别名")
        if fields.get("tags") is not None:
            updates["tags"] = _dump_json(fields["tags"], "标签")
        if fields.get("attributes") is not None:
            updates["attributes"] = _dump_json(fields["attributes"], "自定义属性")

        if not updates:
            return get_character(novel_id, character_id)

        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE characters SET {assignments} WHERE id = ? AND novel_id = ?",
            list(updates.values()) + [character_id, novel_id],
        )
    return get_character(novel_id, character_id)


def delete_character(novel_id: str, character_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _character_row(conn, novel_id, character_id)
        # character_states / character_secrets 通过 ON DELETE CASCADE 自动清理
        # character_relation_events 通过 relation_id ON DELETE CASCADE 自动清理
        conn.execute(
            """
            DELETE FROM character_relations
            WHERE novel_id = ? AND (source_character_id = ? OR target_character_id = ?)
            """,
            (novel_id, character_id, character_id),
        )
        conn.execute(
            "DELETE FROM characters WHERE id = ? AND novel_id = ?",
            (character_id, novel_id),
        )
    return {"deleted": True}


def count_characters(novel_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM characters WHERE novel_id = ?", (novel_id,)
        ).fetchone()
    return int(row["n"]) if row else 0


# ----------------------------- 人物当前状态 -----------------------------

def get_state(novel_id: str, character_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _character_row(conn, novel_id, character_id)
        row = conn.execute(
            "SELECT * FROM character_states WHERE character_id = ?", (character_id,)
        ).fetchone()
    if row is None:
        raise ServiceError(404, "人物当前状态不存在")
    return _to_state_out(row)


def update_state(novel_id: str, character_id: str, fields: dict) -> dict:
    _ensure_novel(novel_id)
    now = _now()
    with get_connection() as conn:
        _character_row(conn, novel_id, character_id)

        updates: dict[str, object] = {}
        for key in (
            "life_status", "current_location", "current_faction",
            "current_cultivation", "health_status", "emotional_state",
            "current_goal", "current_status",
        ):
            if fields.get(key) is not None:
                updates[key] = fields[key]
        if fields.get("attributes") is not None:
            updates["attributes"] = _dump_json(fields["attributes"], "状态自定义属性")

        if not updates:
            return get_state(novel_id, character_id)

        updates["updated_at"] = now
        assignments = ", ".join(f"{key} = ?" for key in updates)
        rows = conn.execute(
            f"UPDATE character_states SET {assignments} WHERE character_id = ?",
            list(updates.values()) + [character_id],
        ).rowcount
        if rows == 0:
            # 状态记录缺失时自动初始化一条默认状态，避免人物无当前状态
            conn.execute(
                """
                INSERT INTO character_states
                    (id, character_id, life_status, current_location, current_faction,
                     current_cultivation, health_status, emotional_state, current_goal,
                     current_status, attributes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (uuid4().hex, character_id, "alive", "", "", "", "", "", "", "", "{}", now),
            )
    return get_state(novel_id, character_id)


# ----------------------------- 人物秘密 -----------------------------

def list_secrets(novel_id: str, character_id: str) -> list[dict]:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _character_row(conn, novel_id, character_id)
        rows = conn.execute(
            """
            SELECT * FROM character_secrets
            WHERE character_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (character_id,),
        ).fetchall()
    return [_to_secret_out(row) for row in rows]


def get_secret(novel_id: str, character_id: str, secret_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _character_row(conn, novel_id, character_id)
        row = conn.execute(
            "SELECT * FROM character_secrets WHERE id = ? AND character_id = ?",
            (secret_id, character_id),
        ).fetchone()
    if row is None:
        raise ServiceError(404, "秘密不存在")
    return _to_secret_out(row)


def create_secret(novel_id: str, character_id: str, payload: dict) -> dict:
    _ensure_novel(novel_id)
    now = _now()
    secret_id = uuid4().hex
    with get_connection() as conn:
        _character_row(conn, novel_id, character_id)
        conn.execute(
            """
            INSERT INTO character_secrets
                (id, character_id, title, content, secrecy_level, reveal_status,
                 notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                secret_id,
                character_id,
                payload["title"],
                payload.get("content", ""),
                payload.get("secrecy_level", "restricted"),
                payload.get("reveal_status", "unrevealed"),
                payload.get("notes", ""),
                now,
                now,
            ),
        )
    return get_secret(novel_id, character_id, secret_id)


def update_secret(
    novel_id: str, character_id: str, secret_id: str, fields: dict
) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _character_row(conn, novel_id, character_id)
        secret = conn.execute(
            "SELECT id FROM character_secrets WHERE id = ? AND character_id = ?",
            (secret_id, character_id),
        ).fetchone()
        if secret is None:
            raise ServiceError(404, "秘密不存在")

        updates: dict[str, object] = {}
        for key in ("title", "content", "secrecy_level", "reveal_status", "notes"):
            if fields.get(key) is not None:
                updates[key] = fields[key]
        if not updates:
            return get_secret(novel_id, character_id, secret_id)

        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE character_secrets SET {assignments} WHERE id = ? AND character_id = ?",
            list(updates.values()) + [secret_id, character_id],
        )
    return get_secret(novel_id, character_id, secret_id)


def delete_secret(novel_id: str, character_id: str, secret_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _character_row(conn, novel_id, character_id)
        rows = conn.execute(
            "DELETE FROM character_secrets WHERE id = ? AND character_id = ?",
            (secret_id, character_id),
        ).rowcount
        if rows == 0:
            raise ServiceError(404, "秘密不存在")
    return {"deleted": True}
