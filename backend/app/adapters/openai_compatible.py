"""OpenAI 兼容协议适配器。

适用于任何实现 /chat/completions 与 /models 的 OpenAI 兼容服务。
Base URL 允许用户自定义，例如：
- https://api.deepseek.com
- https://api.openai.com/v1
- https://your-gateway.example.com/v1
"""

from __future__ import annotations

import time

import httpx

from ..core.security import sanitize_text
from .base import (
    ERROR_BAD_REQUEST,
    ERROR_INVALID_KEY,
    ERROR_MODEL_NOT_FOUND,
    ERROR_NETWORK,
    ERROR_NOT_SUPPORTED,
    ERROR_QUOTA,
    ERROR_SERVER,
    ERROR_TIMEOUT,
    AdapterError,
    BaseAdapter,
    ChatRequest,
    CompletionResult,
)


class OpenAICompatibleAdapter(BaseAdapter):
    provider_type = "openai_compatible"

    def _candidates(self, path: str) -> list[str]:
        """兼容两种 Base URL 写法：带 /v1 或不带 /v1。"""
        urls = [f"{self.base_url}{path}"]
        if not self.base_url.endswith("/v1"):
            urls.append(f"{self.base_url}/v1{path}")
        return urls

    async def _send(
        self, method: str, path: str, payload: dict | None = None
    ) -> httpx.Response:
        last_error: Exception | None = None
        for index, url in enumerate(self._candidates(path)):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, follow_redirects=False
                ) as client:
                    response = await client.request(
                        method,
                        url,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                    )
            except httpx.TimeoutException:
                raise AdapterError(ERROR_TIMEOUT, "请求服务商超时，请检查网络或稍后重试")
            except httpx.HTTPError as exc:
                raise AdapterError(
                    ERROR_NETWORK,
                    f"网络连接失败：{exc.__class__.__name__}，请检查 Base URL 与网络",
                )

            # 404 时尝试另一种路径写法（常见于少写 /v1 的 Base URL）
            if response.status_code == 404 and index + 1 < len(self._candidates(path)):
                last_error = AdapterError(ERROR_MODEL_NOT_FOUND, "接口路径不存在")
                continue
            return response

        raise last_error or AdapterError(ERROR_NETWORK, "无法连接到服务商接口")

    @staticmethod
    def _error_detail(response: httpx.Response, api_key: str) -> str:
        try:
            body = response.json()
        except ValueError:
            body = None
        detail = ""
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                detail = str(err.get("message") or "")
            elif isinstance(err, str):
                detail = err
            if not detail:
                detail = str(body.get("message") or "")
        detail = sanitize_text(detail, api_key)
        return detail or f"HTTP {response.status_code}"

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        detail = self._error_detail(response, self.api_key)
        if status in (401, 403):
            raise AdapterError(ERROR_INVALID_KEY, f"API Key 无效或无访问权限：{detail}")
        if status == 402:
            raise AdapterError(ERROR_QUOTA, f"余额不足或配额已用尽：{detail}")
        if status == 404:
            raise AdapterError(ERROR_MODEL_NOT_FOUND, f"模型或接口不存在：{detail}")
        if status == 429:
            raise AdapterError(ERROR_QUOTA, f"请求过于频繁或配额不足：{detail}")
        if status in (400, 422):
            raise AdapterError(ERROR_BAD_REQUEST, f"请求格式不兼容：{detail}")
        if status >= 500:
            raise AdapterError(ERROR_SERVER, f"服务商返回异常状态：{detail}")
        raise AdapterError(ERROR_SERVER, f"服务商返回未预期状态：HTTP {status}")

    async def list_models(self) -> list[str]:
        response = await self._send("GET", "/models")
        if response.status_code == 404:
            raise AdapterError(ERROR_NOT_SUPPORTED, "服务商未提供模型列表接口")
        if response.status_code != 200:
            self._raise_for_status(response)

        try:
            body = response.json()
        except ValueError:
            raise AdapterError(ERROR_BAD_REQUEST, "服务商返回内容不是有效 JSON")

        items = body.get("data") if isinstance(body, dict) else None
        if not isinstance(items, list):
            raise AdapterError(ERROR_NOT_SUPPORTED, "服务商模型列表格式不受支持")

        model_ids: list[str] = []
        for item in items:
            if isinstance(item, dict):
                identifier = item.get("id") or item.get("name")
                if identifier:
                    model_ids.append(str(identifier))
        return model_ids

    async def chat(self, request: ChatRequest) -> CompletionResult:
        if request.stream:
            raise AdapterError(ERROR_NOT_SUPPORTED, "本阶段暂未实现流式输出")

        payload: dict = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        started = time.perf_counter()
        response = await self._send("POST", "/chat/completions", payload)
        latency_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code != 200:
            self._raise_for_status(response)

        try:
            body = response.json()
        except ValueError:
            raise AdapterError(ERROR_BAD_REQUEST, "服务商返回内容不是有效 JSON")

        choices = body.get("choices") if isinstance(body, dict) else None
        if not choices:
            raise AdapterError(ERROR_SERVER, "服务商响应中缺少 choices 字段")
        message = choices[0].get("message") or {}
        content = message.get("content") or ""

        return CompletionResult(
            content=str(content),
            model=str(body.get("model") or payload["model"]),
            usage=body.get("usage") or {},
            latency_ms=latency_ms,
        )
