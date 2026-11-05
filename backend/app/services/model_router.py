"""ModelRouter：按任务类型选择模型。

本阶段只负责“找到配置”，不做真正的生成调用。
未配置专属模型、或专属模型已被停用/删除时，回退到全局默认模型。
后续小说生成功能应通过本模块获取模型，而不直接查询数据库。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..adapters.base import BaseAdapter
from ..core.config import get_settings
from ..core.security import decrypt_api_key
from ..database.db import DEFAULT_TASK_KEY, TASK_KEYS, get_connection
from ..adapters import factory


@dataclass
class ResolvedModel:
    task: str
    model_row_id: str
    model_identifier: str
    provider_id: str
    provider_type: str
    base_url: str
    resolved_from: str  # "task" 或 "default"
    api_key_encrypted: str | None


def _model_with_provider(model_id: str) -> ResolvedModel | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT m.id, m.model_id, m.enabled AS model_enabled,
                   p.id AS provider_id, p.provider_type, p.base_url,
                   p.enabled AS provider_enabled, p.api_key_encrypted
            FROM models m
            JOIN providers p ON p.id = m.provider_id
            WHERE m.id = ?
            """,
            (model_id,),
        ).fetchone()
    if row is None or not row["model_enabled"] or not row["provider_enabled"]:
        return None
    return ResolvedModel(
        task="",
        model_row_id=row["id"],
        model_identifier=row["model_id"],
        provider_id=row["provider_id"],
        provider_type=row["provider_type"],
        base_url=row["base_url"],
        resolved_from="",
        api_key_encrypted=row["api_key_encrypted"],
    )


def _stored(task: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT model_id FROM task_model_settings WHERE task = ?", (task,)
        ).fetchone()
    return row["model_id"] if row else None


def resolve_model_for_task(task: str) -> ResolvedModel | None:
    """按任务解析模型；找不到可用模型时返回 None。"""
    if task not in TASK_KEYS:
        raise ValueError(f"不支持的任务类型：{task}")

    task_model_id = _stored(task)
    if task_model_id:
        resolved = _model_with_provider(task_model_id)
        if resolved:
            resolved.task = task
            resolved.resolved_from = "task"
            return resolved

    default_model_id = _stored(DEFAULT_TASK_KEY)
    if default_model_id:
        resolved = _model_with_provider(default_model_id)
        if resolved:
            resolved.task = task
            resolved.resolved_from = "default"
            return resolved
    return None


def resolve_model_by_id(model_row_id: str, task: str) -> ResolvedModel | None:
    """显式指定模型的路由解析（不解密密钥，仅用于预览与校验）。"""
    resolved = _model_with_provider(model_row_id)
    if resolved is None:
        return None
    resolved.task = task
    resolved.resolved_from = "explicit"
    return resolved


def _build_adapter(resolved: ResolvedModel) -> tuple[BaseAdapter, ResolvedModel] | None:
    if not resolved.api_key_encrypted:
        return None
    api_key = decrypt_api_key(resolved.api_key_encrypted)
    if not api_key:
        return None
    adapter = factory.create_adapter(
        resolved.provider_type,
        resolved.base_url,
        api_key,
        get_settings().model_request_timeout,
    )
    return adapter, resolved


def build_adapter_for_task(task: str) -> tuple[BaseAdapter, ResolvedModel] | None:
    """为后续生成调用准备适配器（解密密钥仅发生在后端内存中）。"""
    resolved = resolve_model_for_task(task)
    if resolved is None:
        return None
    return _build_adapter(resolved)


def build_adapter_for_explicit(
    task: str, model_row_id: str
) -> tuple[BaseAdapter, ResolvedModel] | None:
    """本次调用显式指定的模型优先于任务配置；模型被停用/删除时返回 None。"""
    resolved = _model_with_provider(model_row_id)
    if resolved is None:
        return None
    resolved.task = task
    resolved.resolved_from = "explicit"
    return _build_adapter(resolved)
