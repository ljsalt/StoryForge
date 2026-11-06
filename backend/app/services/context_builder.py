"""上下文组装器：按需检索 + 分层组织 + Token 预算 + 秘密隔离。

设计要点：
1. 不把整部小说的全部正文塞进上下文；历史章节只用摘要，剧情事件限量截取。
2. 分区（sections）按优先级组织：核心设定与当前任务优先保留，
   超出预算时从低优先级分区开始截断或整体剔除。
3. 秘密隔离：仅作者视角（pov='author'）包含人物秘密；
   叙事/角色视角一律不注入秘密。角色知识状态系统尚未实现，
   选择角色视角时记录 warning，而不是发明不存在的知识字段。
4. Token 数为保守估算（estimate_tokens），结果标记为 estimated。
"""

from __future__ import annotations

from ..core.config import get_settings
from ..database.db import get_connection
from .errors import ServiceError
from .token_util import estimate_tokens

# 各分区检索上限：防止“把整本小说塞给模型”
_MAX_WORLD_ENTRIES = 40
_MAX_WORLD_RELATIONS = 30
_MAX_CHARACTERS = 20
_MAX_RELATIONS = 25
_MAX_RELATION_EVENTS = 10
_MAX_SECRETS = 15
_MAX_PLOT_EVENTS = 15
_MAX_CHAPTER_SUMMARIES = 10

_POVS = ("author", "narrative", "character")

# 分区在最终文本中的固定开销：标题标记「【标题】」与分区间的空行
_SECTION_OVERHEAD = 2


def _truncate(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _section_cost(title: str, content: str) -> int:
    """分区实际占用：与最终 context_text 中的写法保持一致（含标题与分隔开销）。"""
    return estimate_tokens(f"【{title}】\n{content}") + _SECTION_OVERHEAD


def _fit_section(title: str, content: str, limit: int) -> str:
    """把分区内容裁剪到严格不超过 limit 个估算 token 的最长前缀。

    逐字符二分，estimate_tokens 对前缀单调不减，因此结果可保证不超预算。
    """
    if limit <= 0 or not content:
        return ""
    if _section_cost(title, content) <= limit:
        return content
    lo, hi = 0, len(content)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _section_cost(title, content[:mid]) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return content[:lo]


class _Section:
    def __init__(self, key: str, title: str, priority: int, required: bool = False):
        self.key = key
        self.title = title
        self.priority = priority
        self.required = required  # 必需分区：超预算时也尽量保留（截断而非剔除）
        self.lines: list[str] = []

    @property
    def content(self) -> str:
        return "\n".join(self.lines)

    @property
    def item_count(self) -> int:
        return len(self.lines)


def _fetch_novel(conn, novel_id: str):
    row = conn.execute(
        "SELECT * FROM novels WHERE id = ?", (novel_id,)
    ).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")
    return row


def build_context(
    novel_id: str,
    *,
    task_type: str = "writer",
    chapter_id: str | None = None,
    character_ids: list[str] | None = None,
    token_budget: int | None = None,
    pov: str = "author",
    user_requirement: str = "",
    extra_sections: list[dict] | None = None,
    exclude_sections: list[str] | None = None,
) -> dict:
    """组装上下文。

    extra_sections：调用方提供的额外分区，元素形如
    {"key", "title", "content", "priority", "required"}，与内置分区一起
    参与同一 token 预算竞争（例如 P4.1.3 把当前章节正文作为高优先级
    必需分区注入，保证正文优先于非必要历史信息保留）。

    exclude_sections：需要从内置分区中剔除的分区 key 列表，
    用于快速写作的「最近章节 / 自定义」上下文模式。
    剔除发生在预算分配之前，不会占用 token。
    """
    if pov not in _POVS:
        raise ServiceError(400, "不支持的视角类型")
    settings = get_settings()
    budget = int(token_budget or settings.ai_context_token_budget)
    budget = max(200, min(budget, 200_000))

    warnings: list[str] = []
    omitted_sections: list[dict] = []
    excluded = {
        str(item).strip() for item in (exclude_sections or []) if str(item).strip()
    }

    with get_connection() as conn:
        novel = _fetch_novel(conn, novel_id)
        sections = _collect_sections(
            conn, novel, chapter_id=chapter_id, character_ids=character_ids,
            pov=pov, user_requirement=user_requirement, warnings=warnings,
        )
        if excluded:
            sections = [section for section in sections if section.key not in excluded]

    for item in extra_sections or []:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        section = _Section(
            str(item.get("key") or "extra"),
            str(item.get("title") or "补充上下文"),
            int(item.get("priority") or 50),
            bool(item.get("required")),
        )
        section.lines.append(content)
        sections.append(section)

    # 按优先级从高到低纳入预算；每次都用“最终文本写法”精确计费，
    # 因此区内截断后不会再出现总预算超限
    ordered = sorted(sections, key=lambda s: s.priority, reverse=True)
    included: list[_Section] = []
    used = 0
    for section in ordered:
        if not section.lines:
            continue
        remaining = budget - used
        if remaining <= 0:
            omitted_sections.append(
                {"key": section.key, "title": section.title,
                 "reason": "budget", "dropped_items": section.item_count}
            )
            warnings.append(
                f"分区「{section.title}」因预算已用尽被整体省略"
                + ("（该分区为必需分区，请提高 token 预算）" if section.required else "")
            )
            continue

        cost = _section_cost(section.title, section.content)
        if cost <= remaining:
            included.append(section)
            used += cost
            continue

        # 超预算：先尝试按行截断（从分区尾部丢弃低优先级条目）
        kept: list[str] = []
        for line in section.lines:
            candidate = kept + [line]
            if _section_cost(section.title, "\n".join(candidate)) <= remaining:
                kept = candidate
            else:
                break
        if kept:
            dropped = len(section.lines) - len(kept)
            section.lines = kept
            section_content = section.content
            included.append(section)
            used += _section_cost(section.title, section_content)
            warnings.append(
                f"分区「{section.title}」超出预算，已截断 {dropped} 条内容"
            )
            omitted_sections.append(
                {"key": section.key, "title": section.title,
                 "reason": "budget", "dropped_items": dropped}
            )
            continue

        # 单行也放不下：必需分区裁剪到严格符合剩余预算的头部，否则整体剔除
        if section.required:
            head = _fit_section(section.title, section.content, remaining)
            if head.strip():
                total_items = section.item_count
                section.lines = [head]
                content = section.content
                included.append(section)
                used += _section_cost(section.title, content)
                warnings.append(
                    f"必需分区「{section.title}」超出预算，已截断保留开头内容"
                )
                omitted_sections.append(
                    {"key": section.key, "title": section.title,
                     "reason": "budget", "dropped_items": total_items}
                )
                continue
        omitted_sections.append(
            {"key": section.key, "title": section.title,
             "reason": "budget", "dropped_items": section.item_count}
        )
        warnings.append(f"分区「{section.title}」因预算不足被整体省略")

    # 输出顺序与拼接顺序一致：优先级从高到低
    included.sort(key=lambda s: s.priority, reverse=True)

    def _render() -> str:
        return "\n\n".join(f"【{s.title}】\n{s.content}" for s in included)

    # 兜底校验：估算值必须基于最终实际输出；若仍超预算则从最低优先级分区开始剔除
    context_text = _render()
    estimated_tokens = estimate_tokens(context_text)
    while included and estimated_tokens > budget:
        dropped_section = included.pop()
        omitted_sections.append(
            {"key": dropped_section.key, "title": dropped_section.title,
             "reason": "budget", "dropped_items": dropped_section.item_count}
        )
        warnings.append(f"分区「{dropped_section.title}」因预算不足被整体省略")
        context_text = _render()
        estimated_tokens = estimate_tokens(context_text)

    return {
        "context_text": context_text,
        "sections": [
            {
                "key": s.key,
                "title": s.title,
                "content": s.content,
                "tokens": _section_cost(s.title, s.content),
                "estimated": True,
                "included": True,
                "item_count": s.item_count,
                "priority": s.priority,
            }
            for s in included
        ],
        "estimated_tokens": estimated_tokens,
        "token_budget": budget,
        "omitted_sections": omitted_sections,
        "warnings": warnings,
    }


def _collect_sections(
    conn,
    novel,
    *,
    chapter_id: str | None,
    character_ids: list[str] | None,
    pov: str,
    user_requirement: str,
    warnings: list[str],
) -> list[_Section]:
    novel_id = novel["id"]
    sections: list[_Section] = []

    # 1. 核心设定：小说信息 + 世界观概要
    core = _Section("core_settings", "核心设定", priority=100, required=True)
    core.lines.append(
        f"小说：《{novel['title']}》"
        + (f"（{novel['genre']}）" if novel["genre"] else "")
        + f"，状态：{novel['status']}，目标字数：{novel['target_word_count']}"
    )
    if novel["description"]:
        core.lines.append(f"简介：{_truncate(novel['description'], 200)}")
    entries = conn.execute(
        """
        SELECT e.name, e.summary, c.name AS category_name
          FROM world_entries e
          JOIN world_categories c ON c.id = e.category_id
         WHERE e.novel_id = ?
         ORDER BY c.sort_order ASC, e.sort_order ASC
         LIMIT ?
        """,
        (novel_id, _MAX_WORLD_ENTRIES),
    ).fetchall()
    if entries:
        core.lines.append("世界观要点：")
        for entry in entries:
            line = f"- [{entry['category_name']}] {entry['name']}"
            if entry["summary"]:
                line += f"：{_truncate(entry['summary'], 80)}"
            core.lines.append(line)
    relations = conn.execute(
        """
        SELECT r.relation_type, s.name AS source_name, t.name AS target_name
          FROM world_relations r
          JOIN world_entries s ON s.id = r.source_entry_id
          JOIN world_entries t ON t.id = r.target_entry_id
         WHERE r.novel_id = ?
         ORDER BY r.created_at ASC
         LIMIT ?
        """,
        (novel_id, _MAX_WORLD_RELATIONS),
    ).fetchall()
    for rel in relations:
        core.lines.append(f"- 关系：{rel['source_name']} —{rel['relation_type']}→ {rel['target_name']}")
    sections.append(core)

    # 2. 当前任务
    task = _Section("current_task", "当前任务", priority=95, required=True)
    if chapter_id:
        chapter = conn.execute(
            "SELECT * FROM chapters WHERE id = ? AND novel_id = ?",
            (chapter_id, novel_id),
        ).fetchone()
        if chapter is None:
            raise ServiceError(404, "章节不存在")
        task.lines.append(
            f"当前章节：第 {chapter['chapter_number']} 章《{chapter['title']}》"
            f"（状态：{chapter['status']}）"
        )
        if chapter["summary"]:
            task.lines.append(f"章节摘要：{_truncate(chapter['summary'], 200)}")
    if user_requirement.strip():
        task.lines.append(f"创作要求：{_truncate(user_requirement, 500)}")
    if task.lines:
        sections.append(task)

    # 3. 当前人物
    characters = _Section("characters", "当前人物", priority=90)
    char_rows = _select_characters(conn, novel_id, character_ids)
    for row in char_rows:
        line = f"- {row['name']}"
        if row["role"]:
            line += f"（{row['role']}）"
        if row["identity"]:
            line += f"，身份：{_truncate(row['identity'], 40)}"
        characters.lines.append(line)
        if row["personality"]:
            characters.lines.append(f"  性格：{_truncate(row['personality'], 100)}")
        if row["background"]:
            characters.lines.append(f"  背景：{_truncate(row['background'], 120)}")
    if characters.lines:
        sections.append(characters)

    # 4. 人物状态
    states = _Section("character_states", "人物当前状态", priority=85)
    char_ids = [row["id"] for row in char_rows]
    if char_ids:
        placeholders = ", ".join("?" for _ in char_ids)
        state_rows = conn.execute(
            f"""
            SELECT s.life_status, s.current_location, s.current_faction,
                   s.current_cultivation, s.health_status, s.emotional_state,
                   s.current_goal, c.name
              FROM character_states s
              JOIN characters c ON c.id = s.character_id
             WHERE c.novel_id = ? AND s.character_id IN ({placeholders})
            """,
            [novel_id] + char_ids,
        ).fetchall()
        for state in state_rows:
            parts = [f"- {state['name']}：{state['life_status']}"]
            if state["current_location"]:
                parts.append(f"位于{state['current_location']}")
            if state["current_cultivation"]:
                parts.append(f"修为{state['current_cultivation']}")
            if state["current_goal"]:
                parts.append(f"目标：{_truncate(state['current_goal'], 60)}")
            states.lines.append("，".join(parts))
    if states.lines:
        sections.append(states)

    # 5. 人物关系
    relations = _Section("character_relations", "人物关系", priority=80)
    rel_rows = conn.execute(
        """
        SELECT r.relation_type, r.strength, s.name AS source_name, t.name AS target_name
          FROM character_relations r
          JOIN characters s ON s.id = r.source_character_id
          JOIN characters t ON t.id = r.target_character_id
         WHERE r.novel_id = ? AND r.status = 'active'
         ORDER BY r.updated_at DESC
         LIMIT ?
        """,
        (novel_id, _MAX_RELATIONS),
    ).fetchall()
    for rel in rel_rows:
        line = f"- {rel['source_name']} → {rel['target_name']}：{rel['relation_type']}"
        if rel["strength"] is not None:
            line += f"（强度 {rel['strength']:g}）"
        relations.lines.append(line)
    rel_events = conn.execute(
        """
        SELECT e.event_type, e.title, e.story_time
          FROM character_relation_events e
         WHERE e.novel_id = ?
         ORDER BY e.created_at DESC, e.sequence DESC
         LIMIT ?
        """,
        (novel_id, _MAX_RELATION_EVENTS),
    ).fetchall()
    if rel_events:
        relations.lines.append("近期关系变化：")
        for event in reversed(rel_events):
            line = f"- {event['title'] or event['event_type']}"
            if event["story_time"]:
                line += f"（故事时间：{event['story_time']}）"
            relations.lines.append(line)
    if relations.lines:
        sections.append(relations)

    # 6. 人物秘密（仅作者视角；叙事/角色视角严格隔离）
    if pov == "author":
        secrets = _Section("character_secrets", "人物秘密（仅作者可见）", priority=75)
        if char_ids:
            placeholders = ", ".join("?" for _ in char_ids)
            secret_rows = conn.execute(
                f"""
                SELECT s.title, s.content, s.secrecy_level, c.name AS character_name
                  FROM character_secrets s
                  JOIN characters c ON c.id = s.character_id
                 WHERE c.novel_id = ? AND s.character_id IN ({placeholders})
                 ORDER BY s.updated_at DESC
                 LIMIT ?
                """,
                [novel_id] + char_ids + [_MAX_SECRETS],
            ).fetchall()
            for secret in secret_rows:
                secrets.lines.append(
                    f"- [{secret['character_name']}] {secret['title']}"
                    f"（{secret['secrecy_level']}）：{_truncate(secret['content'], 100)}"
                )
        if secrets.lines:
            sections.append(secrets)
    elif pov == "character":
        warnings.append(
            "角色视角知识状态系统尚未实现：本阶段不向上下文注入任何人物秘密，"
            "待后续版本提供逐角色知识过滤"
        )

    # 7. 剧情历史：最近事件 + 已完成章节摘要（绝不注入全部正文）
    history = _Section("plot_history", "剧情历史", priority=70)
    event_rows = conn.execute(
        """
        SELECT title, story_time, description, importance
          FROM plot_events
         WHERE novel_id = ?
         ORDER BY sequence ASC, created_at ASC
         LIMIT ?
        """,
        (novel_id, _MAX_PLOT_EVENTS),
    ).fetchall()
    if event_rows:
        history.lines.append("近期剧情事件：")
        for event in event_rows:
            line = f"- {event['title']}"
            if event["story_time"]:
                line += f"（{event['story_time']}）"
            if event["description"]:
                line += f"：{_truncate(event['description'], 80)}"
            history.lines.append(line)
    chapter_rows = conn.execute(
        """
        SELECT chapter_number, title, summary
          FROM chapters
         WHERE novel_id = ? AND status = 'completed' AND summary != ''
         ORDER BY chapter_number DESC
         LIMIT ?
        """,
        (novel_id, _MAX_CHAPTER_SUMMARIES),
    ).fetchall()
    if chapter_rows:
        history.lines.append("已完成章节摘要：")
        for chapter in reversed(chapter_rows):
            history.lines.append(
                f"- 第 {chapter['chapter_number']} 章《{chapter['title']}》："
                f"{_truncate(chapter['summary'], 100)}"
            )
    if chapter_id:
        chapter_events = conn.execute(
            """
            SELECT title, story_time, description
              FROM plot_events
             WHERE novel_id = ? AND chapter_id = ?
             ORDER BY sequence ASC, created_at ASC
            """,
            (novel_id, chapter_id),
        ).fetchall()
        if chapter_events:
            history.lines.append("本章关联事件：")
            for event in chapter_events:
                history.lines.append(
                    f"- {event['title']}：{_truncate(event['description'], 80)}"
                )
    if history.lines:
        sections.append(history)

    return sections


def _select_characters(conn, novel_id: str, character_ids: list[str] | None):
    """按指定 ID 或默认排序选取人物，所有查询都做小说隔离。"""
    if character_ids:
        placeholders = ", ".join("?" for _ in character_ids)
        rows = conn.execute(
            f"SELECT * FROM characters WHERE novel_id = ? AND id IN ({placeholders})"
            " ORDER BY sort_order ASC, created_at ASC",
            [novel_id] + list(character_ids),
        ).fetchall()
        found = {row["id"] for row in rows}
        missing = [cid for cid in character_ids if cid not in found]
        if missing:
            raise ServiceError(404, "人物不存在或不属于当前小说")
        return rows
    return conn.execute(
        "SELECT * FROM characters WHERE novel_id = ?"
        " ORDER BY sort_order ASC, created_at ASC LIMIT ?",
        (novel_id, _MAX_CHARACTERS),
    ).fetchall()
