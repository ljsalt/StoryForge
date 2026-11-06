"""剧情记忆更新提案服务（P4.1.3）。

核心原则：AI 只生成提案，绝不直接修改正式数据。
- 提取：读取当前记忆快照喂给模型，模型输出结构化变化；服务端负责
  目标解析（名字→同小说 ID）、去重、before_json 实读与 conflict 标记。
- 审核：用户接受/修改后接受/拒绝；批次状态由提案状态推导。
- 应用：仅 accepted/modified 提案在单一事务内通过既有业务服务的
  _in_conn 函数写入；before_json 过期检测不一致即整体回滚；
  事务失败整体回滚，不允许部分成功却显示全部成功。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import get_connection
from . import ai_generation_service, ai_task_service, context_builder
from .chapter_service import _update_chapter_in_conn
from .character_relation_service import (
    _create_relation_in_conn,
    _end_relation_in_conn,
    _update_relation_in_conn,
)
from .character_service import _create_secret_in_conn, _update_state_in_conn
from .continuity_service import _chapter_row, _detect_character_ids, _ensure_novel, _now
from .errors import ServiceError
from .plot_event_service import _create_event_in_conn
from .writing_plan_schema import PlanValidationError, extract_json_object

_EXTRACT_CALL_TIMEOUT = 240.0

# 状态字段白名单：与 character_states 表列一致（防止模型写入不存在的字段）
_STATE_FIELDS = (
    "life_status", "current_location", "current_faction", "current_cultivation",
    "health_status", "emotional_state", "current_goal", "current_status",
)

_EXTRACT_SYSTEM = (
    "你是一部长篇小说的剧情记忆整理员。你的职责是阅读指定章节正文，"
    "提取正文中实际发生的结构化剧情变化，用于更新人物状态、人物关系、"
    "剧情事件与章节摘要。你只能提取正文明确发生或能够合理确认的事实；"
    "不得把人物的猜测、计划、谎言或传闻当作已发生的事实；"
    "不得因为正文提及某秘密就把它标记为已公开；"
    "不得重复提取当前记忆快照中已经存在的信息。"
)

_EXTRACT_JSON_INSTRUCTION = """
你必须只输出一个 JSON 对象，不允许输出解释文字、Markdown 代码块或任何额外内容。
JSON 结构必须严格如下：
{
  "changes": [
    {
      "proposal_type": "character_state | character_relation | character_secret | plot_event | chapter_summary | world_entry",
      "operation": "create | update | end",
      "character_name": "人物姓名（character_state/character_secret 必填）",
      "source_name": "关系发起人物姓名（character_relation 必填）",
      "target_name": "关系目标人物姓名（character_relation 必填）",
      "relation_type": "关系类型（character_relation 必填）",
      "fields": {"current_location": "...", "health_status": "..."},
      "relation": {"relation_type": "...", "description": "...", "strength": 0.5},
      "secret": {"title": "...", "content": "...", "secrecy_level": "restricted"},
      "event": {"title": "...", "description": "...", "event_type": "...",
                "story_time": "...", "location_name": "...", "importance": "normal",
                "participants": [{"name": "...", "role": "..."}]},
      "summary": "章节摘要（chapter_summary 必填）",
      "world_entry": {"name": "...", "category": "...", "content": "..."},
      "reason": "提取理由",
      "source_excerpt": "正文原文证据（原文引用）",
      "confidence": 0.0,
      "uncertainty": "不确定原因（无不确定时为空字符串）"
    }
  ]
}
规则：
1. 只能提取正文明确发生的事情；人物对白中的虚假陈述不得当作事实；
2. 区分事件发生、事件被发现、事件被回忆：回忆与转述不要生成新的剧情事件；
3. 同一事件被不同段落重复描述时只提取一次；
4. 与当前记忆快照一致的内容不要重复提取（快照中已有的事件、状态、关系跳过）；
5. character_state 只填实际发生变化的字段（fields 内不要包含无变化字段）；
6. character_relation：新关系用 create，已有关系性质变化用 update，关系终结用 end；
7. character_secret 仅允许 create（新增秘密），不得标记为已公开；
8. world_entry 仅在世界观设定发生明确新增/变化时提出，需给出充分证据；
9. 不确定的信息降低 confidence（0~1），并在 uncertainty 中说明原因；
10. 没有任何变化时返回 {"changes": []}。
"""


class ExtractValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("；".join(errors))
        self.errors = errors


class _ApplyConflict(ServiceError):
    """提案目标已删除或 before_json 过期：事务回滚后仍需把提案标记为 conflict。"""

    def __init__(self, proposal_id: str, message: str):
        super().__init__(409, message)
        self.proposal_id = proposal_id


def _load_json(raw: str | None, default=None):
    if default is None:
        default = {}
    try:
        value = json.loads(raw or "")
    except (ValueError, TypeError):
        return default
    return value if value is not None else default


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _clamp_confidence(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, number))


# ----------------------------- 目标解析与快照 -----------------------------

def _resolve_character(conn, novel_id: str, name: str):
    """按姓名/别名精确匹配同小说人物；唯一匹配返回行，否则 None。"""
    name = (name or "").strip()
    if not name:
        return None
    rows = conn.execute(
        "SELECT id, name, aliases FROM characters WHERE novel_id = ?", (novel_id,)
    ).fetchall()
    matches = []
    for row in rows:
        candidates = [row["name"]]
        aliases = _load_json(row["aliases"], [])
        if isinstance(aliases, list):
            candidates.extend(str(item) for item in aliases)
        if name in candidates:
            matches.append(row)
    if len(matches) == 1:
        return matches[0]
    return None


def _find_active_relation(conn, novel_id: str, source_id: str, target_id: str, relation_type: str):
    return conn.execute(
        """
        SELECT * FROM character_relations
         WHERE novel_id = ? AND source_character_id = ? AND target_character_id = ?
           AND relation_type = ? AND status = 'active'
         LIMIT 1
        """,
        (novel_id, source_id, target_id, relation_type),
    ).fetchone()


def _state_snapshot(conn, character_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM character_states WHERE character_id = ?", (character_id,)
    ).fetchone()
    if row is None:
        return None
    return {key: row[key] for key in _STATE_FIELDS}


def _memory_snapshot_text(conn, novel_id: str, chapter, character_ids: list[str]) -> str:
    """把当前记忆快照组织为提示词文本（模型据此判断增量）。"""
    lines: list[str] = ["人物当前状态："]
    if character_ids:
        placeholders = ", ".join("?" for _ in character_ids)
        rows = conn.execute(
            f"""
            SELECT c.id, c.name, s.life_status, s.current_location, s.current_faction,
                   s.current_cultivation, s.health_status, s.emotional_state,
                   s.current_goal, s.current_status
              FROM characters c
              LEFT JOIN character_states s ON s.character_id = c.id
             WHERE c.novel_id = ? AND c.id IN ({placeholders})
             ORDER BY c.sort_order ASC
            """,
            [novel_id] + character_ids,
        ).fetchall()
    else:
        rows = []
    for row in rows:
        lines.append(
            f"- {row['name']}：生命={row['life_status'] or 'alive'}，位置={row['current_location'] or '未知'}，"
            f"势力={row['current_faction'] or '无'}，境界={row['current_cultivation'] or '无'}，"
            f"伤势={row['health_status'] or '无'}，情绪={row['emotional_state'] or '无'}，"
            f"目标={row['current_goal'] or '无'}，状态={row['current_status'] or '无'}"
        )
    if not rows:
        lines.append("- （本章未检测到关联人物）")

    lines.append("活跃人物关系：")
    if character_ids:
        placeholders = ", ".join("?" for _ in character_ids)
        rel_rows = conn.execute(
            f"""
            SELECT r.relation_type, r.description, r.strength,
                   s.name AS source_name, t.name AS target_name
              FROM character_relations r
              JOIN characters s ON s.id = r.source_character_id
              JOIN characters t ON t.id = r.target_character_id
             WHERE r.novel_id = ? AND r.status = 'active'
               AND (r.source_character_id IN ({placeholders})
                    OR r.target_character_id IN ({placeholders}))
             ORDER BY r.updated_at DESC
             LIMIT 30
            """,
            [novel_id] + character_ids + character_ids,
        ).fetchall()
        for rel in rel_rows:
            strength = f"（强度{rel['strength']}）" if rel["strength"] is not None else ""
            desc = f"：{rel['description']}" if rel["description"] else ""
            lines.append(f"- {rel['source_name']} —{rel['relation_type']}→ {rel['target_name']}{strength}{desc}")
        if not rel_rows:
            lines.append("- （无）")
    else:
        lines.append("- （无）")

    lines.append("本章已记录剧情事件：")
    event_rows = conn.execute(
        "SELECT title FROM plot_events WHERE novel_id = ? AND chapter_id = ? ORDER BY sequence ASC, created_at ASC",
        (novel_id, chapter["id"]),
    ).fetchall()
    if event_rows:
        lines.extend(f"- {row['title']}" for row in event_rows)
    else:
        lines.append("- （无）")

    lines.append(f"章节当前摘要：{chapter['summary'] or '（空）'}")

    lines.append("人物已有秘密（仅标题，用于避免重复提取）：")
    if character_ids:
        placeholders = ", ".join("?" for _ in character_ids)
        secret_rows = conn.execute(
            f"""
            SELECT c.name AS character_name, s.title, s.reveal_status
              FROM character_secrets s
              JOIN characters c ON c.id = s.character_id
             WHERE c.novel_id = ? AND c.id IN ({placeholders})
             ORDER BY s.updated_at DESC
             LIMIT 20
            """,
            [novel_id] + character_ids,
        ).fetchall()
        if secret_rows:
            lines.extend(
                f"- {row['character_name']}：{row['title']}（{row['reveal_status']}）"
                for row in secret_rows
            )
        else:
            lines.append("- （无）")
    else:
        lines.append("- （无）")
    return "\n".join(lines)


# ----------------------------- 提案解析 -----------------------------

def _build_proposal(conn, novel_id: str, chapter, change: dict, seen_event_titles: set[str], report: dict) -> dict | None:
    """把模型输出的一条 change 解析为规范化提案；返回 None 表示跳过（记入 report）。"""
    ptype = str(change.get("proposal_type") or "").strip()
    operation = str(change.get("operation") or "create").strip()
    reason = str(change.get("reason") or "").strip()
    excerpt = str(change.get("source_excerpt") or "").strip()
    confidence = _clamp_confidence(change.get("confidence"))
    uncertainty = str(change.get("uncertainty") or "").strip()
    if uncertainty:
        confidence = min(confidence, 0.5)

    base = {
        "proposal_type": ptype,
        "operation": operation,
        "reason": reason + (f"（不确定：{uncertainty}）" if uncertainty else ""),
        "source_excerpt": excerpt,
        "confidence": confidence,
        "target_type": "",
        "target_id": None,
        "before": {},
        "proposed": {},
        "status": "pending",
    }

    if ptype == "character_state" and operation == "update":
        char = _resolve_character(conn, novel_id, str(change.get("character_name") or ""))
        raw_fields = change.get("fields") if isinstance(change.get("fields"), dict) else {}
        fields = {key: str(value) for key, value in raw_fields.items()
                  if key in _STATE_FIELDS and value is not None and str(value).strip()}
        if char is None:
            base.update(target_type="character_state", status="conflict",
                        proposed={"character_name": change.get("character_name"), "fields": fields},
                        reason=base["reason"] + "（目标人物无法唯一解析）")
            report["unresolved"] += 1
            return base
        if not fields:
            report["skipped"].append(f"人物状态无有效字段：{char['name']}")
            return None
        current = _state_snapshot(conn, char["id"]) or {}
        changed = {key: value for key, value in fields.items() if current.get(key) != value}
        if not changed:
            report["skipped"].append(f"人物状态无变化：{char['name']}")
            return None
        before = {key: current.get(key) for key in changed}
        base.update(target_type="character_state", target_id=char["id"], before=before,
                    proposed={"character_id": char["id"], "character_name": char["name"], "fields": changed})
        return base

    if ptype == "character_relation":
        source = _resolve_character(conn, novel_id, str(change.get("source_name") or ""))
        target = _resolve_character(conn, novel_id, str(change.get("target_name") or ""))
        rel_data = change.get("relation") if isinstance(change.get("relation"), dict) else {}
        relation_type = str(change.get("relation_type") or rel_data.get("relation_type") or "").strip()
        if source is None or target is None or not relation_type:
            base.update(target_type="character_relation", status="conflict",
                        proposed={"source_name": change.get("source_name"),
                                  "target_name": change.get("target_name"),
                                  "relation_type": relation_type},
                        reason=base["reason"] + "（关系目标无法唯一解析或关系类型缺失）")
            report["unresolved"] += 1
            return base
        existing = _find_active_relation(conn, novel_id, source["id"], target["id"], relation_type)
        if operation == "create":
            if existing is not None:
                report["skipped"].append(f"关系已存在：{source['name']} —{relation_type}→ {target['name']}")
                return None
            base.update(target_type="character_relation",
                        proposed={"source_character_id": source["id"], "target_character_id": target["id"],
                                  "source_name": source["name"], "target_name": target["name"],
                                  "relation_type": relation_type,
                                  "description": str(rel_data.get("description") or ""),
                                  "strength": rel_data.get("strength"),
                                  "chapter_id": chapter["id"],
                                  "story_time": rel_data.get("story_time")})
            return base
        if operation in ("update", "end"):
            if existing is None:
                base.update(target_type="character_relation", status="conflict",
                            proposed={"source_name": source["name"], "target_name": target["name"],
                                      "relation_type": relation_type, "operation": operation},
                            reason=base["reason"] + "（未找到对应的活跃关系，无法更新/结束）")
                report["unresolved"] += 1
                return base
            before = {
                "relation_type": existing["relation_type"],
                "description": existing["description"],
                "strength": existing["strength"],
                "status": existing["status"],
            }
            proposed = {"relation_id": existing["id"],
                        "source_name": source["name"], "target_name": target["name"],
                        "relation_type": relation_type,
                        "description": str(rel_data.get("description") or existing["description"] or ""),
                        "strength": rel_data.get("strength", existing["strength"]),
                        "chapter_id": chapter["id"],
                        "event_title": str(rel_data.get("event_title") or ""),
                        "story_time": rel_data.get("story_time")}
            base.update(target_type="character_relation", target_id=existing["id"],
                        before=before, proposed=proposed)
            return base
        report["skipped"].append(f"不支持的关系操作：{operation}")
        return None

    if ptype == "character_secret" and operation == "create":
        char = _resolve_character(conn, novel_id, str(change.get("character_name") or ""))
        secret = change.get("secret") if isinstance(change.get("secret"), dict) else {}
        title = str(secret.get("title") or "").strip()
        if char is None or not title:
            base.update(target_type="character_secret", status="conflict",
                        proposed={"character_name": change.get("character_name"), "title": title},
                        reason=base["reason"] + "（目标人物无法唯一解析或秘密标题缺失）")
            report["unresolved"] += 1
            return base
        dup = conn.execute(
            "SELECT id FROM character_secrets WHERE character_id = ? AND title = ?",
            (char["id"], title),
        ).fetchone()
        if dup is not None:
            report["skipped"].append(f"秘密已存在：{char['name']}《{title}》")
            return None
        base.update(target_type="character_secret", target_id=char["id"],
                    proposed={"character_id": char["id"], "character_name": char["name"],
                              "title": title, "content": str(secret.get("content") or ""),
                              "secrecy_level": str(secret.get("secrecy_level") or "restricted"),
                              "reveal_status": "unrevealed",  # 秘密提案绝不自动公开
                              "notes": str(secret.get("notes") or "")})
        return base

    if ptype == "plot_event" and operation == "create":
        event = change.get("event") if isinstance(change.get("event"), dict) else {}
        title = str(event.get("title") or "").strip()
        if not title:
            report["skipped"].append("剧情事件缺少标题")
            return None
        if title in seen_event_titles:
            report["skipped"].append(f"剧情事件重复：{title}")
            return None
        dup = conn.execute(
            "SELECT id FROM plot_events WHERE novel_id = ? AND chapter_id = ? AND title = ?",
            (novel_id, chapter["id"], title),
        ).fetchone()
        if dup is not None:
            report["skipped"].append(f"本章已有同名剧情事件：{title}")
            return None
        participants = []
        unresolved_participants = []
        for item in event.get("participants") or []:
            if not isinstance(item, dict):
                continue
            char = _resolve_character(conn, novel_id, str(item.get("name") or ""))
            if char is None:
                unresolved_participants.append(str(item.get("name") or ""))
                continue
            participants.append({"character_id": char["id"], "character_name": char["name"],
                                 "participant_role": str(item.get("role") or "")})
        seen_event_titles.add(title)
        status = "pending"
        reason = base["reason"]
        if unresolved_participants:
            status = "conflict"
            reason += f"（参与人物无法解析：{'、'.join(unresolved_participants)}）"
            report["unresolved"] += 1
        base.update(target_type="plot_event", status=status, reason=reason,
                    proposed={"title": title, "description": str(event.get("description") or ""),
                              "event_type": str(event.get("event_type") or ""),
                              "story_time": str(event.get("story_time") or ""),
                              "location_name": str(event.get("location_name") or ""),
                              "importance": str(event.get("importance") or "normal"),
                              "chapter_id": chapter["id"],
                              "participants": participants})
        return base

    if ptype == "chapter_summary" and operation == "update":
        summary = str(change.get("summary") or "").strip()
        if not summary or summary == (chapter["summary"] or "").strip():
            report["skipped"].append("章节摘要无变化")
            return None
        base.update(target_type="chapter", target_id=chapter["id"],
                    before={"summary": chapter["summary"] or ""},
                    proposed={"chapter_id": chapter["id"], "summary": summary})
        return base

    if ptype == "world_entry":
        entry = change.get("world_entry") if isinstance(change.get("world_entry"), dict) else {}
        name = str(entry.get("name") or "").strip()
        if not name:
            report["skipped"].append("世界观条目缺少名称")
            return None
        # 世界观条目本阶段仅生成提案，不支持自动应用（前端仅展示，禁止接受）
        base.update(target_type="world_entry",
                    proposed={"name": name, "category": str(entry.get("category") or ""),
                              "content": str(entry.get("content") or ""),
                              "apply_supported": False})
        return base

    report["skipped"].append(f"不支持或未实现的提案类型：{ptype}/{operation}")
    return None


# ----------------------------- 提取任务 -----------------------------

async def create_batch(novel_id: str, chapter_id: str, payload: dict) -> dict:
    """创建一次记忆提取任务：AI 输出变化清单，服务端解析为提案批次。"""
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        chapter = _chapter_row(conn, novel_id, chapter_id)
    content = (chapter["content"] or "").strip()
    if not content:
        raise ServiceError(400, "章节正文为空，无法提取剧情变化")

    model_id = str(payload.get("model_id") or "").strip() or None
    with get_connection() as conn:
        char_ids, _ = _detect_character_ids(conn, novel_id, content)
        snapshot_text = _memory_snapshot_text(conn, novel_id, chapter, char_ids)

    context = context_builder.build_context(
        novel_id,
        task_type="assistant",
        chapter_id=chapter_id,
        character_ids=char_ids or None,
        token_budget=payload.get("token_budget"),
        pov="author",
        user_requirement="提取本章节实际发生的结构化剧情变化",
        extra_sections=[
            {"key": "chapter_content",
             "title": f"章节正文（第{chapter['chapter_number']}章 {chapter['title']}）",
             "content": content, "priority": 98, "required": True},
            {"key": "memory_snapshot", "title": "当前记忆快照",
             "content": snapshot_text, "priority": 90, "required": False},
        ],
    )
    system = f"{_EXTRACT_SYSTEM}\n{_EXTRACT_JSON_INSTRUCTION}"
    user = (
        "以下是小说上下文，其中包含章节正文与当前记忆快照：\n"
        f"{context['context_text']}\n\n"
        "请提取章节正文中实际发生的结构化剧情变化，只输出符合要求的 JSON 对象。"
    )
    result = await ai_generation_service.generate(
        {
            "novel_id": novel_id,
            "task_type": "assistant",
            "system_prompt": system,
            "user_prompt": user,
            "temperature": float(payload.get("temperature", 0.3)),
            "max_tokens": int(payload.get("max_tokens") or 4096),
            "timeout": _EXTRACT_CALL_TIMEOUT,
            "model_id": model_id,
            "include_reasoning": False,
        }
    )
    if not result["success"]:
        message = result.get("error_message") or result.get("error_code") or "AI 调用失败"
        raise ServiceError(502, f"记忆提取调用失败：{message}")
    if result.get("truncated"):
        raise ServiceError(502, "记忆提取输出被截断，请增大 max_tokens 后重试")
    ai_task_service.touch_task(result.get("task_id") or "")

    try:
        changes = _parse_changes(result["content"])
    except ExtractValidationError as first_error:
        changes = await _repair_extract(novel_id, system, user, result["content"], first_error, payload)

    now = _now()
    batch_id = uuid4().hex
    report = {"skipped": [], "unresolved": 0}
    proposals: list[dict] = []
    seen_event_titles: set[str] = set()
    with get_connection() as conn:
        for change in changes:
            try:
                proposal = _build_proposal(conn, novel_id, chapter, change, seen_event_titles, report)
            except Exception:  # 单条解析异常不应拖垮整个批次
                report["skipped"].append("一条变化解析失败，已跳过")
                proposal = None
            if proposal is not None:
                proposals.append(proposal)

        conn.execute(
            """
            INSERT INTO memory_update_batches
                (id, novel_id, chapter_id, check_id, status, report_json, created_at)
            VALUES (?, ?, ?, ?, 'pending_review', ?, ?)
            """,
            (
                batch_id, novel_id, chapter_id,
                str(payload.get("check_id") or "").strip() or None,
                _dump({**report, "counts": {"total": len(changes), "created": len(proposals)},
                       "model": result.get("model") or "",
                       "task_id": result.get("task_id")}),
                now,
            ),
        )
        for proposal in proposals:
            conn.execute(
                """
                INSERT INTO memory_update_proposals
                    (id, batch_id, novel_id, proposal_type, target_type, target_id,
                     operation, before_json, proposed_json, reason, source_excerpt,
                     confidence, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex, batch_id, novel_id,
                    proposal["proposal_type"], proposal["target_type"], proposal["target_id"],
                    proposal["operation"], _dump(proposal["before"]), _dump(proposal["proposed"]),
                    proposal["reason"], proposal["source_excerpt"], proposal["confidence"],
                    proposal["status"], now,
                ),
            )
    return get_batch(novel_id, batch_id)


def _parse_changes(content: str) -> list[dict]:
    try:
        data = extract_json_object(content)
    except PlanValidationError as exc:
        raise ExtractValidationError(exc.errors) from exc
    changes = data.get("changes")
    if changes is None:
        return []
    if not isinstance(changes, list):
        raise ExtractValidationError(["changes 必须是数组"])
    out = [item for item in changes if isinstance(item, dict)]
    if len(out) != len(changes):
        raise ExtractValidationError(["changes 的元素必须是对象"])
    return out


async def _repair_extract(novel_id, system, user, raw_content, error, payload) -> list[dict]:
    feedback = "\n".join(f"- {item}" for item in error.errors[:20])
    repair_user = (
        f"{user}\n\n你上一次的输出不是合法的变化清单，问题如下：\n{feedback}\n\n"
        f"上一次输出片段（仅供修正参考）：\n{raw_content[:2000]}\n\n"
        "请只输出修正后的完整 JSON 对象。"
    )
    repair = await ai_generation_service.generate(
        {
            "novel_id": novel_id,
            "task_type": "assistant",
            "system_prompt": system,
            "user_prompt": repair_user,
            "temperature": 0.2,
            "max_tokens": int(payload.get("max_tokens") or 4096),
            "timeout": _EXTRACT_CALL_TIMEOUT,
        }
    )
    if not repair["success"] or repair.get("truncated"):
        raise ServiceError(502, "记忆提取结果格式不合法，自动修复一次后仍未通过校验，请重新提取")
    ai_task_service.touch_task(repair.get("task_id") or "")
    try:
        return _parse_changes(repair["content"])
    except ExtractValidationError as exc:
        raise ServiceError(
            502, "记忆提取结果格式不合法：" + "；".join(exc.errors[:5]) + "。请重新提取"
        ) from exc


# ----------------------------- 查询 -----------------------------

def _batch_row(conn, novel_id: str, batch_id: str):
    row = conn.execute(
        "SELECT * FROM memory_update_batches WHERE id = ? AND novel_id = ?",
        (batch_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "记忆更新批次不存在")
    return row


def _proposal_row(conn, novel_id: str, proposal_id: str):
    row = conn.execute(
        "SELECT * FROM memory_update_proposals WHERE id = ? AND novel_id = ?",
        (proposal_id, novel_id),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "记忆更新提案不存在")
    return row


def _to_batch_out(row, proposals: list[dict] | None = None) -> dict:
    out = {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "chapter_id": row["chapter_id"],
        "check_id": row["check_id"],
        "status": row["status"],
        "report": _load_json(row["report_json"]),
        "created_at": row["created_at"],
        "reviewed_at": row["reviewed_at"],
        "applied_at": row["applied_at"],
    }
    if proposals is not None:
        out["proposals"] = proposals
    return out


def _current_target_json(conn, novel_id: str, row) -> object:
    """查询提案目标的实时当前数据，供前端对比 before_json 判断是否过期。"""
    target_type = row["target_type"]
    target_id = row["target_id"]
    if not target_id:
        return None
    if target_type == "character_state":
        char = conn.execute(
            "SELECT name FROM characters WHERE id = ? AND novel_id = ?", (target_id, novel_id)
        ).fetchone()
        if char is None:
            return None
        return {"character_name": char["name"], "state": _state_snapshot(conn, target_id)}
    if target_type == "character_relation":
        rel = conn.execute(
            """
            SELECT r.*, s.name AS source_name, t.name AS target_name
              FROM character_relations r
              JOIN characters s ON s.id = r.source_character_id
              JOIN characters t ON t.id = r.target_character_id
             WHERE r.id = ? AND r.novel_id = ?
            """,
            (target_id, novel_id),
        ).fetchone()
        if rel is None:
            return None
        return {"source_name": rel["source_name"], "target_name": rel["target_name"],
                "relation_type": rel["relation_type"], "status": rel["status"],
                "description": rel["description"], "strength": rel["strength"]}
    if target_type == "chapter":
        ch = conn.execute(
            "SELECT summary FROM chapters WHERE id = ? AND novel_id = ?", (target_id, novel_id)
        ).fetchone()
        return {"summary": ch["summary"]} if ch else None
    if target_type == "character_secret":
        secret = conn.execute(
            "SELECT s.*, c.name AS character_name FROM character_secrets s"
            " JOIN characters c ON c.id = s.character_id WHERE s.id = ?",
            (target_id,),
        ).fetchone()
        if secret is None:
            return None
        return {"character_name": secret["character_name"], "title": secret["title"],
                "content": secret["content"], "secrecy_level": secret["secrecy_level"],
                "reveal_status": secret["reveal_status"]}
    return None


def _to_proposal_out(conn, novel_id: str, row) -> dict:
    proposed = _load_json(row["proposed_json"])
    return {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "novel_id": row["novel_id"],
        "proposal_type": row["proposal_type"],
        "target_type": row["target_type"],
        "target_id": row["target_id"],
        "operation": row["operation"],
        "before": _load_json(row["before_json"]),
        "proposed": proposed,
        "final": _load_json(row["final_json"]) if row["final_json"] else None,
        "reason": row["reason"],
        "source_excerpt": row["source_excerpt"],
        "confidence": row["confidence"],
        "status": row["status"],
        "user_note": row["user_note"],
        "apply_supported": row["target_type"] != "world_entry",
        "current": _current_target_json(conn, novel_id, row),
        "created_at": row["created_at"],
        "reviewed_at": row["reviewed_at"],
        "applied_at": row["applied_at"],
    }


def list_batches(novel_id: str, chapter_id: str) -> list[dict]:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        _chapter_row(conn, novel_id, chapter_id)
        rows = conn.execute(
            "SELECT * FROM memory_update_batches WHERE novel_id = ? AND chapter_id = ?"
            " ORDER BY created_at DESC, id DESC",
            (novel_id, chapter_id),
        ).fetchall()
        result = []
        for row in rows:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM memory_update_proposals WHERE batch_id = ?",
                (row["id"],),
            ).fetchone()
            item = _to_batch_out(row)
            item["proposal_count"] = int(count["n"]) if count else 0
            result.append(item)
    return result


def get_batch(novel_id: str, batch_id: str, *, include_proposals: bool = True) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _batch_row(conn, novel_id, batch_id)
        proposals = None
        if include_proposals:
            proposals = [_to_proposal_out(conn, novel_id, p) for p in _proposals_of(conn, batch_id)]
    return _to_batch_out(row, proposals)


def _proposals_of(conn, batch_id: str):
    return conn.execute(
        "SELECT * FROM memory_update_proposals WHERE batch_id = ? ORDER BY created_at ASC, id ASC",
        (batch_id,),
    ).fetchall()


def list_proposals(novel_id: str, batch_id: str) -> list[dict]:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        _batch_row(conn, novel_id, batch_id)
        return [_to_proposal_out(conn, novel_id, row) for row in _proposals_of(conn, batch_id)]


def get_proposal(novel_id: str, proposal_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _proposal_row(conn, novel_id, proposal_id)
        return _to_proposal_out(conn, novel_id, row)


# ----------------------------- 审核 -----------------------------

def _derive_batch_status(statuses: list[str]) -> str:
    if not statuses:
        return "pending_review"
    if any(s == "applied" for s in statuses):
        return "applied"
    undecided = {"pending", "conflict"}
    if all(s in undecided for s in statuses):
        return "pending_review"
    if all(s == "rejected" for s in statuses):
        return "rejected"
    if any(s in undecided for s in statuses):
        return "partially_approved"
    return "approved"


def _refresh_batch_status(conn, batch_id: str, now: str) -> None:
    rows = conn.execute(
        "SELECT status FROM memory_update_proposals WHERE batch_id = ?", (batch_id,)
    ).fetchall()
    status = _derive_batch_status([row["status"] for row in rows])
    conn.execute(
        "UPDATE memory_update_batches SET status = ?, reviewed_at = ? WHERE id = ?",
        (status, now, batch_id),
    )


def _review_one(conn, novel_id: str, proposal_id: str, action: str,
                final_json, user_note: str, now: str) -> None:
    row = _proposal_row(conn, novel_id, proposal_id)
    if row["status"] == "applied":
        raise ServiceError(409, "提案已应用，不能再审核")
    if action == "accept":
        if row["target_type"] == "world_entry":
            raise ServiceError(400, "世界观条目提案本阶段仅作参考，不支持自动应用，请手动处理")
        conn.execute(
            "UPDATE memory_update_proposals SET status = ?, user_note = ?, reviewed_at = ? WHERE id = ?",
            ("modified" if row["final_json"] else "accepted", user_note or row["user_note"], now, proposal_id),
        )
    elif action == "reject":
        conn.execute(
            "UPDATE memory_update_proposals SET status = 'rejected', user_note = ?, reviewed_at = ? WHERE id = ?",
            (user_note or row["user_note"], now, proposal_id),
        )
    elif action == "modify":
        if row["target_type"] == "world_entry":
            raise ServiceError(400, "世界观条目提案本阶段仅作参考，不支持自动应用，请手动处理")
        if not isinstance(final_json, dict) or not final_json:
            raise ServiceError(400, "修改提案时必须提供 final_json")
        conn.execute(
            "UPDATE memory_update_proposals SET status = 'modified', final_json = ?, user_note = ?, reviewed_at = ? WHERE id = ?",
            (_dump(final_json), user_note or row["user_note"], now, proposal_id),
        )
    elif action == "reset":
        conn.execute(
            "UPDATE memory_update_proposals SET status = 'pending', final_json = NULL, user_note = ?, reviewed_at = NULL WHERE id = ?",
            (user_note or row["user_note"], proposal_id),
        )
    else:
        raise ServiceError(400, "不支持的审核操作")


def update_proposal(novel_id: str, proposal_id: str, payload: dict) -> dict:
    """修改提案内容（用户修改后的内容才是最终提交内容，不会被 AI 覆盖）。"""
    now = _now()
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _proposal_row(conn, novel_id, proposal_id)
        if row["status"] == "applied":
            raise ServiceError(409, "提案已应用，不能再修改")
        if row["target_type"] == "world_entry":
            raise ServiceError(400, "世界观条目提案本阶段仅作参考，不支持自动应用，请手动处理")
        final_json = payload.get("final_json")
        if not isinstance(final_json, dict) or not final_json:
            raise ServiceError(400, "修改提案时必须提供 final_json")
        conn.execute(
            """
            UPDATE memory_update_proposals
               SET final_json = ?, user_note = ?, status = 'modified', reviewed_at = ?
             WHERE id = ?
            """,
            (_dump(final_json), str(payload.get("user_note") or row["user_note"] or ""), now, proposal_id),
        )
        _refresh_batch_status(conn, row["batch_id"], now)
    return get_proposal(novel_id, proposal_id)


def accept_proposal(novel_id: str, proposal_id: str, payload: dict) -> dict:
    now = _now()
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _proposal_row(conn, novel_id, proposal_id)
        _review_one(conn, novel_id, proposal_id, "accept", None,
                    str(payload.get("user_note") or ""), now)
        _refresh_batch_status(conn, row["batch_id"], now)
    return get_proposal(novel_id, proposal_id)


def reject_proposal(novel_id: str, proposal_id: str, payload: dict) -> dict:
    now = _now()
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = _proposal_row(conn, novel_id, proposal_id)
        _review_one(conn, novel_id, proposal_id, "reject", None,
                    str(payload.get("user_note") or ""), now)
        _refresh_batch_status(conn, row["batch_id"], now)
    return get_proposal(novel_id, proposal_id)


def review_batch(novel_id: str, batch_id: str, payload: dict) -> dict:
    """批量审核：items = [{"id", "action": accept|reject|modify|reset, "final_json"?, "user_note"?}]"""
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ServiceError(400, "批量审核列表不能为空")
    if len(items) > 200:
        raise ServiceError(400, "单次批量审核最多 200 条")
    now = _now()
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        batch = _batch_row(conn, novel_id, batch_id)
        if batch["status"] == "applied":
            raise ServiceError(409, "批次已应用，不能再审核")
        for item in items:
            if not isinstance(item, dict):
                raise ServiceError(400, "批量审核条目必须是对象")
            proposal_id = str(item.get("id") or "").strip()
            action = str(item.get("action") or "").strip()
            row = _proposal_row(conn, novel_id, proposal_id)
            if row["batch_id"] != batch_id:
                raise ServiceError(400, "提案不属于当前批次")
            _review_one(conn, novel_id, proposal_id, action,
                        item.get("final_json"), str(item.get("user_note") or ""), now)
        _refresh_batch_status(conn, batch_id, now)
    return get_batch(novel_id, batch_id)


# ----------------------------- 正式应用 -----------------------------

def _before_matches(before: dict, current: dict | None) -> bool:
    """before_json 子集一致性：before 中每个键都必须与当前值相等。"""
    if not before:
        return True
    if current is None:
        return False
    for key, value in before.items():
        current_value = current.get(key) if isinstance(current, dict) else None
        if _dump(current_value) != _dump(value):
            return False
    return True


def _apply_one(conn, novel_id: str, row, now: str) -> str:
    """在事务内应用单条提案，返回结果说明。任何失败都抛异常触发整体回滚。"""
    data = _load_json(row["final_json"]) if row["final_json"] else _load_json(row["proposed_json"])
    target_type = row["target_type"]
    operation = row["operation"]

    if target_type == "character_state" and operation == "update":
        character_id = data.get("character_id") or row["target_id"]
        current = _state_snapshot(conn, character_id)
        if current is None:
            raise _ApplyConflict(row["id"], f"提案 {row['id']} 的目标人物状态不存在（可能已被删除）")
        before = _load_json(row["before_json"])
        if not _before_matches(before, current):
            raise _ApplyConflict(row["id"], f"提案 {row['id']} 的目标数据已被其他操作修改，请重新审核")
        _update_state_in_conn(conn, novel_id, character_id, data.get("fields") or {}, now)
        return f"人物状态已更新：{data.get('character_name') or character_id}"

    if target_type == "plot_event" and operation == "create":
        participants = [
            {"character_id": p["character_id"], "participant_role": p.get("participant_role") or ""}
            for p in data.get("participants") or []
        ]
        event_id = _create_event_in_conn(conn, novel_id, {
            "title": data.get("title"), "description": data.get("description") or "",
            "event_type": data.get("event_type") or "",
            "story_time": data.get("story_time") or "",
            "location_name": data.get("location_name") or "",
            "importance": data.get("importance") or "normal",
            "chapter_id": data.get("chapter_id"),
            "participants": participants,
        }, now)
        conn.execute("UPDATE memory_update_proposals SET target_id = ? WHERE id = ?",
                     (event_id, row["id"]))
        return f"剧情事件已创建：{data.get('title')}"

    if target_type == "character_relation":
        if operation == "create":
            relation_id = _create_relation_in_conn(conn, novel_id, {
                "source_character_id": data.get("source_character_id"),
                "target_character_id": data.get("target_character_id"),
                "relation_type": data.get("relation_type"),
                "description": data.get("description") or "",
                "strength": data.get("strength"),
                "chapter_id": data.get("chapter_id"),
                "story_time": data.get("story_time"),
            }, now)
            conn.execute("UPDATE memory_update_proposals SET target_id = ? WHERE id = ?",
                         (relation_id, row["id"]))
            return f"人物关系已建立：{data.get('source_name')} —{data.get('relation_type')}→ {data.get('target_name')}"
        relation_id = data.get("relation_id") or row["target_id"]
        rel = conn.execute(
            "SELECT * FROM character_relations WHERE id = ? AND novel_id = ?",
            (relation_id, novel_id),
        ).fetchone()
        if rel is None:
            raise _ApplyConflict(row["id"], f"提案 {row['id']} 的目标关系不存在（可能已被删除）")
        before = _load_json(row["before_json"])
        current = {"relation_type": rel["relation_type"], "description": rel["description"],
                   "strength": rel["strength"], "status": rel["status"]}
        if not _before_matches(before, current):
            raise _ApplyConflict(row["id"], f"提案 {row['id']} 的目标数据已被其他操作修改，请重新审核")
        event_info = {"title": data.get("event_title") or "",
                      "description": f"章节记忆更新：{row['reason'][:200]}",
                      "chapter_id": data.get("chapter_id"),
                      "story_time": data.get("story_time")}
        if operation == "update":
            _update_relation_in_conn(conn, novel_id, relation_id, {
                "description": data.get("description"),
                "strength": data.get("strength"),
            }, event_info)
            return f"人物关系已更新：{data.get('source_name')} —{data.get('relation_type')}→ {data.get('target_name')}"
        if operation == "end":
            _end_relation_in_conn(conn, novel_id, relation_id, event_info=event_info, now=now)
            return f"人物关系已结束：{data.get('source_name')} —{data.get('relation_type')}→ {data.get('target_name')}"
        raise ServiceError(400, f"不支持的关系操作：{operation}")

    if target_type == "chapter" and operation == "update":
        chapter_id = data.get("chapter_id") or row["target_id"]
        ch = conn.execute(
            "SELECT summary FROM chapters WHERE id = ? AND novel_id = ?", (chapter_id, novel_id)
        ).fetchone()
        if ch is None:
            raise _ApplyConflict(row["id"], f"提案 {row['id']} 的目标章节不存在（可能已被删除）")
        before = _load_json(row["before_json"])
        if not _before_matches(before, {"summary": ch["summary"]}):
            raise _ApplyConflict(row["id"], f"提案 {row['id']} 的目标数据已被其他操作修改，请重新审核")
        _update_chapter_in_conn(conn, novel_id, chapter_id, {"summary": data.get("summary") or ""})
        return "章节摘要已更新"

    if target_type == "character_secret" and operation == "create":
        character_id = data.get("character_id") or row["target_id"]
        secret_id = _create_secret_in_conn(conn, novel_id, character_id, {
            "title": data.get("title"), "content": data.get("content") or "",
            "secrecy_level": data.get("secrecy_level") or "restricted",
            "reveal_status": "unrevealed",  # 绝不自动公开
            "notes": data.get("notes") or "",
        }, now)
        conn.execute("UPDATE memory_update_proposals SET target_id = ? WHERE id = ?",
                     (secret_id, row["id"]))
        return f"人物秘密已创建：{data.get('title')}"

    if target_type == "world_entry":
        raise ServiceError(400, "世界观条目提案不支持自动应用")

    raise ServiceError(400, f"不支持的提案类型：{row['proposal_type']}/{operation}")


def _mark_conflict(conn, proposal_id: str, now: str) -> None:
    conn.execute(
        "UPDATE memory_update_proposals SET status = 'conflict', reviewed_at = ? WHERE id = ?",
        (now, proposal_id),
    )


def apply_batch(novel_id: str, batch_id: str) -> dict:
    """应用批次中所有已接受/已修改的提案：单一事务，整体成功或整体回滚。"""
    now = _now()
    try:
        with get_connection() as conn:
            _ensure_novel(conn, novel_id)
            batch = _batch_row(conn, novel_id, batch_id)
            if batch["status"] == "applied":
                raise ServiceError(409, "批次已应用，不能重复提交")
            if batch["status"] not in ("approved", "partially_approved"):
                raise ServiceError(409, "批次尚未完成审核，不能提交")

            rows = conn.execute(
                """
                SELECT * FROM memory_update_proposals
                 WHERE batch_id = ? AND status IN ('accepted', 'modified')
                 ORDER BY created_at ASC, id ASC
                """,
                (batch_id,),
            ).fetchall()
            if not rows:
                raise ServiceError(400, "批次中没有已接受的提案")

            results: list[dict] = []
            for row in rows:
                message = _apply_one(conn, novel_id, row, now)
                conn.execute(
                    "UPDATE memory_update_proposals SET status = 'applied', applied_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                results.append({"proposal_id": row["id"], "result": message})

            conn.execute(
                "UPDATE memory_update_batches SET status = 'applied', applied_at = ? WHERE id = ?",
                (now, batch_id),
            )
    except sqlite3.IntegrityError as exc:
        raise ServiceError(409, f"提案应用违反数据约束，已整体回滚：{exc}") from exc
    except _ApplyConflict as exc:
        # 冲突标记必须在回滚后的独立事务中写入，否则会被一起回滚掉
        with get_connection() as conn:
            _mark_conflict(conn, exc.proposal_id, _now())
            _refresh_batch_status(conn, batch_id, _now())
        raise ServiceError(409, exc.message) from exc
    return {"batch": get_batch(novel_id, batch_id), "applied": results}
