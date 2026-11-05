"""统一模型调用接口。

业务代码只依赖 BaseAdapter，不直接依赖任何一家服务商的 SDK 或接口细节。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 统一错误码，供前端展示与错误分类
ERROR_NETWORK = "network_error"          # 网络连接失败
ERROR_TIMEOUT = "timeout"                # 请求超时
ERROR_INVALID_KEY = "invalid_api_key"    # API Key 无效或无权限
ERROR_MODEL_NOT_FOUND = "model_not_found"  # 模型不存在
ERROR_QUOTA = "quota_exceeded"           # 余额/配额/频率限制
ERROR_BAD_REQUEST = "bad_request"        # 请求格式不兼容
ERROR_SERVER = "server_error"            # 服务商返回其他错误
ERROR_NOT_SUPPORTED = "not_supported"    # 服务商不支持该能力（如模型列表）
ERROR_INVALID_URL = "invalid_base_url"   # Base URL 不合法
ERROR_MISSING_KEY = "missing_api_key"    # 尚未配置 API Key


class AdapterError(Exception):
    """适配器统一异常，携带机器可读错误码与安全的中文提示。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatRequest:
    model: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int | None = 512
    stream: bool = False  # 预留流式输出接口，本阶段未实现


@dataclass
class CompletionResult:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    latency_ms: int = 0


class BaseAdapter:
    """模型服务商适配器基类。"""

    provider_type = "generic"

    def __init__(self, base_url: str, api_key: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def list_models(self) -> list[str]:
        """返回服务商可用模型标识符列表；不支持时抛 ERROR_NOT_SUPPORTED。"""
        raise AdapterError(ERROR_NOT_SUPPORTED, "当前服务商不支持模型列表接口")

    async def chat(self, request: ChatRequest) -> CompletionResult:
        raise AdapterError(ERROR_NOT_SUPPORTED, "当前服务商不支持对话接口")

    async def close(self) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()
