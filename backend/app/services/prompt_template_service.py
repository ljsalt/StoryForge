"""提示词模板管理：CRUD + 版本历史 + 安全渲染。

渲染安全：
- 变量形如 {name}（字母/下划线开头的标识符），只用字典查值做文本替换，
  不支持属性访问、索引、表达式，模板内容不可能执行任意代码；
- 渲染前校验所有必需变量都已提供，缺失即报错，
  绝不允许未替换的 {变量} 原样发送给模型。

版本管理：
- 创建模板即 v1 并写入版本快照；
- 每次更新版本号 +1 并写入新快照；
- restore 以旧版本内容生成一个新版本（历史不丢失）。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from ..database.db import AI_TASK_TYPES, get_connection
from .errors import ServiceError

_VAR_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def extract_variables(text: str) -> list[str]:
    """提取模板中的变量名（去重，保持出现顺序）。"""
    seen: list[str] = []
    for match in _VAR_PATTERN.finditer(text or ""):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def render_text(template: str, variables: dict[str, str]) -> str:
    """安全渲染：仅做 {name} 字典替换；缺失变量直接报错。"""
    required = extract_variables(template)
    missing = [name for name in required if name not in variables]
    if missing:
        raise ServiceError(400, "缺少必需的模板变量：" + "、".join(missing))

    def _sub(match: re.Match) -> str:
        return str(variables[match.group(1)])

    return _VAR_PATTERN.sub(_sub, template or "")


def _check_task_type(task_type: str) -> None:
    if task_type not in AI_TASK_TYPES:
        raise ServiceError(400, "不支持的任务类型")


def _parse_preset_config(value: str | None) -> dict:
    """解析预设配置；历史脏数据不应导致接口 500。"""
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _to_out(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "task_type": row["task_type"],
        "description": row["description"],
        "system_prompt": row["system_prompt"],
        "user_prompt_template": row["user_prompt_template"],
        "version": row["version"],
        "is_active": bool(row["is_active"]),
        "is_preset": bool(row["is_preset"]),
        "is_default": bool(row["is_default"]),
        "preset_config": _parse_preset_config(row["preset_config"]),
        "variables": extract_variables(
            (row["system_prompt"] or "") + "\n" + (row["user_prompt_template"] or "")
        ),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _template_row(conn, template_id: str):
    row = conn.execute(
        "SELECT * FROM prompt_templates WHERE id = ?", (template_id,)
    ).fetchone()
    if row is None:
        raise ServiceError(404, "提示词模板不存在")
    return row


def _snapshot(conn, template_row) -> None:
    conn.execute(
        """
        INSERT INTO prompt_template_versions
            (id, template_id, version, name, task_type, description,
             system_prompt, user_prompt_template, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid4().hex,
            template_row["id"],
            template_row["version"],
            template_row["name"],
            template_row["task_type"],
            template_row["description"],
            template_row["system_prompt"],
            template_row["user_prompt_template"],
            _now(),
        ),
    )


def list_templates(
    task_type: str | None = None,
    *,
    include_inactive: bool = False,
    include_presets: bool = False,
) -> list[dict]:
    if task_type and task_type.strip():
        _check_task_type(task_type.strip())
    sql = ["SELECT * FROM prompt_templates WHERE 1 = 1"]
    params: list[object] = []
    if not include_presets:
        # 写作预设和普通提示词模板共用一张表，但默认互相隔离：
        # 预设只在写作预设管理接口中出现，不污染原有模板列表。
        sql.append(" AND is_preset = 0")
    if task_type and task_type.strip():
        sql.append(" AND task_type = ?")
        params.append(task_type.strip())
    if not include_inactive:
        sql.append(" AND is_active = 1")
    sql.append(" ORDER BY updated_at DESC, created_at DESC")
    with get_connection() as conn:
        rows = conn.execute("\n".join(sql), params).fetchall()
    return [_to_out(row) for row in rows]


def get_template(template_id: str) -> dict:
    with get_connection() as conn:
        return _to_out(_template_row(conn, template_id))


def create_template(payload: dict) -> dict:
    task_type = str(payload.get("task_type") or "").strip()
    _check_task_type(task_type)
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ServiceError(400, "模板名称不能为空")
    now = _now()
    template_id = uuid4().hex
    preset_config = payload.get("preset_config")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO prompt_templates
                (id, name, task_type, description, system_prompt,
                 user_prompt_template, version, is_active, preset_config,
                 is_preset, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
            """,
            (
                template_id,
                name,
                task_type,
                str(payload.get("description") or "").strip(),
                str(payload.get("system_prompt") or ""),
                str(payload.get("user_prompt_template") or ""),
                1 if payload.get("is_active", True) else 0,
                json.dumps(preset_config, ensure_ascii=False)
                if isinstance(preset_config, dict) else "{}",
                1 if payload.get("is_preset") else 0,
                1 if payload.get("is_default") else 0,
                now,
                now,
            ),
        )
        _snapshot(conn, _template_row(conn, template_id))
    return get_template(template_id)


def update_template(template_id: str, fields: dict) -> dict:
    updates: dict[str, object] = {}
    with get_connection() as conn:
        row = _template_row(conn, template_id)
        if fields.get("name") is not None:
            name = str(fields["name"]).strip()
            if not name:
                raise ServiceError(400, "模板名称不能为空")
            updates["name"] = name
        if fields.get("task_type") is not None:
            _check_task_type(str(fields["task_type"]).strip())
            updates["task_type"] = str(fields["task_type"]).strip()
        for key in ("description", "system_prompt", "user_prompt_template"):
            if fields.get(key) is not None:
                updates[key] = str(fields[key])
        if fields.get("preset_config") is not None:
            config = fields["preset_config"]
            updates["preset_config"] = (
                json.dumps(config, ensure_ascii=False) if isinstance(config, dict) else "{}"
            )
        if fields.get("is_preset") is not None:
            updates["is_preset"] = 1 if fields["is_preset"] else 0
        if fields.get("is_default") is not None:
            updates["is_default"] = 1 if fields["is_default"] else 0
        if fields.get("is_active") is not None:
            updates["is_active"] = 1 if fields["is_active"] else 0
        if not updates:
            return _to_out(row)
        # 内容变更时递增版本号
        content_changed = any(
            key in updates
            for key in ("name", "task_type", "description",
                        "system_prompt", "user_prompt_template", "preset_config")
        )
        if content_changed:
            updates["version"] = int(row["version"]) + 1
        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE prompt_templates SET {assignments} WHERE id = ?",
            list(updates.values()) + [template_id],
        )
        if content_changed:
            _snapshot(conn, _template_row(conn, template_id))
    return get_template(template_id)


def delete_template(template_id: str) -> dict:
    with get_connection() as conn:
        _template_row(conn, template_id)
        # 版本快照通过 template_id 外键 CASCADE 一并清理
        conn.execute("DELETE FROM prompt_templates WHERE id = ?", (template_id,))
    return {"deleted": True}


def list_versions(template_id: str) -> list[dict]:
    with get_connection() as conn:
        _template_row(conn, template_id)
        rows = conn.execute(
            """
            SELECT * FROM prompt_template_versions
             WHERE template_id = ?
             ORDER BY version DESC
            """,
            (template_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "template_id": row["template_id"],
            "version": row["version"],
            "name": row["name"],
            "task_type": row["task_type"],
            "description": row["description"],
            "system_prompt": row["system_prompt"],
            "user_prompt_template": row["user_prompt_template"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def restore_version(template_id: str, version: int) -> dict:
    """以历史版本内容生成一个新版本（版本号继续递增，历史不丢失）。"""
    with get_connection() as conn:
        current = _template_row(conn, template_id)
        row = conn.execute(
            "SELECT * FROM prompt_template_versions WHERE template_id = ? AND version = ?",
            (template_id, version),
        ).fetchone()
        if row is None:
            raise ServiceError(404, "模板版本不存在")
        conn.execute(
            """
            UPDATE prompt_templates
               SET name = ?, task_type = ?, description = ?, system_prompt = ?,
                   user_prompt_template = ?, version = ?, updated_at = ?
             WHERE id = ?
            """,
            (
                row["name"],
                row["task_type"],
                row["description"],
                row["system_prompt"],
                row["user_prompt_template"],
                int(current["version"]) + 1,
                _now(),
                template_id,
            ),
        )
        _snapshot(conn, _template_row(conn, template_id))
    return get_template(template_id)


def render_template(template_id: str, variables: dict[str, str]) -> dict:
    """渲染校验：必需变量缺失时报 400，绝不放行未替换的变量。"""
    with get_connection() as conn:
        row = _template_row(conn, template_id)
    system_prompt = render_text(row["system_prompt"], variables)
    user_prompt = render_text(row["user_prompt_template"], variables)
    # 渲染后再次确认没有遗留的变量占位符
    leftovers = extract_variables(system_prompt + "\n" + user_prompt)
    if leftovers:
        raise ServiceError(400, "存在未替换的模板变量：" + "、".join(leftovers))
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "template_id": row["id"],
        "version": row["version"],
        "task_type": row["task_type"],
    }


def get_active_for_task(task_type: str) -> dict | None:
    _check_task_type(task_type)
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM prompt_templates
             WHERE task_type = ? AND is_active = 1 AND is_preset = 0
             ORDER BY updated_at DESC
             LIMIT 1
            """,
            (task_type,),
        ).fetchone()
    return _to_out(row) if row else None


# ---- 初始模板（仅在内置模板为空时播种，用户可自由修改） ----

_SEED_TEMPLATES = [
    {
        "name": "剧情导演基础模板",
        "task_type": "planner",
        "description": "根据小说上下文规划后续剧情走向（基础版，完整工作流后续阶段实现）",
        "system_prompt": (
            "你是一部长篇小说的剧情导演。你的职责是基于既有设定与剧情历史，"
            "提出合理、连贯、有张力的剧情规划建议。不得违背已确定的世界观、"
            "人物设定与已发生的故事事实。"
        ),
        "user_prompt_template": (
            "以下是小说的上下文资料：\n{context}\n\n"
            "请基于以上资料，为接下来的剧情提出规划建议。\n"
            "补充要求：{task}"
        ),
    },
    {
        "name": "正文作者基础模板",
        "task_type": "writer",
        "description": "根据上下文创作小说正文（基础版，完整工作流后续阶段实现）",
        "system_prompt": (
            "你是一部长篇小说的正文作者。你的文字风格稳定，严格遵循给定的世界观、"
            "人物设定与剧情走向。你只能使用上下文中提供的信息，"
            "不得编造与设定冲突的情节，不得让人物知道他们在故事中不可能知道的秘密。"
        ),
        "user_prompt_template": (
            "以下是小说的上下文资料：\n{context}\n\n"
            "请根据以上上下文创作正文内容。\n写作要求：{task}"
        ),
    },
    {
        "name": "连续性检查基础模板",
        "task_type": "editor",
        "description": "检查文本与既有设定的一致性（基础版，完整工作流后续阶段实现）",
        "system_prompt": (
            "你是一名严谨的小说连续性编辑。你负责检查给定文本与既有设定、"
            "人物状态、剧情时间线之间是否存在矛盾，并给出具体的修改建议。"
            "只报告确实存在的冲突，不要臆测。"
        ),
        "user_prompt_template": (
            "以下是小说的上下文资料：\n{context}\n\n"
            "请检查以下文本与设定是否一致，并列出所有冲突点：\n{text}"
        ),
    },
    {
        "name": "通用助手基础模板",
        "task_type": "assistant",
        "description": "摘要、命名、头脑风暴等普通辅助任务（基础版）",
        "system_prompt": (
            "你是一名中文小说写作助手，帮助作者完成摘要、命名、润色等辅助任务。"
            "回答应简洁、直接、可用。"
        ),
        "user_prompt_template": "{task}\n\n参考资料：\n{context}",
    },
]


def seed_default_templates() -> None:
    """首次启动时写入初始模板；已有任何模板时跳过（幂等）。"""
    with get_connection() as conn:
        existing = conn.execute("SELECT COUNT(*) AS n FROM prompt_templates").fetchone()
        if existing and int(existing["n"]) > 0:
            return
        now = _now()
        for item in _SEED_TEMPLATES:
            template_id = uuid4().hex
            conn.execute(
                """
                INSERT INTO prompt_templates
                    (id, name, task_type, description, system_prompt,
                     user_prompt_template, version, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
                """,
                (
                    template_id,
                    item["name"],
                    item["task_type"],
                    item["description"],
                    item["system_prompt"],
                    item["user_prompt_template"],
                    now,
                    now,
                ),
            )
            _snapshot(conn, _template_row(conn, template_id))
