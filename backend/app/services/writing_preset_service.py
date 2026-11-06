"""写作预设（P4.2）。

预设复用 prompt_templates 存储（is_preset=1），因此天然获得：
- 版本历史与恢复；
- 名称/描述/System Prompt 的既有校验；
- 与普通提示词模板在同一张表上的安全隔离。

预设不与任何模型绑定：同一预设可用于不同模型，方便比较文风差异。
按小说指定的预设保存在 app_settings（writing_preset:<novel_id>），
不改动小说表结构。
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..database.db import get_connection
from . import prompt_template_service
from .errors import ServiceError

PRESET_TASK_TYPE = "writer"
NOVEL_PRESET_KEY_PREFIX = "writing_preset:"

# 写作预设的文本字段（全部为自然语言，不做固定模板化限制）
_TEXT_FIELDS = (
    "writing_style",
    "narrative_perspective",
    "person",
    "language_style",
    "dialogue_style",
    "style_constraints",
    "extra_prompt",
    "relationship_background",
    "adult_narrative_style",
    "intensity",
    "conventions",
    "forbidden",
)

_FIELD_LABELS = (
    ("writing_style", "写作风格"),
    ("narrative_perspective", "叙事视角"),
    ("person", "人称"),
    ("language_style", "语言风格"),
    ("dialogue_style", "对话风格"),
    ("style_constraints", "文风限制"),
    ("extra_prompt", "其他要求"),
    ("adult_genres", "题材标签"),
    ("relationship_background", "角色关系与背景"),
    ("adult_narrative_style", "叙事风格"),
    ("intensity", "描写尺度"),
    ("conventions", "创作约定"),
    ("forbidden", "禁止出现的内容"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_config(config: dict | None) -> dict:
    if not isinstance(config, dict):
        config = {}
    out: dict[str, object] = {}
    for key in _TEXT_FIELDS:
        out[key] = str(config.get(key) or "").strip()
    genres = config.get("adult_genres") or []
    if isinstance(genres, str):
        genres = [item for item in genres.replace("，", ",").replace("、", ",").split(",")]
    if not isinstance(genres, list):
        genres = []
    cleaned: list[str] = []
    for item in genres:
        text = str(item or "").strip()
        if text and text not in cleaned:
            cleaned.append(text[:50])
    out["adult_genres"] = cleaned[:20]
    return out


def _preset_row(conn, preset_id: str):
    row = conn.execute(
        "SELECT * FROM prompt_templates WHERE id = ? AND is_preset = 1",
        (preset_id,),
    ).fetchone()
    if row is None:
        raise ServiceError(404, "写作预设不存在")
    return row


def _to_out(row) -> dict:
    data = prompt_template_service._to_out(row)
    return {
        "id": data["id"],
        "name": data["name"],
        "description": data["description"],
        "system_prompt": data["system_prompt"],
        "config": _normalize_config(data["preset_config"]),
        "version": data["version"],
        "is_active": data["is_active"],
        "is_default": data["is_default"],
        "variables": data["variables"],
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
    }


def list_presets(*, include_inactive: bool = True) -> list[dict]:
    rows = prompt_template_service.list_templates(
        PRESET_TASK_TYPE, include_inactive=include_inactive, include_presets=True
    )
    presets = [row for row in rows if row["is_preset"]]
    presets.sort(key=lambda row: (not row["is_default"], row["updated_at"]), reverse=True)
    return [_to_out(row) for row in presets]


def get_preset(preset_id: str) -> dict:
    with get_connection() as conn:
        return _to_out(_preset_row(conn, preset_id))


def create_preset(payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ServiceError(400, "预设名称不能为空")
    with get_connection() as conn:
        if payload.get("is_default"):
            conn.execute(
                "UPDATE prompt_templates SET is_default = 0 WHERE is_preset = 1"
            )
    return prompt_template_service.create_template(
        {
            "name": name,
            "task_type": PRESET_TASK_TYPE,
            "description": str(payload.get("description") or "").strip(),
            "system_prompt": str(payload.get("system_prompt") or ""),
            "user_prompt_template": "",
            "is_active": payload.get("is_active", True),
            "preset_config": _normalize_config(payload.get("config")),
            "is_preset": True,
            "is_default": bool(payload.get("is_default")),
        }
    ) | {"config": _normalize_config(payload.get("config"))}


def update_preset(preset_id: str, fields: dict) -> dict:
    with get_connection() as conn:
        _preset_row(conn, preset_id)
    mapped: dict[str, object] = {}
    if fields.get("name") is not None:
        name = str(fields["name"]).strip()
        if not name:
            raise ServiceError(400, "预设名称不能为空")
        mapped["name"] = name
    for key in ("description", "system_prompt"):
        if fields.get(key) is not None:
            mapped[key] = str(fields[key])
    if fields.get("is_active") is not None:
        mapped["is_active"] = bool(fields["is_active"])
    if fields.get("config") is not None:
        mapped["preset_config"] = _normalize_config(fields["config"])
    if not mapped:
        return get_preset(preset_id)
    prompt_template_service.update_template(preset_id, mapped)
    return get_preset(preset_id)


def copy_preset(preset_id: str, name: str | None = None) -> dict:
    source = get_preset(preset_id)
    copy_name = str(name or "").strip() or f"{source['name']}（副本）"
    if len(copy_name) > 100:
        copy_name = copy_name[:100]
    copied = create_preset(
        {
            "name": copy_name,
            "description": source["description"],
            "system_prompt": source["system_prompt"],
            "config": source["config"],
            "is_active": True,
            "is_default": False,
        }
    )
    return copied


def set_default_preset(preset_id: str) -> dict:
    with get_connection() as conn:
        row = _preset_row(conn, preset_id)
        if not row["is_active"]:
            raise ServiceError(400, "停用的预设不能设为默认")
        now = _now()
        conn.execute(
            "UPDATE prompt_templates SET is_default = 0 WHERE is_preset = 1 AND is_default = 1"
        )
        conn.execute(
            "UPDATE prompt_templates SET is_default = 1, updated_at = ? WHERE id = ?",
            (now, preset_id),
        )
    return get_preset(preset_id)


def delete_preset(preset_id: str) -> dict:
    with get_connection() as conn:
        _preset_row(conn, preset_id)
        # 清理按小说指定与该预设的关联，避免留下悬空引用
        conn.execute(
            "DELETE FROM app_settings WHERE key LIKE ? AND value = ?",
            (NOVEL_PRESET_KEY_PREFIX + "%", preset_id),
        )
    prompt_template_service.delete_template(preset_id)
    return {"deleted": True}


# ----------------------------- 按小说指定 -----------------------------

def _novel_preset_key(novel_id: str) -> str:
    return f"{NOVEL_PRESET_KEY_PREFIX}{novel_id}"


def _ensure_novel(conn, novel_id: str) -> None:
    row = conn.execute("SELECT id FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")


def get_novel_preset(novel_id: str) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (_novel_preset_key(novel_id),),
        ).fetchone()
        preset_id = (row["value"] if row else None) or None
    preset = None
    if preset_id:
        try:
            preset = get_preset(preset_id)
        except ServiceError:
            # 预设已被删除时视为未指定，不让小说配置报错
            preset = None
    return {"novel_id": novel_id, "preset_id": preset_id, "preset": preset}


def set_novel_preset(novel_id: str, preset_id: str | None) -> dict:
    with get_connection() as conn:
        _ensure_novel(conn, novel_id)
        key = _novel_preset_key(novel_id)
        if not preset_id:
            conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
        else:
            _preset_row(conn, preset_id)
            now = _now()
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE
                   SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, preset_id, now),
            )
    return get_novel_preset(novel_id)


# ----------------------------- 解析与提示词组装 -----------------------------

def resolve_preset(novel_id: str, preset_id: str | None = None) -> dict | None:
    """解析本次写作实际使用的预设。

    优先级：显式指定 > 小说指定 > 全局默认预设 > 无预设。
    显式指定但不可用时明确报错，不静默回退，避免用户误以为用了某个预设。
    """
    if preset_id:
        try:
            preset = get_preset(preset_id)
        except ServiceError as exc:
            raise ServiceError(400, "指定的写作预设不存在") from exc
        if not preset["is_active"]:
            raise ServiceError(400, "指定的写作预设已停用")
        return preset

    assigned = get_novel_preset(novel_id)
    if assigned["preset"] and assigned["preset"]["is_active"]:
        return assigned["preset"]

    for preset in list_presets(include_inactive=False):
        if preset["is_default"]:
            return preset
    return None


def build_system_prompt(preset: dict | None, overrides: dict | None = None) -> str:
    """把预设字段组装为 System Prompt。

    overrides 只作用于本次调用，不回写预设。
    """
    if not preset:
        return ""
    config = _normalize_config(preset.get("config"))
    for key, value in (overrides or {}).items():
        if key in _TEXT_FIELDS and value not in (None, ""):
            config[key] = str(value).strip()
        elif key == "adult_genres" and value:
            config["adult_genres"] = _normalize_config({"adult_genres": value})["adult_genres"]

    lines = [str(preset.get("system_prompt") or "").strip()]
    for key, label in _FIELD_LABELS:
        if key == "adult_genres":
            tags = config.get("adult_genres") or []
            if tags:
                lines.append(f"【{label}】{'、'.join(tags)}")
            continue
        value = str(config.get(key) or "").strip()
        if value:
            lines.append(f"【{label}】{value}")
    return "\n".join(line for line in lines if line)
