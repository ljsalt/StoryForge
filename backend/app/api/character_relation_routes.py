"""人物关系接口（按小说隔离）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    CharacterCharacterRelationsOut,
    CharacterRelationCreate,
    CharacterRelationEventOut,
    CharacterRelationOut,
    CharacterRelationUpdate,
    WorldDeleteResult,
)
from ..services import character_relation_service as service
from ..services.errors import ServiceError

router = APIRouter(tags=["character-relations"])


def _err(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get(
    "/novels/{novel_id}/character-relations",
    response_model=list[CharacterRelationOut],
)
def list_relations(
    novel_id: str,
    source_character_id: str | None = Query(default=None, max_length=64),
    target_character_id: str | None = Query(default=None, max_length=64),
    relation_type: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None, max_length=20),
    only_active: bool = Query(default=False),
    search: str | None = Query(default=None, max_length=100),
) -> list[dict]:
    try:
        return service.list_relations(
            novel_id,
            source_character_id=source_character_id,
            target_character_id=target_character_id,
            relation_type=relation_type,
            status=status,
            only_active=only_active,
            search=search,
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/character-relations",
    response_model=CharacterRelationOut,
)
def create_relation(novel_id: str, payload: CharacterRelationCreate) -> dict:
    try:
        return service.create_relation(novel_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/character-relations/bidirectional",
    response_model=tuple[CharacterRelationOut, CharacterRelationOut],
)
def create_bidirectional(novel_id: str, payload: CharacterRelationCreate) -> tuple[dict, dict]:
    try:
        return service.create_bidirectional(novel_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/character-relations/{relation_id}",
    response_model=CharacterRelationOut,
)
def get_relation(novel_id: str, relation_id: str) -> dict:
    try:
        return service.get_relation(novel_id, relation_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.put(
    "/novels/{novel_id}/character-relations/{relation_id}",
    response_model=CharacterRelationOut,
)
def update_relation(
    novel_id: str,
    relation_id: str,
    payload: CharacterRelationUpdate,
) -> dict:
    try:
        # 后端服务自动记录 updated 事件；event_info 作为事件附加上下文暂不暴露给前端
        return service.update_relation(
            novel_id, relation_id, payload.model_dump(exclude_unset=True)
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/character-relations/{relation_id}/end",
    response_model=CharacterRelationOut,
)
def end_relation(novel_id: str, relation_id: str) -> dict:
    try:
        return service.end_relation(novel_id, relation_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/character-relations/{relation_id}/restore",
    response_model=CharacterRelationOut,
)
def restore_relation(novel_id: str, relation_id: str) -> dict:
    try:
        return service.restore_relation(novel_id, relation_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/character-relations/{relation_id}/events",
    response_model=list[CharacterRelationEventOut],
)
def list_events(novel_id: str, relation_id: str) -> list[dict]:
    try:
        return service.list_events(novel_id, relation_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/characters/{character_id}/relations",
    response_model=CharacterCharacterRelationsOut,
)
def list_character_relations(
    novel_id: str,
    character_id: str,
    include_ended: bool = Query(default=True),
) -> dict:
    try:
        return service.list_character_relations(
            novel_id, character_id, include_ended=include_ended
        )
    except ServiceError as exc:
        raise _err(exc) from exc
