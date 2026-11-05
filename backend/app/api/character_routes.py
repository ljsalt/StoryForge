"""人物档案接口（按小说隔离）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    CharacterCreate,
    CharacterListOut,
    CharacterOut,
    CharacterSecretCreate,
    CharacterSecretOut,
    CharacterSecretUpdate,
    CharacterStateOut,
    CharacterStateUpdate,
    CharacterUpdate,
    WorldDeleteResult,
)
from ..services import character_service
from ..services.errors import ServiceError

router = APIRouter(tags=["characters"])


def _error(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# ----------------------------- 人物档案 -----------------------------
@router.get(
    "/novels/{novel_id}/characters", response_model=list[CharacterListOut]
)
def list_characters(
    novel_id: str,
    search: str | None = Query(default=None, max_length=100, description="姓名/身份/背景/别名关键词"),
    role: str | None = Query(default=None, max_length=50, description="人物定位筛选"),
    tag: str | None = Query(default=None, max_length=20, description="标签筛选"),
    sort: str | None = Query(
        default=None, max_length=20,
        description="排序：name / created_desc / updated_desc",
    ),
) -> list[dict]:
    try:
        return character_service.list_characters(
            novel_id, search=search, role=role, tag=tag, sort=sort
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.post("/novels/{novel_id}/characters", response_model=CharacterOut)
def create_character(novel_id: str, payload: CharacterCreate) -> dict:
    try:
        return character_service.create_character(novel_id, payload.model_dump())
    except ServiceError as exc:
        raise _error(exc) from exc


@router.get("/novels/{novel_id}/characters/{character_id}", response_model=CharacterOut)
def get_character(novel_id: str, character_id: str) -> dict:
    try:
        return character_service.get_character(novel_id, character_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.put("/novels/{novel_id}/characters/{character_id}", response_model=CharacterOut)
def update_character(
    novel_id: str, character_id: str, payload: CharacterUpdate
) -> dict:
    try:
        return character_service.update_character(
            novel_id, character_id, payload.model_dump(exclude_unset=True)
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.delete(
    "/novels/{novel_id}/characters/{character_id}", response_model=WorldDeleteResult
)
def delete_character(novel_id: str, character_id: str) -> dict:
    try:
        return character_service.delete_character(novel_id, character_id)
    except ServiceError as exc:
        raise _error(exc) from exc


# ----------------------------- 当前状态 -----------------------------
@router.get(
    "/novels/{novel_id}/characters/{character_id}/state",
    response_model=CharacterStateOut,
)
def get_state(novel_id: str, character_id: str) -> dict:
    try:
        return character_service.get_state(novel_id, character_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.put(
    "/novels/{novel_id}/characters/{character_id}/state",
    response_model=CharacterStateOut,
)
def update_state(
    novel_id: str, character_id: str, payload: CharacterStateUpdate
) -> dict:
    try:
        return character_service.update_state(
            novel_id, character_id, payload.model_dump(exclude_unset=True)
        )
    except ServiceError as exc:
        raise _error(exc) from exc


# ----------------------------- 秘密 -----------------------------
@router.get(
    "/novels/{novel_id}/characters/{character_id}/secrets",
    response_model=list[CharacterSecretOut],
)
def list_secrets(novel_id: str, character_id: str) -> list[dict]:
    try:
        return character_service.list_secrets(novel_id, character_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.post(
    "/novels/{novel_id}/characters/{character_id}/secrets",
    response_model=CharacterSecretOut,
)
def create_secret(
    novel_id: str, character_id: str, payload: CharacterSecretCreate
) -> dict:
    try:
        return character_service.create_secret(
            novel_id, character_id, payload.model_dump()
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.get(
    "/novels/{novel_id}/characters/{character_id}/secrets/{secret_id}",
    response_model=CharacterSecretOut,
)
def get_secret(novel_id: str, character_id: str, secret_id: str) -> dict:
    try:
        return character_service.get_secret(novel_id, character_id, secret_id)
    except ServiceError as exc:
        raise _error(exc) from exc


@router.put(
    "/novels/{novel_id}/characters/{character_id}/secrets/{secret_id}",
    response_model=CharacterSecretOut,
)
def update_secret(
    novel_id: str,
    character_id: str,
    secret_id: str,
    payload: CharacterSecretUpdate,
) -> dict:
    try:
        return character_service.update_secret(
            novel_id, character_id, secret_id, payload.model_dump(exclude_unset=True)
        )
    except ServiceError as exc:
        raise _error(exc) from exc


@router.delete(
    "/novels/{novel_id}/characters/{character_id}/secrets/{secret_id}",
    response_model=WorldDeleteResult,
)
def delete_secret(
    novel_id: str, character_id: str, secret_id: str
) -> dict:
    try:
        return character_service.delete_secret(novel_id, character_id, secret_id)
    except ServiceError as exc:
        raise _error(exc) from exc
