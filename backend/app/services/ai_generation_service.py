"""统一 AI 调用服务。

所有业务侧的模型调用都必须经过本服务，再由本服务通过 ModelRouter 解析模型。
禁止在业务代码中直接硬编码任何服务商或绕过 ModelRouter。

模型选择优先级：显式指定 > 任务模型配置 > 全局默认模型
（小说级任务模型配置当前架构尚未支持，预留扩展点，见 route 结果说明）。

响应处理要点：
- reasoning（思维链）与 content（正文）严格区分，思维链不当作正文；
- HTTP 200 但正文为空返回明确错误（empty_content / reasoning_only），不伪装成功；
- finish_reason == 'length' 标记 truncated，不把截断内容当作完整结果；
- 不做自动重试，避免重复生成与重复扣费；
- 日志与返回值都不包含 API Key、完整提示词和完整正文。
"""

from __future__ import annotations

import logging
import time

from ..adapters.base import AdapterError, ChatMessage, ChatRequest
from ..database.db import AI_TASK_TYPES, get_connection
from . import ai_task_service, model_router
from .errors import ServiceError
from .token_util import estimate_tokens

logger = logging.getLogger(__name__)

_TIMEOUT_MIN = 1.0
_TIMEOUT_MAX = 300.0


def _ensure_novel(novel_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM novels WHERE id = ?", (novel_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "小说不存在")


def route_preview(task_type: str, model_id: str | None = None) -> dict:
    """展示某次调用会实际使用的模型（不发起任何请求，不接触密钥）。"""
    if task_type not in AI_TASK_TYPES:
        raise ServiceError(400, "不支持的任务类型")
    if model_id:
        resolved = model_router.resolve_model_by_id(model_id, task_type)
        if resolved is None:
            return {
                "task_type": task_type,
                "resolved": False,
                "model_id": model_id,
                "model_identifier": None,
                "provider_id": None,
                "provider_type": None,
                "resolved_from": None,
                "message": "指定的模型不存在或已停用，请重新选择",
            }
    else:
        resolved = model_router.resolve_model_for_task(task_type)
        if resolved is None:
            return {
                "task_type": task_type,
                "resolved": False,
                "model_id": None,
                "model_identifier": None,
                "provider_id": None,
                "provider_type": None,
                "resolved_from": None,
                "message": "尚未为该任务类型配置可用模型，请先在系统设置中分配模型",
            }
    return {
        "task_type": task_type,
        "resolved": True,
        "model_id": resolved.model_row_id,
        "model_identifier": resolved.model_identifier,
        "provider_id": resolved.provider_id,
        "provider_type": resolved.provider_type,
        "resolved_from": resolved.resolved_from,
        "message": "",
    }


async def generate(payload: dict) -> dict:
    """执行一次 AI 调用，返回统一响应结构（见模块文档）。"""
    novel_id = str(payload.get("novel_id") or "").strip()
    task_type = str(payload.get("task_type") or "default").strip()
    if task_type not in AI_TASK_TYPES:
        raise ServiceError(400, "不支持的任务类型")
    _ensure_novel(novel_id)

    model_id = (payload.get("model_id") or "").strip() or None
    if model_id:
        built = model_router.build_adapter_for_explicit(task_type, model_id)
        if built is None:
            raise ServiceError(400, "指定的模型不存在、已停用或未配置 API Key")
    else:
        built = model_router.build_adapter_for_task(task_type)
        if built is None:
            raise ServiceError(
                400, "尚未为该任务类型配置可用模型，请先在系统设置中分配模型"
            )
    adapter, resolved = built

    # 允许单次调用覆盖超时（钳制在合理范围），不修改全局配置
    timeout = payload.get("timeout")
    if timeout is not None:
        adapter.timeout = max(_TIMEOUT_MIN, min(float(timeout), _TIMEOUT_MAX))

    system_prompt = str(payload.get("system_prompt") or "")
    user_prompt = str(payload["user_prompt"])
    context = str(payload.get("context") or "")
    if context.strip():
        user_content = f"【小说上下文】\n{context}\n\n【本次任务】\n{user_prompt}"
    else:
        user_content = user_prompt

    messages: list[ChatMessage] = []
    if system_prompt.strip():
        messages.append(ChatMessage(role="system", content=system_prompt))
    messages.append(ChatMessage(role="user", content=user_content))

    estimated_input = estimate_tokens(system_prompt + user_content)
    task_id = ai_task_service.create_task(
        novel_id=novel_id,
        task_type=task_type,
        model_id=resolved.model_row_id,
        model_identifier=resolved.model_identifier,
        provider_id=resolved.provider_id,
        prompt_template_id=payload.get("prompt_template_id"),
        template_version=payload.get("template_version"),
        input_summary=ai_task_service.summarize(user_prompt),
        estimated_tokens=estimated_input,
    )

    request = ChatRequest(
        model=resolved.model_identifier,
        messages=messages,
        temperature=float(payload.get("temperature", 0.7)),
        max_tokens=payload.get("max_tokens"),
        extra=payload.get("extra_params") or {},
    )

    base = {
        "model": resolved.model_identifier,
        "provider": resolved.provider_type,
        "task_type": task_type,
        "task_id": task_id,
        "resolved_from": resolved.resolved_from,
    }

    started = time.perf_counter()
    try:
        result = await adapter.chat(request)
    except AdapterError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        ai_task_service.fail_task(
            task_id,
            error_code=exc.code,
            error_message=exc.message,
            latency_ms=latency_ms,
        )
        logger.info(
            "AI 调用失败 task=%s model=%s code=%s", task_id, resolved.model_identifier, exc.code
        )
        return {
            **base,
            "success": False,
            "content": "",
            "reasoning": "",
            "finish_reason": None,
            "truncated": False,
            "usage": {},
            "error_code": exc.code,
            "error_message": exc.message,
            "latency_ms": latency_ms,
        }
    except Exception as exc:  # 兜底：不泄露内部细节
        latency_ms = int((time.perf_counter() - started) * 1000)
        ai_task_service.fail_task(
            task_id,
            error_code="server_error",
            error_message=f"调用失败：{exc.__class__.__name__}",
            latency_ms=latency_ms,
        )
        logger.exception("AI 调用出现未预期异常 task=%s", task_id)
        return {
            **base,
            "success": False,
            "content": "",
            "reasoning": "",
            "finish_reason": None,
            "truncated": False,
            "usage": {},
            "error_code": "server_error",
            "error_message": "调用失败，请稍后重试",
            "latency_ms": latency_ms,
        }
    finally:
        await adapter.close()

    content = result.content or ""
    reasoning = result.reasoning or ""

    # HTTP 200 但正文为空：不伪装成成功，明确标记业务错误
    if not content.strip():
        error_code = "reasoning_only" if reasoning.strip() else "empty_content"
        error_message = (
            "模型只返回了思维链（reasoning），没有生成正文，请调整提示词或更换模型后重试"
            if reasoning.strip()
            else "模型返回了空正文，请调整提示词或增大 max_tokens 后重试"
        )
        ai_task_service.fail_task(
            task_id,
            error_code=error_code,
            error_message=error_message,
            latency_ms=result.latency_ms,
        )
        return {
            **base,
            "success": False,
            "content": "",
            "reasoning": reasoning if payload.get("include_reasoning") else "",
            "finish_reason": result.finish_reason,
            "truncated": False,
            "usage": result.usage or {},
            "error_code": error_code,
            "error_message": error_message,
            "latency_ms": result.latency_ms,
        }

    # finish_reason == 'length'：输出被 max_tokens 截断，必须显式标记
    truncated = result.finish_reason == "length"
    ai_task_service.complete_task(
        task_id,
        output_summary=ai_task_service.summarize(content),
        input_tokens=(result.usage or {}).get("prompt_tokens"),
        output_tokens=(result.usage or {}).get("completion_tokens"),
        truncated=truncated,
        latency_ms=result.latency_ms,
    )
    logger.info(
        "AI 调用完成 task=%s model=%s truncated=%s", task_id, result.model, truncated
    )
    return {
        **base,
        "success": True,
        "content": content,
        # reasoning 默认不返回给普通前端，仅在显式要求时附带
        "reasoning": reasoning if payload.get("include_reasoning") else "",
        "finish_reason": result.finish_reason,
        "truncated": truncated,
        "usage": result.usage or {},
        "error_code": None,
        "error_message": None,
        "latency_ms": result.latency_ms,
    }
