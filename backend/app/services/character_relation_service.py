"""人物关系业务逻辑。

设计要点：
1. 关系有方向：A→B 与 B→A 独立存储，双向快捷创建两次 INSERT + 两条 created 事件。
2. 软终止：结束关系把 status 置为 'ended' + end_time 非空，不物理删除。
3. 活跃关系查重：同 novel + source + target + type 且 status='active' 时不允许重复创建；
   已结束关系允许同方向同类型重新建立（新建一条新 relation，旧 relation 保持历史）。
4. 历史事件事务化：每次 relation 写操作都在同一个 get_connection() 事务内同时写 event；
   事件表原则上只提供查询接口，不暴露普通写接口。
5. 级联：删人物时显式 DELETE character_relations WHERE source=? OR target=?；
   事件表通过 relation_id FK ON DELETE CASCADE 自动清理，不会出现 relation 删了但 event 残留。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import get_connection
from .errors import ServiceError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dump_json(value: object, label: str) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ServiceError(400, f"{label}格式不正确") from exc


def _load_json(raw: str | None, default: object = None) -> object:
    if default is None:
        default = {}
    try:
        value = json.loads(raw or "")
    except (ValueError, TypeError):
        return default
    return value


def _ensure_novel(novel_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")


def _character_brief(
    conn: sqlite3.Connection, novel_id: str, character_id: str, label: str
) -> sqlite3.Row:
    row = conn.execute(
        "SELECT id, name FROM characters WHERE id = ? AND novel_id = ?",
        (character_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, f"{label}不存在")
    return row


def _relation_row(
    conn: sqlite3.Connection, novel_id: str, relation_id: str
) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT r.*, s.name AS source_name, t.name AS target_name
        FROM character_relations r
        JOIN characters s ON s.id = r.source_character_id
        JOIN characters t ON t.id = r.target_character_id
        WHERE r.id = ? AND r.novel_id = ?
        """,
        (relation_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "关系不存在")
    return row


def _to_relation_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "source_character_id": row["source_character_id"],
        "target_character_id": row["target_character_id"],
        "source_name": row["source_name"],
        "target_name": row["target_name"],
        "relation_type": row["relation_type"],
        "status": row["status"],
        "description": row["description"],
        "strength": row["strength"],
        "attributes": _load_json(row["attributes"]),
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "sort_order": row["sort_order"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _relation_snapshot(conn: sqlite3.Connection, relation_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM character_relations WHERE id = ?", (relation_id,)
    ).fetchone()
    if row is None:
        return None
    return {
        "relation_type": row["relation_type"],
        "status": row["status"],
        "description": row["description"],
        "strength": row["strength"],
        "attributes": _load_json(row["attributes"]),
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "updated_at": row["updated_at"],
    }


def _next_sequence(conn: sqlite3.Connection, relation_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(sequence), 0) + 1 AS n FROM character_relation_events WHERE relation_id = ?",
        (relation_id,),
    ).fetchone()
    return int(row["n"]) if row else 1


def _insert_event(
    conn: sqlite3.Connection,
    *,
    novel_id: str,
    relation_id: str,
    event_type: str,
    title: str = "",
    description: str = "",
    previous_data: dict | None = None,
    new_data: dict | None = None,
    story_time: str | None = None,
    chapter_id: str | None = None,
    created_at: str | None = None,
) -> None:
    now = created_at or _now()
    seq = _next_sequence(conn, relation_id)
    conn.execute(
        """
        INSERT INTO character_relation_events
            (id, novel_id, relation_id, event_type, title, description,
             previous_data, new_data, story_time, chapter_id, sequence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid4().hex,
            novel_id,
            relation_id,
            event_type,
            title,
            description,
            _dump_json(previous_data or {}, "事件 previous_data"),
            _dump_json(new_data or {}, "事件 new_data"),
            story_time,
            chapter_id,
            seq,
            now,
        ),
    )


def _validate_chapter(
    conn: sqlite3.Connection, novel_id: str, chapter_id: str | None
) -> None:
    """章节可选择性关联；一旦提供就必须属于当前小说，否则 404。"""
    if not chapter_id:
        return
    row = conn.execute(
        "SELECT id FROM chapters WHERE id = ? AND novel_id = ?",
        (chapter_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "章节不存在")


def _check_active_duplicate(
    conn: sqlite3.Connection,
    novel_id: str,
    source_id: str,
    target_id: str,
    relation_type: str,
) -> None:
    row = conn.execute(
        """
        SELECT id FROM character_relations
        WHERE novel_id = ? AND source_character_id = ?
          AND target_character_id = ? AND relation_type = ? AND status = 'active'
        LIMIT 1
        """,
        (novel_id, source_id, target_id, relation_type),
    ).fetchone()
    if row is not None:
        raise ServiceError(400, "相同方向、相同类型的有效关系已存在，不能重复创建")


def _constraint_error(exc: sqlite3.IntegrityError) -> ServiceError:
    """把数据库约束冲突翻译为 400。

    服务层预检是"先查后写"，并发请求可能同时通过预检；此时由
    uq_char_relations_active 部分唯一索引与复合外键在数据库层兜底，
    这里负责把兜底产生的 IntegrityError 转成业务错误而不是 500。
    """
    text = str(exc)
    if "uq_char_relations_active" in text or "unique constraint failed" in text.lower():
        return ServiceError(400, "相同方向、相同类型的有效关系已存在，不能重复创建")
    if "foreign key" in text.lower():
        return ServiceError(400, "关系两端人物不存在或不属于当前小说")
    return ServiceError(400, "关系数据违反数据库约束")


@contextmanager
def _relation_txn():
    """关系写事务：数据库约束冲突统一翻译为 400，其余异常原样透传。"""
    try:
        with get_connection() as conn:
            yield conn
    except sqlite3.IntegrityError as exc:
        raise _constraint_error(exc) from exc


def _finalize(
    conn: sqlite3.Connection, novel_id: str, relation_id: str
) -> dict:
    row = _relation_row(conn, novel_id, relation_id)
    return _to_relation_out(row)


# ----------------------------- 对外接口 -----------------------------

def list_relations(
    novel_id: str,
    *,
    source_character_id: str | None = None,
    target_character_id: str | None = None,
    relation_type: str | None = None,
    status: str | None = None,
    only_active: bool = False,
    search: str | None = None,
) -> list[dict]:
    _ensure_novel(novel_id)
    sql = """
        SELECT r.*, s.name AS source_name, t.name AS target_name
        FROM character_relations r
        JOIN characters s ON s.id = r.source_character_id
        JOIN characters t ON t.id = r.target_character_id
        WHERE r.novel_id = ?
    """
    params: list[object] = [novel_id]

    if source_character_id:
        sql += " AND r.source_character_id = ?"
        params.append(source_character_id)
    if target_character_id:
        sql += " AND r.target_character_id = ?"
        params.append(target_character_id)
    if relation_type and relation_type.strip():
        sql += " AND r.relation_type = ?"
        params.append(relation_type.strip())
    if status and status.strip():
        sql += " AND r.status = ?"
        params.append(status.strip())
    elif only_active:
        sql += " AND r.status = 'active'"
    if search and search.strip():
        keyword = f"%{search.strip()}%"
        sql += (
            " AND (s.name LIKE ? OR t.name LIKE ?"
            " OR r.relation_type LIKE ? OR r.description LIKE ?)"
        )
        params.extend([keyword, keyword, keyword, keyword])

    sql += (
        " ORDER BY CASE r.status WHEN 'active' THEN 0 ELSE 1 END, "
        " r.sort_order ASC, r.updated_at DESC, r.created_at DESC"
    )

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_to_relation_out(row) for row in rows]


def get_relation(novel_id: str, relation_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        return _finalize(conn, novel_id, relation_id)


def _create_relation_in_conn(
    conn: sqlite3.Connection, novel_id: str, payload: dict, now: str
) -> str:
    """在已有事务连接内创建关系并写入 created 历史事件，返回 relation_id。

    供 create_relation 与 P4.1.3 记忆提案应用共用；业务校验失败抛 ServiceError，
    数据库约束冲突（并发重复等）由调用方所在事务统一翻译/回滚。
    """
    source_id = payload["source_character_id"]
    target_id = payload["target_character_id"]
    relation_type = payload["relation_type"]

    if source_id == target_id:
        raise ServiceError(400, "人物不能与自己建立关系")

    # 两端都必须属于当前小说
    _character_brief(conn, novel_id, source_id, "发起人物")
    _character_brief(conn, novel_id, target_id, "目标人物")
    _validate_chapter(conn, novel_id, payload.get("chapter_id"))
    _check_active_duplicate(conn, novel_id, source_id, target_id, relation_type)

    relation_id = uuid4().hex
    conn.execute(
        """
        INSERT INTO character_relations
            (id, novel_id, source_character_id, target_character_id,
             relation_type, status, description, strength, attributes,
             start_time, end_time, sort_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            relation_id,
            novel_id,
            source_id,
            target_id,
            relation_type,
            "active",
            payload.get("description", ""),
            payload.get("strength"),
            _dump_json(payload.get("attributes") or {}, "自定义属性"),
            payload.get("start_time"),
            None,
            now,
            now,
        ),
    )
    new_snapshot = _relation_snapshot(conn, relation_id)
    _insert_event(
        conn,
        novel_id=novel_id,
        relation_id=relation_id,
        event_type="created",
        title=f"建立{relation_type}关系",
        description=payload.get("description", "") or "",
        new_data=new_snapshot,
        story_time=payload.get("story_time"),
        chapter_id=payload.get("chapter_id"),
    )
    return relation_id


def create_relation(novel_id: str, payload: dict) -> dict:
    _ensure_novel(novel_id)
    now = _now()
    with _relation_txn() as conn:
        relation_id = _create_relation_in_conn(conn, novel_id, payload, now)
    return get_relation(novel_id, relation_id)


def create_bidirectional(novel_id: str, payload: dict) -> tuple[dict, dict]:
    """快捷创建双向：两次 create_relation，不人为合为一条。"""
    first = create_relation(novel_id, payload)
    second_payload = dict(payload)
    second_payload["source_character_id"] = payload["target_character_id"]
    second_payload["target_character_id"] = payload["source_character_id"]
    second = create_relation(novel_id, second_payload)
    return first, second


def _update_relation_in_conn(
    conn: sqlite3.Connection,
    novel_id: str,
    relation_id: str,
    fields: dict,
    event_info: dict | None = None,
) -> None:
    """在已有事务连接内更新关系并写入 updated 历史事件。

    供 update_relation 与 P4.1.3 记忆提案应用共用；无实际变更时不写事件。
    """
    before = _relation_snapshot(conn, relation_id)
    if before is None:
        raise ServiceError(404, "关系不存在")

    updates: dict[str, object] = {}
    for key in ("relation_type", "description", "start_time"):
        if fields.get(key) is not None:
            updates[key] = fields[key]
    if "strength" in fields:
        updates["strength"] = fields.get("strength")
    if fields.get("attributes") is not None:
        updates["attributes"] = _dump_json(fields["attributes"], "自定义属性")

    # 即使本次只提交 chapter_id，也要先校验章节归属再返回
    if fields.get("chapter_id") is not None:
        _validate_chapter(conn, novel_id, fields["chapter_id"])

    if not updates:
        return

    # 如果修改 relation_type，需要检查新类型是否与其他活跃关系冲突
    if "relation_type" in updates:
        updated = updates["relation_type"]
        existing = conn.execute(
            """
            SELECT id FROM character_relations
            WHERE novel_id = ? AND source_character_id = (
                SELECT source_character_id FROM character_relations WHERE id = ?
            ) AND target_character_id = (
                SELECT target_character_id FROM character_relations WHERE id = ?
            ) AND relation_type = ? AND status = 'active' AND id != ?
            LIMIT 1
            """,
            (
                novel_id,
                relation_id,
                relation_id,
                updated,
                relation_id,
            ),
        ).fetchone()
        if existing is not None:
            raise ServiceError(400, "相同方向、相同类型的有效关系已存在")

    updates["updated_at"] = _now()
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE character_relations SET {assignments} WHERE id = ? AND novel_id = ?",
        list(updates.values()) + [relation_id, novel_id],
    )

    after = _relation_snapshot(conn, relation_id)
    info = dict(event_info or {})
    if fields.get("chapter_id") is not None:
        info["chapter_id"] = fields["chapter_id"]
    _insert_event(
        conn,
        novel_id=novel_id,
        relation_id=relation_id,
        event_type="updated",
        title=info.get("title") or "关系发生变化",
        description=info.get("description") or "",
        previous_data=before,
        new_data=after,
        story_time=info.get("story_time"),
        chapter_id=info.get("chapter_id"),
    )


def update_relation(
    novel_id: str, relation_id: str, fields: dict, *, event_info: dict | None = None
) -> dict:
    _ensure_novel(novel_id)
    with _relation_txn() as conn:
        _update_relation_in_conn(conn, novel_id, relation_id, fields, event_info)
    return get_relation(novel_id, relation_id)


def _end_relation_in_conn(
    conn: sqlite3.Connection,
    novel_id: str,
    relation_id: str,
    *,
    event_info: dict | None = None,
    now: str,
) -> None:
    """在已有事务连接内软终止关系并写入 ended 历史事件。

    供 end_relation 与 P4.1.3 记忆提案应用共用。
    """
    before_row = _relation_row(conn, novel_id, relation_id)
    before = _relation_snapshot(conn, relation_id)
    if before_row["status"] == "ended":
        raise ServiceError(400, "关系已经结束")

    conn.execute(
        """
        UPDATE character_relations
           SET status = 'ended', end_time = ?, updated_at = ?
         WHERE id = ? AND novel_id = ?
        """,
        (now, now, relation_id, novel_id),
    )

    after = _relation_snapshot(conn, relation_id)
    info = dict(event_info or {})
    _validate_chapter(conn, novel_id, info.get("chapter_id"))
    _insert_event(
        conn,
        novel_id=novel_id,
        relation_id=relation_id,
        event_type="ended",
        title=info.get("title") or f"关系结束",
        description=info.get("description") or "",
        previous_data=before,
        new_data=after,
        story_time=info.get("story_time"),
        chapter_id=info.get("chapter_id"),
    )


def end_relation(
    novel_id: str, relation_id: str, *, event_info: dict | None = None
) -> dict:
    _ensure_novel(novel_id)
    now = _now()
    with get_connection() as conn:
        _end_relation_in_conn(conn, novel_id, relation_id, event_info=event_info, now=now)
    return get_relation(novel_id, relation_id)


def restore_relation(
    novel_id: str, relation_id: str, *, event_info: dict | None = None
) -> dict:
    _ensure_novel(novel_id)
    now = _now()
    with _relation_txn() as conn:
        before_row = _relation_row(conn, novel_id, relation_id)
        before = _relation_snapshot(conn, relation_id)
        if before_row["status"] == "active":
            raise ServiceError(400, "关系当前已经有效")

        source_id = before_row["source_character_id"]
        target_id = before_row["target_character_id"]
        relation_type = before_row["relation_type"]

        # 复开前先检查当前活跃关系里是否已有同方向同类型
        dup = conn.execute(
            """
            SELECT id FROM character_relations
            WHERE novel_id = ? AND source_character_id = ?
              AND target_character_id = ? AND relation_type = ?
              AND status = 'active' AND id != ?
            LIMIT 1
            """,
            (novel_id, source_id, target_id, relation_type, relation_id),
        ).fetchone()
        if dup is not None:
            raise ServiceError(
                400,
                "同方向同类型的活跃关系已存在，不能恢复这条已结束关系",
            )

        conn.execute(
            """
            UPDATE character_relations
               SET status = 'active', end_time = NULL, updated_at = ?
             WHERE id = ? AND novel_id = ?
            """,
            (now, relation_id, novel_id),
        )

        after = _relation_snapshot(conn, relation_id)
        info = dict(event_info or {})
        _validate_chapter(conn, novel_id, info.get("chapter_id"))
        _insert_event(
            conn,
            novel_id=novel_id,
            relation_id=relation_id,
            event_type="restored",
            title=info.get("title") or f"关系恢复",
            description=info.get("description") or "",
            previous_data=before,
            new_data=after,
            story_time=info.get("story_time"),
            chapter_id=info.get("chapter_id"),
        )
    return get_relation(novel_id, relation_id)


def list_events(novel_id: str, relation_id: str) -> list[dict]:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        # 先确认关系属于这本小说
        _relation_row(conn, novel_id, relation_id)
        rows = conn.execute(
            """
            SELECT e.*, c.title AS chapter_title,
                   c.chapter_number AS chapter_number
              FROM character_relation_events e
              LEFT JOIN chapters c
                ON c.id = e.chapter_id AND c.novel_id = e.novel_id
             WHERE e.relation_id = ?
             ORDER BY e.sequence ASC, e.id ASC
            """,
            (relation_id,),
        ).fetchall()
    return [_to_event_out(r) for r in rows]


def _to_event_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "relation_id": row["relation_id"],
        "event_type": row["event_type"],
        "title": row["title"],
        "description": row["description"],
        "previous_data": _load_json(row["previous_data"]),
        "new_data": _load_json(row["new_data"]),
        "story_time": row["story_time"],
        "chapter_id": row["chapter_id"],
        "chapter_title": row["chapter_title"],
        "chapter_number": row["chapter_number"],
        "sequence": row["sequence"],
        "created_at": row["created_at"],
    }


def list_relation_events_by_chapter(novel_id: str, chapter_id: str) -> list[dict]:
    """章节关联的人物关系变化历史（关系事实，不是剧情事件）。"""
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM chapters WHERE id = ? AND novel_id = ?",
            (chapter_id, novel_id),
        ).fetchone()
        if row is None:
            raise ServiceError(404, "章节不存在")
        rows = conn.execute(
            """
            SELECT e.*, c.title AS chapter_title,
                   c.chapter_number AS chapter_number,
                   s.name AS source_name, t.name AS target_name
              FROM character_relation_events e
              JOIN character_relations r ON r.id = e.relation_id
              JOIN characters s ON s.id = r.source_character_id
              JOIN characters t ON t.id = r.target_character_id
              LEFT JOIN chapters c
                ON c.id = e.chapter_id AND c.novel_id = e.novel_id
             WHERE e.novel_id = ? AND e.chapter_id = ?
             ORDER BY e.sequence ASC, e.created_at ASC, e.id ASC
            """,
            (novel_id, chapter_id),
        ).fetchall()
    result = []
    for r in rows:
        item = _to_event_out(r)
        item["source_name"] = r["source_name"]
        item["target_name"] = r["target_name"]
        result.append(item)
    return result


def list_character_relations(
    novel_id: str, character_id: str, *, include_ended: bool = True
) -> dict:
    """人物的出向、入向关系。"""
    _ensure_novel(novel_id)
    with get_connection() as conn:
        _character_brief(conn, novel_id, character_id, "人物")
        sql = """
            SELECT r.*, s.name AS source_name, t.name AS target_name
            FROM character_relations r
            JOIN characters s ON s.id = r.source_character_id
            JOIN characters t ON t.id = r.target_character_id
            WHERE r.novel_id = ? AND (r.source_character_id = ? OR r.target_character_id = ?)
        """
        params: list[object] = [novel_id, character_id, character_id]
        if not include_ended:
            sql += " AND r.status = 'active'"
        sql += (
            " ORDER BY CASE r.status WHEN 'active' THEN 0 ELSE 1 END, "
            " r.updated_at DESC"
        )
        rows = conn.execute(sql, params).fetchall()

    outgoing: list[dict] = []
    incoming: list[dict] = []
    for row in rows:
        relation = _to_relation_out(row)
        if row["source_character_id"] == character_id:
            outgoing.append({"relation": relation, "direction": "outgoing"})
        else:
            incoming.append({"relation": relation, "direction": "incoming"})
    return {"character_id": character_id, "outgoing": outgoing, "incoming": incoming}


def count_relations(novel_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM character_relations WHERE novel_id = ?",
            (novel_id,),
        ).fetchone()
    return int(row["n"]) if row else 0
