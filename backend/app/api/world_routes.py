"""世界观设定接口（按小说隔离）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    WorldCategoryCreate,
    WorldCategoryOut,
    WorldCategoryUpdate,
    WorldDeleteResult,
    WorldEntryCreate,
    WorldEntryOut,
    WorldEntryRelationsOut,
    WorldEntryUpdate,
    WorldRelationCreate,
    WorldRelationOut,
    WorldRelationUpdate,
    WorldStats,
)
from ..services import world_relation_service, world_service
from ..services.errors import ServiceError

router = APIRouter(tags=["world"])


def _error(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# ----------------------------- 条目 -----------------------------
@router.get("/novels/{novel_id}/world/entries", response_model=list[WorldEntryOut])
def list_entries(
    novel_id: str,
    search: str | None = Query(default=None, max_length=100, description="关键词搜索"),
    category_id: str | None = Query(default=None, max_length=64, description="分类筛选"),
    tag: str | None = Query(default=None, max_length=20, description="标签筛选"),
    parent_id: str | None = Query(default=None, max_length=64, description="父级条目筛选"),
) -> list[dict]:
    try:
        return world_service.list_entries(
            novel_id,
            search=search,
            category_id=category_id,
            tag=tag,
            parent_id=parent_id,
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.post("/novels/{novel_id}/world/entries", response_model=WorldEntryOut)
def create_entry(novel_id: str, payload: WorldEntryCreate) -> dict:
    try:
        return world_service.create_entry(novel_id, payload.model_dump())
    except ServiceError as exc:
        raise _error(exc) from exc


@router.get("/novels/{novel_id}/world/entries/{entry_id}", response_model=WorldEntryOut)
def get_entry(novel_id: str, entry_id: str) -> dict:
    try:
        return world_service.get_entry(novel_id, entry_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.put("/novels/{novel_id}/world/entries/{entry_id}", response_model=WorldEntryOut)
def update_entry(novel_id: str, entry_id: str, payload: WorldEntryUpdate) -> dict:
    try:
        return world_service.update_entry(
            novel_id, entry_id, payload.model_dump(exclude_unset=True)
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.delete(
    "/novels/{novel_id}/world/entries/{entry_id}", response_model=WorldDeleteResult
)
def delete_entry(novel_id: str, entry_id: str) -> dict:
    try:
        return world_service.delete_entry(novel_id, entry_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.get(
    "/novels/{novel_id}/world/entries/{entry_id}/relations",
    response_model=WorldEntryRelationsOut,
)
def list_entry_relations(novel_id: str, entry_id: str) -> dict:
    try:
        return world_relation_service.list_entry_relations(novel_id, entry_id)
    except ServiceError as exc:
        raise _error(exc) from exc


# ----------------------------- 关系 -----------------------------
@router.get(
    "/novels/{novel_id}/world/relations", response_model=list[WorldRelationOut]
)
def list_relations(
    novel_id: str,
    relation_type: str | None = Query(
        default=None, max_length=50, description="关系类型筛选"
    ),
    source_entry_id: str | None = Query(
        default=None, max_length=64, description="起点条目筛选"
    ),
    target_entry_id: str | None = Query(
        default=None, max_length=64, description="终点条目筛选"
    ),
    search: str | None = Query(default=None, max_length=100, description="描述关键词搜索"),
) -> list[dict]:
    try:
        return world_relation_service.list_relations(
            novel_id,
            relation_type=relation_type,
            source_entry_id=source_entry_id,
            target_entry_id=target_entry_id,
            search=search,
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.post("/novels/{novel_id}/world/relations", response_model=WorldRelationOut)
def create_relation(novel_id: str, payload: WorldRelationCreate) -> dict:
    try:
        return world_relation_service.create_relation(novel_id, payload.model_dump())
    except ServiceError as exc:
        raise _error(exc) from exc


@router.get(
    "/novels/{novel_id}/world/relations/{relation_id}", response_model=WorldRelationOut
)
def get_relation(novel_id: str, relation_id: str) -> dict:
    try:
        return world_relation_service.get_relation(novel_id, relation_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.put(
    "/novels/{novel_id}/world/relations/{relation_id}", response_model=WorldRelationOut
)
def update_relation(
    novel_id: str, relation_id: str, payload: WorldRelationUpdate
) -> dict:
    try:
        return world_relation_service.update_relation(
            novel_id, relation_id, payload.model_dump(exclude_unset=True)
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.delete(
    "/novels/{novel_id}/world/relations/{relation_id}",
    response_model=WorldDeleteResult,
)
def delete_relation(novel_id: str, relation_id: str) -> dict:
    try:
        return world_relation_service.delete_relation(novel_id, relation_id)
    except ServiceError as exc:
        raise _error(exc) from exc


# ----------------------------- 分类 -----------------------------
@router.get(
    "/novels/{novel_id}/world/categories", response_model=list[WorldCategoryOut]
)
def list_categories(novel_id: str) -> list[dict]:
    try:
        return world_service.list_categories(novel_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.post(
    "/novels/{novel_id}/world/categories", response_model=WorldCategoryOut
)
def create_category(novel_id: str, payload: WorldCategoryCreate) -> dict:
    try:
        return world_service.create_category(
            novel_id,
            name=payload.name,
            description=payload.description,
            sort_order=payload.sort_order,
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.put(
    "/novels/{novel_id}/world/categories/{category_id}", response_model=WorldCategoryOut
)
def update_category(
    novel_id: str, category_id: str, payload: WorldCategoryUpdate
) -> dict:
    try:
        return world_service.update_category(
            novel_id, category_id, payload.model_dump(exclude_unset=True)
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.delete(
    "/novels/{novel_id}/world/categories/{category_id}",
    response_model=WorldDeleteResult,
)
def delete_category(novel_id: str, category_id: str) -> dict:
    try:
        return world_service.delete_category(novel_id, category_id)
    except ServiceError as exc:
        raise _error(exc) from exc


# ----------------------------- 统计 -----------------------------
@router.get("/novels/{novel_id}/world/stats", response_model=WorldStats)
def get_stats(novel_id: str) -> dict:
    try:
        return world_service.get_stats(novel_id)
    except ServiceError as exc:
        raise _error(exc) from exc
