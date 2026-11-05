"""小说项目管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..database.db import NOVEL_STATUSES
from ..models.schemas import (
    NovelCreate,
    NovelDeleteResult,
    NovelDetail,
    NovelOut,
    NovelUpdate,
)
from ..services import novel_service
from ..services.errors import ServiceError

router = APIRouter(tags=["novels"])


def _error(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/novels", response_model=list[NovelOut])
def list_novels(
    search: str | None = Query(default=None, max_length=100, description="按标题搜索"),
    status: str | None = Query(default=None, description="按创作状态筛选"),
) -> list[dict]:
    if status and status not in NOVEL_STATUSES:
        raise HTTPException(status_code=400, detail="不支持的创作状态")
    return novel_service.list_novels(search=search, status=status)


# 注意：/novels/default 必须声明在 /novels/{novel_id} 之前，避免被动态路径捕获
@router.get("/novels/default", response_model=NovelOut | None)
def get_default_novel() -> dict | None:
    return novel_service.get_default_novel()


@router.post("/novels", response_model=NovelDetail)
def create_novel(payload: NovelCreate) -> dict:
    return novel_service.create_novel(**payload.model_dump())


@router.get("/novels/{novel_id}", response_model=NovelDetail)
def get_novel(novel_id: str) -> dict:
    try:
        return novel_service.get_novel(novel_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.put("/novels/{novel_id}", response_model=NovelDetail)
def update_novel(novel_id: str, payload: NovelUpdate) -> dict:
    try:
        return novel_service.update_novel(novel_id, payload.model_dump())
    except ServiceError as exc:
        raise _error(exc) from exc


@router.put("/novels/{novel_id}/default", response_model=NovelOut)
def set_default_novel(novel_id: str) -> dict:
    try:
        return novel_service.set_default_novel(novel_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.delete("/novels/{novel_id}", response_model=NovelDeleteResult)
def delete_novel(novel_id: str) -> dict:
    try:
        return novel_service.delete_novel(novel_id)
    except ServiceError as exc:
        raise _error(exc) from exc
