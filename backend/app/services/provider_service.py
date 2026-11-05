"""Provider（API 服务商）业务逻辑。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from ..core.net_guard import UrlValidationError, validate_base_url
from ..core.security import encrypt_api_key, mask_api_key
from ..database.db import get_connection
from .errors import ServiceError

PROVIDER_TYPES = ("deepseek", "openai_compatible", "custom")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "provider_type": row["provider_type"],
        "base_url": row["base_url"],
        "enabled": bool(row["enabled"]),
        "has_api_key": bool(row["api_key_encrypted"]),
        # 仅返回脱敏状态，永不返回完整密钥
        "api_key_masked": row["api_key_hint"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_providers() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM providers ORDER BY created_at ASC"
        ).fetchall()
    return [_to_out(row) for row in rows]


def get_provider_row(provider_id: str) -> sqlite3.Row:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM providers WHERE id = ?", (provider_id,)
        ).fetchone()
    if row is None:
        raise ServiceError(404, "服务商不存在")
    return row


def get_provider(provider_id: str) -> dict:
    return _to_out(get_provider_row(provider_id))


def _clean_base_url(base_url: str) -> str:
    try:
        return validate_base_url(base_url)
    except UrlValidationError as exc:
        raise ServiceError(400, str(exc)) from exc


def create_provider(
    *,
    name: str,
    provider_type: str,
    base_url: str,
    api_key: str | None,
    enabled: bool,
) -> dict:
    if provider_type not in PROVIDER_TYPES:
        raise ServiceError(400, "不支持的服务商类型")

    base_url = _clean_base_url(base_url)
    normalized_key = (api_key or "").strip()
    encrypted = encrypt_api_key(normalized_key) if normalized_key else None
    hint = mask_api_key(normalized_key) if normalized_key else ""

    now = _now()
    provider_id = uuid4().hex
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO providers
                    (id, name, provider_type, base_url, api_key_encrypted,
                     api_key_hint, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider_id,
                    name.strip(),
                    provider_type,
                    base_url,
                    encrypted,
                    hint,
                    1 if enabled else 0,
                    now,
                    now,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ServiceError(409, "服务商名称已存在，请换一个名称") from exc

    return get_provider(provider_id)


def update_provider(
    provider_id: str,
    *,
    name: str | None = None,
    provider_type: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    enabled: bool | None = None,
) -> dict:
    row = get_provider_row(provider_id)

    fields: dict[str, object] = {}
    if name is not None:
        fields["name"] = name.strip()
    if provider_type is not None:
        if provider_type not in PROVIDER_TYPES:
            raise ServiceError(400, "不支持的服务商类型")
        fields["provider_type"] = provider_type
    if base_url is not None:
        fields["base_url"] = _clean_base_url(base_url)
    if enabled is not None:
        fields["enabled"] = 1 if enabled else 0
    # api_key 省略/None 表示不变；空字符串表示清除；其他表示更新
    if api_key is not None:
        normalized_key = api_key.strip()
        if normalized_key:
            fields["api_key_encrypted"] = encrypt_api_key(normalized_key)
            fields["api_key_hint"] = mask_api_key(normalized_key)
        else:
            fields["api_key_encrypted"] = None
            fields["api_key_hint"] = ""

    if not fields:
        return _to_out(row)

    fields["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [provider_id]

    try:
        with get_connection() as conn:
            conn.execute(
                f"UPDATE providers SET {assignments} WHERE id = ?", values
            )
    except sqlite3.IntegrityError as exc:
        raise ServiceError(409, "服务商名称已存在，请换一个名称") from exc

    return get_provider(provider_id)


def delete_provider(provider_id: str) -> dict:
    get_provider_row(provider_id)
    with get_connection() as conn:
        model_count = conn.execute(
            "SELECT COUNT(*) FROM models WHERE provider_id = ?", (provider_id,)
        ).fetchone()[0]
        # 外键 ON DELETE CASCADE 删除关联模型，
        # task_model_settings 中引用这些模型的配置会被置空
        conn.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
    return {"deleted": True, "deleted_models": model_count}
