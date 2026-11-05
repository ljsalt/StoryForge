"""剧情事件接口（按小说隔离）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    PlotEventCreate,
    PlotEventOut,
    PlotEventUpdate,
    PlotTimelineOut,
    WorldDeleteResult,
)
from ..services import plot_event_service as service
from ..services.errors import ServiceError

router = APIRouter(tags=["plot-events"])


def _err(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# 固定路径必须先于 /plot-events/{event_id} 声明
@router.get(
    "/novels/{novel_id}/plot-events/timeline",
    response_model=PlotTimelineOut,
)
def plot_timeline(
    novel_id: str,
    chapter_id: str | None = Query(default=None, max_length=64),
    character_id: str | None = Query(default=None, max_length=64),
    event_type: str | None = Query(default=None, max_length=80),
    importance: str | None = Query(default=None, max_length=20),
) -> dict:
    try:
        return service.timeline(
            novel_id,
            chapter_id=chapter_id,
            character_id=character_id,
            event_type=event_type,
            importance=importance,
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get("/novels/{novel_id}/plot-events", response_model=list[PlotEventOut])
def list_plot_events(
    novel_id: str,
    chapter_id: str | None = Query(default=None, max_length=64),
    character_id: str | None = Query(default=None, max_length=64),
    event_type: str | None = Query(default=None, max_length=80),
    importance: str | None = Query(default=None, max_length=20),
    search: str | None = Query(default=None, max_length=100),
    has_story_time: bool | None = Query(default=None),
) -> list[dict]:
    try:
        return service.list_events(
            novel_id,
            chapter_id=chapter_id,
            character_id=character_id,
            event_type=event_type,
            importance=importance,
            search=search,
            has_story_time=has_story_time,
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/novels/{novel_id}/plot-events", response_model=PlotEventOut)
def create_plot_event(novel_id: str, payload: PlotEventCreate) -> dict:
    try:
        return service.create_event(novel_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get("/novels/{novel_id}/plot-events/{event_id}", response_model=PlotEventOut)
def get_plot_event(novel_id: str, event_id: str) -> dict:
    try:
        return service.get_event(novel_id, event_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.put("/novels/{novel_id}/plot-events/{event_id}", response_model=PlotEventOut)
def update_plot_event(novel_id: str, event_id: str, payload: PlotEventUpdate) -> dict:
    try:
        return service.update_event(novel_id, event_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.delete(
    "/novels/{novel_id}/plot-events/{event_id}", response_model=WorldDeleteResult
)
def delete_plot_event(novel_id: str, event_id: str) -> dict:
    try:
        return service.delete_event(novel_id, event_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/characters/{character_id}/plot-events",
    response_model=list[PlotEventOut],
)
def character_plot_events(novel_id: str, character_id: str) -> list[dict]:
    try:
        return service.list_by_character(novel_id, character_id)
    except ServiceError as exc:
        raise _err(exc) from exc
