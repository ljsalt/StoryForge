"""DeepSeek 官方 API 适配器。

DeepSeek 官方接口与 OpenAI 协议兼容，但单独保留适配器，
便于后续接入 DeepSeek 独有参数（如 reasoning 相关配置）而不影响其他服务商。
Base URL 默认 https://api.deepseek.com，允许用户修改。
"""

from __future__ import annotations

from .openai_compatible import OpenAICompatibleAdapter

DEFAULT_BASE_URL = "https://api.deepseek.com"


class DeepSeekAdapter(OpenAICompatibleAdapter):
    provider_type = "deepseek"

    def __init__(self, base_url: str, api_key: str, timeout: float = 20.0):
        super().__init__(base_url or DEFAULT_BASE_URL, api_key, timeout)
