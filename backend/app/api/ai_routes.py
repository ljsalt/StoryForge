"""AI 基础设施接口：调用测试、上下文预览、提示词模板、任务记录。

注意：/ai/generate 是 AI 调用测试接口，只用于验证模型链路，
不代表本阶段已实现正式章节生成。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    AiGenerateRequest,
    AiGenerateResult,
    AiRoutePreviewOut,
    AiTaskOut,
    ContextPreviewOut,
    ContextPreviewRequest,
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptTemplateRenderOut,
    PromptTemplateRenderRequest,
    PromptTemplateUpdate,
    PromptTemplateVersionOut,
    WorldDeleteResult,
)
from ..services import (
    ai_generation_service,
    ai_task_service,
    context_builder,
    prompt_template_service,
)
from ..services.errors import ServiceError

router = APIRouter(tags=["ai"])


def _err(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# ----------------------------- AI 调用测试 -----------------------------

@router.post("/ai/generate", response_model=AiGenerateResult)
async def ai_generate(payload: AiGenerateRequest) -> dict:
    """AI 调用测试接口（测试用途，不会写入任何章节/剧情数据）。"""
    try:
        result = await ai_generation_service.generate(payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc
    result["test_only"] = True
    return result


@router.get("/ai/route", response_model=AiRoutePreviewOut)
def ai_route_preview(
    task_type: str = Query(default="default", max_length=20),
    model_id: str | None = Query(default=None, max_length=64),
) -> dict:
    """查看某任务类型当前实际路由到的模型（不发起请求）。"""
    try:
        return ai_generation_service.route_preview(task_type, model_id)
    except ServiceError as exc:
        raise _err(exc) from exc


# ----------------------------- 上下文预览 -----------------------------

@router.post("/ai/context/preview", response_model=ContextPreviewOut)
def ai_context_preview(payload: ContextPreviewRequest) -> dict:
    """组装上下文预览：只读取数据库并返回分区结果，不执行任何模型调用。"""
    try:
        return context_builder.build_context(
            payload.novel_id,
            task_type=payload.task_type,
            chapter_id=payload.chapter_id,
            character_ids=payload.character_ids,
            token_budget=payload.token_budget,
            pov=payload.pov,
            user_requirement=payload.user_requirement,
        )
    except ServiceError as exc:
        raise _err(exc) from exc


# ----------------------------- 提示词模板 -----------------------------

@router.get("/ai/prompt-templates", response_model=list[PromptTemplateOut])
def list_prompt_templates(
    task_type: str | None = Query(default=None, max_length=20),
    include_inactive: bool = Query(default=False),
) -> list[dict]:
    try:
        return prompt_template_service.list_templates(
            task_type, include_inactive=include_inactive
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/ai/prompt-templates", response_model=PromptTemplateOut)
def create_prompt_template(payload: PromptTemplateCreate) -> dict:
    try:
        return prompt_template_service.create_template(payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/ai/prompt-templates/render", response_model=PromptTemplateRenderOut)
def render_prompt_template(payload: PromptTemplateRenderRequest) -> dict:
    """渲染校验：必需变量缺失时返回 400，不会把未替换的变量放行。"""
    try:
        return prompt_template_service.render_template(
            payload.template_id, payload.variables
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get("/ai/prompt-templates/{template_id}", response_model=PromptTemplateOut)
def get_prompt_template(template_id: str) -> dict:
    try:
        return prompt_template_service.get_template(template_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.put("/ai/prompt-templates/{template_id}", response_model=PromptTemplateOut)
def update_prompt_template(template_id: str, payload: PromptTemplateUpdate) -> dict:
    try:
        return prompt_template_service.update_template(
            template_id, payload.model_dump()
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.delete(
    "/ai/prompt-templates/{template_id}", response_model=WorldDeleteResult
)
def delete_prompt_template(template_id: str) -> dict:
    try:
        return prompt_template_service.delete_template(template_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/ai/prompt-templates/{template_id}/versions",
    response_model=list[PromptTemplateVersionOut],
)
def list_prompt_template_versions(template_id: str) -> list[dict]:
    try:
        return prompt_template_service.list_versions(template_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/ai/prompt-templates/{template_id}/restore/{version}",
    response_model=PromptTemplateOut,
)
def restore_prompt_template_version(template_id: str, version: int) -> dict:
    """以历史版本内容生成新版本（版本号递增，历史不丢失）。"""
    try:
        return prompt_template_service.restore_version(template_id, version)
    except ServiceError as exc:
        raise _err(exc) from exc


# ----------------------------- AI 任务记录 -----------------------------

@router.get("/ai/tasks", response_model=list[AiTaskOut])
def list_ai_tasks(
    novel_id: str = Query(min_length=1, max_length=64),
    status: str | None = Query(default=None, max_length=20),
    task_type: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    try:
        return ai_task_service.list_tasks(
            novel_id, status=status, task_type=task_type, limit=limit
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get("/ai/tasks/{task_id}", response_model=AiTaskOut)
def get_ai_task(
    task_id: str,
    novel_id: str = Query(min_length=1, max_length=64),
) -> dict:
    try:
        return ai_task_service.get_task(novel_id, task_id)
    except ServiceError as exc:
        raise _err(exc) from exc
