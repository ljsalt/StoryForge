"""剧情事件业务逻辑。

设计要点：
1. plot_events 记录「故事事实」，与「人物关系变化历史」（character_relation_events）
   是两类数据，只通过 chapter_id 共享章节，不做自动联动。
2. 事件可以暂不关联章节；删除章节时事件保留，chapter_id 置空。
3. location_id 关联世界观条目，删除条目时由外键置空；location_name 保存地点名称快照，
   没有对应世界观条目时允许直接手填。
4. story_time 是故事世界内时间，created_at 是系统记录时间，二者严格区分，
   永远不把创建时间当作故事时间。
5. 参与者通过 plot_event_characters 关联，复合外键保证事件与人物同属一本小说。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import PLOT_EVENT_IMPORTANCE_LEVELS, get_connection
from .errors import ServiceError

_TABLE_MISSING_HINT = "剧情事件表尚未初始化，请重启后端"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _event_txn():
    """事件写事务：数据库约束冲突统一翻译为 400，其余异常原样透传。"""
    try:
        with get_connection() as conn:
            yield conn
    except sqlite3.IntegrityError as exc:
        text = str(exc).lower()
        if "plot_event_characters" in text or "unique constraint" in text:
            raise ServiceError(400, "同一事件中同一人物不能重复关联") from exc
        if "foreign key" in text:
            raise ServiceError(400, "关联的章节、人物或地点不属于当前小说") from exc
        raise ServiceError(400, "剧情事件数据违反数据库约束") from exc


def _ensure_novel(novel_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")


def _event_row(
    conn: sqlite3.Connection, novel_id: str, event_id: str
) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT e.*, c.title AS chapter_title, c.chapter_number AS chapter_number
          FROM plot_events e
          LEFT JOIN chapters c ON c.id = e.chapter_id AND c.novel_id = e.novel_id
         WHERE e.id = ? AND e.novel_id = ?
        """,
        (event_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "剧情事件不存在")
    return row


def _participants_for(
    conn: sqlite3.Connection, novel_id: str, event_ids: list[str]
) -> dict[str, list[dict]]:
    if not event_ids:
        return {}
    placeholders = ", ".join("?" for _ in event_ids)
    rows = conn.execute(
        f"""
        SELECT p.id, p.event_id, p.character_id, p.participant_role, p.description,
               ch.name AS character_name
          FROM plot_event_characters p
          JOIN characters ch ON ch.id = p.character_id
         WHERE p.novel_id = ? AND p.event_id IN ({placeholders})
         ORDER BY p.created_at ASC, p.id ASC
        """,
        [novel_id] + event_ids,
    ).fetchall()
    grouped: dict[str, list[dict]] = {event_id: [] for event_id in event_ids}
    for row in rows:
        grouped[row["event_id"]].append(
            {
                "id": row["id"],
                "character_id": row["character_id"],
                "character_name": row["character_name"],
                "participant_role": row["participant_role"],
                "description": row["description"],
            }
        )
    return grouped


def _to_out(row: sqlite3.Row, participants: list[dict]) -> dict:
    return {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "chapter_id": row["chapter_id"],
        "chapter_title": row["chapter_title"],
        "chapter_number": row["chapter_number"],
        "title": row["title"],
        "description": row["description"],
        "event_type": row["event_type"],
        "story_time": row["story_time"],
        "location_id": row["location_id"],
        "location_name": row["location_name"],
        "importance": row["importance"],
        "sequence": row["sequence"],
        "participants": participants,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _validate_chapter(
    conn: sqlite3.Connection, novel_id: str, chapter_id: str | None
) -> None:
    if not chapter_id:
        return
    row = conn.execute(
        "SELECT id FROM chapters WHERE id = ? AND novel_id = ?",
        (chapter_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "章节不存在")


def _location_snapshot(
    conn: sqlite3.Connection, novel_id: str, location_id: str | None
) -> str | None:
    """校验地点条目归属并返回名称快照；location_id 为空时返回 None。"""
    if not location_id:
        return None
    row = conn.execute(
        "SELECT name FROM world_entries WHERE id = ? AND novel_id = ?",
        (location_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "世界观地点不存在")
    return row["name"]


def _validate_participants(
    conn: sqlite3.Connection, novel_id: str, participants: list[dict]
) -> list[sqlite3.Row]:
    if len(participants) > 50:
        raise ServiceError(400, "参与人物最多 50 位")
    ids: list[str] = []
    for item in participants:
        character_id = str(item["character_id"]).strip()
        if not character_id:
            raise ServiceError(400, "参与人物不能为空")
        if character_id in ids:
            raise ServiceError(400, "同一事件中同一人物不能重复关联")
        ids.append(character_id)
    if not ids:
        return []
    placeholders = ", ".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT id, name FROM characters WHERE novel_id = ? AND id IN ({placeholders})",
        [novel_id] + ids,
    ).fetchall()
    found = {row["id"] for row in rows}
    missing = [cid for cid in ids if cid not in found]
    if missing:
        raise ServiceError(404, "参与人物不存在或不属于当前小说")
    return rows


def _check_importance(value: str) -> None:
    if value not in PLOT_EVENT_IMPORTANCE_LEVELS:
        raise ServiceError(400, "不支持的重要程度")


def list_events(
    novel_id: str,
    *,
    chapter_id: str | None = None,
    character_id: str | None = None,
    event_type: str | None = None,
    importance: str | None = None,
    search: str | None = None,
    has_story_time: bool | None = None,
) -> list[dict]:
    _ensure_novel(novel_id)
    if importance and importance.strip():
        _check_importance(importance.strip())

    sql = [
        "SELECT e.*, c.title AS chapter_title, c.chapter_number AS chapter_number",
        "  FROM plot_events e",
        "  LEFT JOIN chapters c ON c.id = e.chapter_id AND c.novel_id = e.novel_id",
    ]
    params: list[object] = []
    if character_id and character_id.strip():
        sql.append(
            "  JOIN plot_event_characters p"
            "    ON p.event_id = e.id AND p.novel_id = e.novel_id"
        )
    sql.append(" WHERE e.novel_id = ?")
    params.append(novel_id)
    if character_id and character_id.strip():
        # 顺序与 SQL 占位符一致：先 novel_id，再 character_id
        sql.append(" AND p.character_id = ?")
        params.append(character_id.strip())
    if chapter_id and chapter_id.strip():
        sql.append(" AND e.chapter_id = ?")
        params.append(chapter_id.strip())
    if event_type and event_type.strip():
        sql.append(" AND e.event_type = ?")
        params.append(event_type.strip())
    if importance and importance.strip():
        sql.append(" AND e.importance = ?")
        params.append(importance.strip())
    if search and search.strip():
        keyword = f"%{search.strip()}%"
        sql.append(" AND (e.title LIKE ? OR e.description LIKE ? OR e.event_type LIKE ?)")
        params.extend([keyword, keyword, keyword])
    if has_story_time is True:
        sql.append(" AND e.story_time IS NOT NULL AND e.story_time != ''")
    elif has_story_time is False:
        sql.append(" AND (e.story_time IS NULL OR e.story_time = '')")
    sql.append(" ORDER BY e.sequence ASC, e.created_at ASC, e.id ASC")

    with get_connection() as conn:
        rows = conn.execute("\n".join(sql), params).fetchall()
        grouped = _participants_for(conn, novel_id, [row["id"] for row in rows])
    return [_to_out(row, grouped.get(row["id"], [])) for row in rows]


def get_event(novel_id: str, event_id: str) -> dict:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = _event_row(conn, novel_id, event_id)
        grouped = _participants_for(conn, novel_id, [event_id])
    return _to_out(row, grouped.get(event_id, []))


def create_event(novel_id: str, payload: dict) -> dict:
    _ensure_novel(novel_id)
    importance = payload.get("importance") or "normal"
    _check_importance(importance)
    now = _now()
    event_id = uuid4().hex
    participants = payload.get("participants") or []

    with _event_txn() as conn:
        _validate_chapter(conn, novel_id, payload.get("chapter_id"))
        location_name = payload.get("location_name") or ""
        snapshot = _location_snapshot(conn, novel_id, payload.get("location_id"))
        if snapshot and not location_name:
            location_name = snapshot
        character_rows = _validate_participants(conn, novel_id, participants)

        conn.execute(
            """
            INSERT INTO plot_events
                (id, novel_id, chapter_id, title, description, event_type, story_time,
                 location_id, location_name, importance, sequence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                novel_id,
                payload.get("chapter_id"),
                payload["title"],
                payload.get("description") or "",
                payload.get("event_type") or "",
                (payload.get("story_time") or "").strip() or None,
                payload.get("location_id"),
                location_name,
                importance,
                int(payload.get("sequence") or 0),
                now,
                now,
            ),
        )

        for item in participants:
            conn.execute(
                """
                INSERT INTO plot_event_characters
                    (id, novel_id, event_id, character_id, participant_role,
                     description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    novel_id,
                    event_id,
                    item["character_id"],
                    item.get("participant_role") or "",
                    item.get("description") or "",
                    now,
                ),
            )
    return get_event(novel_id, event_id)


def update_event(novel_id: str, event_id: str, fields: dict) -> dict:
    _ensure_novel(novel_id)
    if fields.get("importance") is not None:
        _check_importance(str(fields["importance"]))

    with _event_txn() as conn:
        _event_row(conn, novel_id, event_id)

        updates: dict[str, object] = {}
        for key in (
            "title",
            "description",
            "event_type",
            "importance",
            "sequence",
        ):
            if fields.get(key) is not None:
                updates[key] = fields[key]

        if fields.get("story_time") is not None:
            value = str(fields["story_time"]).strip()
            updates["story_time"] = value or None

        if fields.get("chapter_id") is not None:
            chapter_id = fields["chapter_id"] or None
            _validate_chapter(conn, novel_id, chapter_id)
            updates["chapter_id"] = chapter_id

        if fields.get("location_id") is not None:
            location_id = fields["location_id"] or None
            snapshot = _location_snapshot(conn, novel_id, location_id)
            updates["location_id"] = location_id
            if snapshot and fields.get("location_name") is None:
                # 地点变更时同步刷新名称快照
                updates["location_name"] = snapshot

        if fields.get("location_name") is not None:
            updates["location_name"] = fields["location_name"] or ""

        if updates:
            updates["updated_at"] = _now()
            assignments = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE plot_events SET {assignments} WHERE id = ? AND novel_id = ?",
                list(updates.values()) + [event_id, novel_id],
            )

        if fields.get("participants") is not None:
            participants = fields["participants"] or []
            _validate_participants(conn, novel_id, participants)
            conn.execute(
                "DELETE FROM plot_event_characters WHERE event_id = ? AND novel_id = ?",
                (event_id, novel_id),
            )
            now = _now()
            for item in participants:
                conn.execute(
                    """
                    INSERT INTO plot_event_characters
                        (id, novel_id, event_id, character_id, participant_role,
                         description, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid4().hex,
                        novel_id,
                        event_id,
                        item["character_id"],
                        item.get("participant_role") or "",
                        item.get("description") or "",
                        now,
                    ),
                )
    return get_event(novel_id, event_id)


def delete_event(novel_id: str, event_id: str) -> dict:
    _ensure_novel(novel_id)
    with _event_txn() as conn:
        _event_row(conn, novel_id, event_id)
        # 仅清理参与人物关联，不删除人物档案或章节
        conn.execute(
            "DELETE FROM plot_event_characters WHERE event_id = ? AND novel_id = ?",
            (event_id, novel_id),
        )
        conn.execute(
            "DELETE FROM plot_events WHERE id = ? AND novel_id = ?",
            (event_id, novel_id),
        )
    return {"deleted": True}


def timeline(novel_id: str, **filters: object) -> dict:
    events = list_events(novel_id, **filters)  # type: ignore[arg-type]
    timed = [e for e in events if e["story_time"]]
    untimed = [e for e in events if not e["story_time"]]
    timed.sort(key=lambda e: (str(e["story_time"]), int(e["sequence"]), e["created_at"], e["id"]))
    untimed.sort(key=lambda e: (int(e["sequence"]), e["created_at"], e["id"]))
    return {"timed": timed, "untimed": untimed}


def list_by_chapter(novel_id: str, chapter_id: str) -> list[dict]:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM chapters WHERE id = ? AND novel_id = ?",
            (chapter_id, novel_id),
        ).fetchone()
    if row is None:
        raise ServiceError(404, "章节不存在")
    return list_events(novel_id, chapter_id=chapter_id)


def list_by_character(novel_id: str, character_id: str) -> list[dict]:
    _ensure_novel(novel_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM characters WHERE id = ? AND novel_id = ?",
            (character_id, novel_id),
        ).fetchone()
    if row is None:
        raise ServiceError(404, "人物不存在")
    return list_events(novel_id, character_id=character_id)


def count_events(novel_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM plot_events WHERE novel_id = ?", (novel_id,)
        ).fetchone()
    return int(row["n"]) if row else 0
