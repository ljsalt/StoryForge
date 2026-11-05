"""Model（模型）业务逻辑、连接测试与任务模型分配配置。"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from uuid import uuid4

from ..adapters import factory
from ..adapters.base import (
    ERROR_INVALID_KEY,
    ERROR_INVALID_URL,
    ERROR_MISSING_KEY,
    ERROR_MODEL_NOT_FOUND,
    ERROR_NOT_SUPPORTED,
    ERROR_SERVER,
    AdapterError,
    ChatMessage,
    ChatRequest,
)
from ..core.config import get_settings
from ..core.net_guard import UrlValidationError, validate_base_url
from ..core.security import decrypt_api_key, sanitize_text
from ..database.db import DEFAULT_TASK_KEY, TASK_KEYS, get_connection
from .errors import ServiceError

MODEL_SELECT = """
SELECT m.*, p.name AS provider_name, p.provider_type AS provider_type
FROM models m
JOIN providers p ON p.id = m.provider_id
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "provider_id": row["provider_id"],
        "provider_name": row["provider_name"],
        "provider_type": row["provider_type"],
        "name": row["name"],
        "model_id": row["model_id"],
        "remark": row["remark"],
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_models(provider_id: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if provider_id:
            rows = conn.execute(
                MODEL_SELECT + " WHERE m.provider_id = ? ORDER BY m.created_at ASC",
                (provider_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                MODEL_SELECT + " ORDER BY m.created_at ASC"
            ).fetchall()
    return [_to_out(row) for row in rows]


def _fetch_model_row(model_row_id: str) -> sqlite3.Row:
    with get_connection() as conn:
        row = conn.execute(
            MODEL_SELECT + " WHERE m.id = ?", (model_row_id,)
        ).fetchone()
    if row is None:
        raise ServiceError(404, "模型不存在")
    return row


def _ensure_provider(provider_id: str) -> None:
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM providers WHERE id = ?", (provider_id,)
        ).fetchone()
    if exists is None:
        raise ServiceError(400, "所属服务商不存在，请先创建服务商")


def create_model(
    *,
    provider_id: str,
    name: str,
    model_id: str,
    remark: str = "",
    enabled: bool = True,
) -> dict:
    _ensure_provider(provider_id)
    now = _now()
    row_id = uuid4().hex
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO models
                    (id, provider_id, name, model_id, remark, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    provider_id,
                    name.strip(),
                    model_id.strip(),
                    remark.strip(),
                    1 if enabled else 0,
                    now,
                    now,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ServiceError(409, "该服务商下已存在相同模型标识符") from exc
    return _to_out(_fetch_model_row(row_id))


def update_model(
    model_row_id: str,
    *,
    provider_id: str | None = None,
    name: str | None = None,
    model_id: str | None = None,
    remark: str | None = None,
    enabled: bool | None = None,
) -> dict:
    row = _fetch_model_row(model_row_id)

    fields: dict[str, object] = {}
    if provider_id is not None:
        _ensure_provider(provider_id)
        fields["provider_id"] = provider_id
    if name is not None:
        fields["name"] = name.strip()
    if model_id is not None:
        fields["model_id"] = model_id.strip()
    if remark is not None:
        fields["remark"] = remark.strip()
    if enabled is not None:
        fields["enabled"] = 1 if enabled else 0

    if not fields:
        return _to_out(row)

    fields["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [model_row_id]

    try:
        with get_connection() as conn:
            conn.execute(f"UPDATE models SET {assignments} WHERE id = ?", values)
    except sqlite3.IntegrityError as exc:
        raise ServiceError(409, "该服务商下已存在相同模型标识符") from exc
    return _to_out(_fetch_model_row(model_row_id))


def delete_model(model_row_id: str) -> dict:
    _fetch_model_row(model_row_id)
    with get_connection() as conn:
        # task_model_settings 中引用该模型的任务会通过外键 ON DELETE SET NULL 自动置空
        conn.execute("DELETE FROM models WHERE id = ?", (model_row_id,))
    return {"deleted": True}


def get_model_settings() -> dict:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT task, model_id FROM task_model_settings"
        ).fetchall()
    stored = {row["task"]: row["model_id"] for row in rows}
    return {
        "tasks": [
            {"task": task, "model_id": stored.get(task)} for task in TASK_KEYS
        ],
        "default_model_id": stored.get(DEFAULT_TASK_KEY),
    }


def update_model_settings(
    tasks: dict[str, str | None], default_model_id: str | None
) -> dict:
    known_ids = {row["id"] for row in list_models()}
    for task, model_id in tasks.items():
        if task not in TASK_KEYS:
            raise ServiceError(400, f"不支持的任务类型：{task}")
        if model_id and model_id not in known_ids:
            raise ServiceError(400, "所选模型不存在，请刷新后重试")
    if default_model_id and default_model_id not in known_ids:
        raise ServiceError(400, "默认模型不存在，请刷新后重试")

    now = _now()
    with get_connection() as conn:
        for task, model_id in tasks.items():
            conn.execute(
                """
                INSERT INTO task_model_settings (task, model_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(task) DO UPDATE SET
                    model_id = excluded.model_id,
                    updated_at = excluded.updated_at
                """,
                (task, model_id or None, now),
            )
        if default_model_id:
            conn.execute(
                """
                INSERT INTO task_model_settings (task, model_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(task) DO UPDATE SET
                    model_id = excluded.model_id,
                    updated_at = excluded.updated_at
                """,
                (DEFAULT_TASK_KEY, default_model_id, now),
            )
    return get_model_settings()


async def test_model_connection(model_row_id: str) -> dict:
    """测试模型连通性。

    先尝试服务商的模型列表接口（通常不产生费用），
    服务商不支持时再使用 max_tokens=1 的最小对话请求。
    """
    model = _fetch_model_row(model_row_id)
    provider = None
    with get_connection() as conn:
        provider = conn.execute(
            "SELECT * FROM providers WHERE id = ?", (model["provider_id"],)
        ).fetchone()
    if provider is None:
        raise ServiceError(404, "模型所属服务商不存在")

    settings = get_settings()
    base_url = provider["base_url"]
    try:
        validate_base_url(base_url)
    except UrlValidationError as exc:
        return _failure(model, ERROR_INVALID_URL, str(exc), 0, "none")

    if not provider["api_key_encrypted"]:
        return _failure(
            model, ERROR_MISSING_KEY, "该服务商尚未配置 API Key，请先填写后再测试", 0, "none"
        )

    api_key = decrypt_api_key(provider["api_key_encrypted"])
    if not api_key:
        return _failure(
            model,
            ERROR_INVALID_KEY,
            "API Key 无法解密（加密主密钥可能已更换），请重新填写 API Key",
            0,
            "none",
        )

    adapter = factory.create_adapter(
        provider["provider_type"], base_url, api_key, settings.model_request_timeout
    )
    started = time.perf_counter()

    try:
        listed = await adapter.list_models()
        latency = int((time.perf_counter() - started) * 1000)
        if model["model_id"] not in listed:
            message = (
                f"模型标识符 {model['model_id']} 不在服务商返回的模型列表中"
                f"（服务商共返回 {len(listed)} 个模型）"
            )
            return _failure(model, ERROR_MODEL_NOT_FOUND, message, latency, "models")
        return {
            "success": True,
            "latency_ms": latency,
            "method": "models",
            "error_code": None,
            "message": f"连接成功，模型标识符校验通过（服务商返回 {len(listed)} 个模型）",
            "model_identifier": model["model_id"],
        }
    except AdapterError as exc:
        latency = int((time.perf_counter() - started) * 1000)
        if exc.code != ERROR_NOT_SUPPORTED:
            return _failure(model, exc.code, exc.message, latency, "models")

    # 服务商不支持模型列表：改用最小输出长度的对话请求
    probe = ChatRequest(
        model=model["model_id"],
        messages=[ChatMessage(role="user", content="ping")],
        temperature=0,
        max_tokens=1,
    )
    probe_started = time.perf_counter()
    try:
        result = await adapter.chat(probe)
        latency = int((time.perf_counter() - probe_started) * 1000)
        return {
            "success": True,
            "latency_ms": latency,
            "method": "chat",
            "error_code": None,
            "message": (
                "连接成功（使用最小对话请求验证，可能产生少量 API 费用）"
                f"，返回模型：{result.model}"
            ),
            "model_identifier": model["model_id"],
        }
    except AdapterError as exc:
        latency = int((time.perf_counter() - probe_started) * 1000)
        return _failure(model, exc.code, exc.message, latency, "chat")
    except Exception as exc:  # 兜底：不泄露内部细节与密钥
        latency = int((time.perf_counter() - probe_started) * 1000)
        return _failure(
            model,
            ERROR_SERVER,
            sanitize_text(f"测试失败：{exc.__class__.__name__}", api_key),
            latency,
            "chat",
        )
    finally:
        await adapter.close()


def _failure(
    model: sqlite3.Row, code: str, message: str, latency_ms: int, method: str
) -> dict:
    return {
        "success": False,
        "latency_ms": latency_ms,
        "method": method,
        "error_code": code,
        "message": message,
        "model_identifier": model["model_id"],
    }
