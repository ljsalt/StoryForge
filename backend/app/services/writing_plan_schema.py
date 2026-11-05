"""剧情计划 JSON 结构定义与严格校验。

设计要点：
1. 模型返回的 JSON 必须真正通过本地校验，不能只信模型自称"格式正确"。
2. 校验失败时返回具体错误列表，供上层发起有限次数的修复请求。
3. 面对模型输出的轻微偏差（多包一层、列表元素是字符串等）做可预期的归一化，
   但结构缺失、类型错误、场景字段缺失一律判为不合法。
"""

from __future__ import annotations

import json
import re

# 供提示词与接口文档展示的计划结构说明
PLAN_SCHEMA = {
    "type": "object",
    "required": [
        "chapter_goal",
        "opening",
        "scenes",
        "character_actions",
        "conflicts",
        "plot_events",
        "foreshadowing",
        "ending",
        "estimated_word_count",
        "major_decisions",
    ],
    "properties": {
        "chapter_goal": {"type": "string", "description": "本章目标"},
        "opening": {"type": "string", "description": "开场"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "name",
                    "location",
                    "characters",
                    "purpose",
                    "actions",
                    "conflict",
                    "result",
                    "transition",
                ],
                "properties": {
                    "name": {"type": "string", "description": "场景名称"},
                    "location": {"type": "string", "description": "地点"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "purpose": {"type": "string", "description": "场景目的"},
                    "actions": {"type": "string", "description": "主要行动"},
                    "conflict": {"type": "string", "description": "冲突"},
                    "result": {"type": "string", "description": "场景结果"},
                    "transition": {"type": "string", "description": "与下一场景的衔接"},
                },
            },
        },
        "character_actions": {"type": "array", "items": {"type": "string"}},
        "conflicts": {"type": "array", "items": {"type": "string"}},
        "plot_events": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "description"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "foreshadowing": {"type": "array", "items": {"type": "string"}},
        "ending": {"type": "string", "description": "章节结尾"},
        "estimated_word_count": {"type": "integer", "minimum": 1},
        "major_decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "decision_id",
                    "title",
                    "description",
                    "context",
                    "options",
                    "recommended_option",
                    "consequences",
                    "is_required",
                ],
                "properties": {
                    "decision_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "context": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "recommended_option": {"type": ["string", "null"]},
                    "consequences": {"type": "string"},
                    "is_required": {"type": "boolean"},
                },
            },
        },
    },
}

SCENE_FIELDS = (
    "name",
    "location",
    "characters",
    "purpose",
    "actions",
    "conflict",
    "result",
    "transition",
)


class PlanValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("；".join(errors))
        self.errors = errors


def extract_json_object(text: str) -> dict:
    """从模型输出中提取第一个完整 JSON 对象，容忍代码块包裹与前后说明文字。"""
    raw = (text or "").strip()
    if not raw:
        raise PlanValidationError(["模型返回内容为空"])
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw, re.IGNORECASE)
    if fenced:
        raw = fenced.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanValidationError([f"JSON 解析失败：{exc.msg}（位置 {exc.pos}）"]) from exc
    if not isinstance(data, dict):
        raise PlanValidationError(["计划必须是一个 JSON 对象"])
    return data


def _as_text(value, field: str, errors: list[str], *, allow_empty: bool = True) -> str:
    if value is None:
        if allow_empty:
            return ""
        errors.append(f"{field} 不能为空")
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        errors.append(f"{field} 必须是字符串")
        return ""
    text = value.strip()
    if not allow_empty and not text:
        errors.append(f"{field} 不能为空")
    return text


def _as_text_list(value, field: str, errors: list[str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        errors.append(f"{field} 必须是数组")
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, dict):
            # 容忍 {name: ...} / {title: ...} 之类的对象写法
            text = str(
                item.get("name") or item.get("title") or item.get("content") or ""
            ).strip()
        elif isinstance(item, (str, int, float)) and not isinstance(item, bool):
            text = str(item).strip()
        else:
            errors.append(f"{field} 的元素必须是字符串")
            continue
        if text:
            out.append(text)
    return out


def _normalize_scenes(value, errors: list[str]) -> list[dict]:
    if not isinstance(value, list) or not value:
        errors.append("scenes 必须是非空数组")
        return []
    scenes: list[dict] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            errors.append(f"scenes[{index}] 必须是对象")
            continue
        scene: dict = {}
        for field in ("name", "location", "purpose", "actions", "conflict", "result", "transition"):
            scene[field] = _as_text(
                item.get(field), f"scenes[{index}].{field}", errors, allow_empty=False
            )
        scene["characters"] = _as_text_list(
            item.get("characters"), f"scenes[{index}].characters", errors
        )
        if not scene["characters"]:
            errors.append(f"scenes[{index}].characters 至少需要一个出场人物")
        scenes.append(scene)
    return scenes


def _normalize_plot_events(value, errors: list[str]) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append("plot_events 必须是数组")
        return []
    events: list[dict] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            title = _as_text(item.get("title"), f"plot_events[{index}].title", errors)
            description = _as_text(
                item.get("description"), f"plot_events[{index}].description", errors
            )
        elif isinstance(item, str):
            title, description = item.strip(), ""
        else:
            errors.append(f"plot_events[{index}] 必须是对象或字符串")
            continue
        if title:
            events.append({"title": title, "description": description})
        else:
            errors.append(f"plot_events[{index}].title 不能为空")
    return events


def _normalize_decisions(value, errors: list[str]) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append("major_decisions 必须是数组")
        return []
    decisions: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            errors.append(f"major_decisions[{index}] 必须是对象")
            continue
        key = _as_text(item.get("decision_id"), f"major_decisions[{index}].decision_id", errors)
        if not key:
            key = f"decision_{index}"
        if key in seen:
            errors.append(f"major_decisions 的 decision_id 重复：{key}")
            continue
        seen.add(key)
        options = _as_text_list(
            item.get("options"), f"major_decisions[{index}].options", errors
        )
        if not options:
            errors.append(f"major_decisions[{index}].options 至少需要一个选项")
        recommended = _as_text(
            item.get("recommended_option"),
            f"major_decisions[{index}].recommended_option",
            errors,
        )
        if recommended and recommended not in options:
            errors.append(
                f"major_decisions[{index}].recommended_option 必须是 options 中的一项"
            )
        is_required = item.get("is_required", False)
        if not isinstance(is_required, bool):
            errors.append(f"major_decisions[{index}].is_required 必须是布尔值")
            is_required = False
        decisions.append(
            {
                "decision_id": key,
                "title": _as_text(
                    item.get("title"), f"major_decisions[{index}].title", errors,
                    allow_empty=False,
                ),
                "description": _as_text(
                    item.get("description"), f"major_decisions[{index}].description", errors
                ),
                "context": _as_text(
                    item.get("context"), f"major_decisions[{index}].context", errors
                ),
                "options": options,
                "recommended_option": recommended or None,
                "consequences": _as_text(
                    item.get("consequences"), f"major_decisions[{index}].consequences", errors
                ),
                "is_required": bool(is_required),
            }
        )
    return decisions


def validate_plan(data: dict) -> dict:
    """校验并归一化计划；不合法时抛出 PlanValidationError。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        raise PlanValidationError(["计划必须是一个 JSON 对象"])

    chapter_goal = _as_text(
        data.get("chapter_goal"), "chapter_goal", errors, allow_empty=False
    )
    opening = _as_text(data.get("opening"), "opening", errors, allow_empty=False)
    ending = _as_text(data.get("ending"), "ending", errors, allow_empty=False)
    scenes = _normalize_scenes(data.get("scenes"), errors)
    character_actions = _as_text_list(
        data.get("character_actions"), "character_actions", errors
    )
    conflicts = _as_text_list(data.get("conflicts"), "conflicts", errors)
    plot_events = _normalize_plot_events(data.get("plot_events"), errors)
    foreshadowing = _as_text_list(data.get("foreshadowing"), "foreshadowing", errors)
    decisions = _normalize_decisions(data.get("major_decisions"), errors)

    raw_count = data.get("estimated_word_count")
    if isinstance(raw_count, bool) or not isinstance(raw_count, (int, float)):
        errors.append("estimated_word_count 必须是正整数")
        estimated = 0
    else:
        estimated = int(raw_count)
        if estimated <= 0:
            errors.append("estimated_word_count 必须大于 0")

    if errors:
        raise PlanValidationError(errors)

    return {
        "chapter_goal": chapter_goal,
        "opening": opening,
        "scenes": scenes,
        "character_actions": character_actions,
        "conflicts": conflicts,
        "plot_events": plot_events,
        "foreshadowing": foreshadowing,
        "ending": ending,
        "estimated_word_count": estimated,
        "major_decisions": decisions,
    }
