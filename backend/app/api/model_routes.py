"""模型服务商、模型与任务模型分配接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models.schemas import (
    ModelCreate,
    ModelOut,
    ModelSettingsOut,
    ModelSettingsUpdate,
    ModelTestRequest,
    ModelTestResult,
    ModelUpdate,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
)
from ..services import model_service, provider_service
from ..services.errors import ServiceError

router = APIRouter(tags=["models"])


def _error(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# ----------------------------- Provider -----------------------------
@router.get("/providers", response_model=list[ProviderOut])
def list_providers() -> list[dict]:
    return provider_service.list_providers()


@router.post("/providers", response_model=ProviderOut)
def create_provider(payload: ProviderCreate) -> dict:
    try:
        return provider_service.create_provider(
            name=payload.name,
            provider_type=payload.provider_type,
            base_url=payload.base_url,
            api_key=payload.api_key,
            enabled=payload.enabled,
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.put("/providers/{provider_id}", response_model=ProviderOut)
def update_provider(provider_id: str, payload: ProviderUpdate) -> dict:
    try:
        return provider_service.update_provider(
            provider_id,
            name=payload.name,
            provider_type=payload.provider_type,
            base_url=payload.base_url,
            api_key=payload.api_key,
            enabled=payload.enabled,
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: str) -> dict:
    try:
        return provider_service.delete_provider(provider_id)
    except ServiceError as exc:
        raise _error(exc) from exc


# ------------------------------ Model -------------------------------
@router.get("/models", response_model=list[ModelOut])
def list_models(provider_id: str | None = None) -> list[dict]:
    return model_service.list_models(provider_id)


@router.post("/models", response_model=ModelOut)
def create_model(payload: ModelCreate) -> dict:
    try:
        return model_service.create_model(
            provider_id=payload.provider_id,
            name=payload.name,
            model_id=payload.model_id,
            remark=payload.remark,
            enabled=payload.enabled,
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.post("/models/test", response_model=ModelTestResult)
async def test_model(payload: ModelTestRequest) -> dict:
    try:
        return await model_service.test_model_connection(payload.model_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.put("/models/{model_id}", response_model=ModelOut)
def update_model(model_id: str, payload: ModelUpdate) -> dict:
    try:
        return model_service.update_model(
            model_id,
            provider_id=payload.provider_id,
            name=payload.name,
            model_id=payload.model_id,
            remark=payload.remark,
            enabled=payload.enabled,
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.delete("/models/{model_id}")
def delete_model(model_id: str) -> dict:
    try:
        return model_service.delete_model(model_id)
    except ServiceError as exc:
        raise _error(exc) from exc


# ------------------------- Task model settings -----------------------
@router.get("/model-settings", response_model=ModelSettingsOut)
def get_model_settings() -> dict:
    return model_service.get_model_settings()


@router.put("/model-settings", response_model=ModelSettingsOut)
def update_model_settings(payload: ModelSettingsUpdate) -> dict:
    try:
        return model_service.update_model_settings(
            payload.tasks, payload.default_model_id
        )
    except ServiceError as exc:
        raise _error(exc) from exc
