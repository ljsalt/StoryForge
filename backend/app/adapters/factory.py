"""适配器工厂：根据服务商类型创建统一适配器实例。"""

from __future__ import annotations

from .base import BaseAdapter
from .deepseek import DeepSeekAdapter
from .openai_compatible import OpenAICompatibleAdapter


def create_adapter(
    provider_type: str, base_url: str, api_key: str, timeout: float = 20.0
) -> BaseAdapter:
    if provider_type == "deepseek":
        return DeepSeekAdapter(base_url=base_url, api_key=api_key, timeout=timeout)
    return OpenAICompatibleAdapter(base_url=base_url, api_key=api_key, timeout=timeout)
