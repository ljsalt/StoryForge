"""章节接口（按小说隔离）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    ChapterCreate,
    ChapterOut,
    ChapterReorder,
    ChapterStats,
    ChapterSummaryOut,
    ChapterUpdate,
    ChapterRelationEventOut,
    PlotEventOut,
    WorldDeleteResult,
)
from ..services import chapter_service as service
from ..services import character_relation_service as rel_service
from ..services import plot_event_service
from ..services.errors import ServiceError

router = APIRouter(tags=["chapters"])


def _err(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# 固定路径必须先于 /chapters/{chapter_id} 声明，避免 "stats" 被当成章节 ID
@router.get("/novels/{novel_id}/chapters/stats", response_model=ChapterStats)
def chapter_stats(novel_id: str) -> dict:
    try:
        return service.get_stats(novel_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.patch(
    "/novels/{novel_id}/chapters/reorder",
    response_model=list[ChapterSummaryOut],
)
def reorder_chapters(novel_id: str, payload: ChapterReorder) -> list[dict]:
    try:
        return service.reorder_chapters(novel_id, payload.ordered_ids)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/chapters",
    response_model=list[ChapterSummaryOut],
)
def list_chapters(
    novel_id: str,
    status: str | None = Query(default=None, max_length=20),
    volume_number: int | None = Query(default=None, ge=1),
    search: str | None = Query(default=None, max_length=100),
) -> list[dict]:
    try:
        return service.list_chapters(
            novel_id,
            status=status,
            volume_number=volume_number,
            search=search,
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/novels/{novel_id}/chapters", response_model=ChapterOut)
def create_chapter(novel_id: str, payload: ChapterCreate) -> dict:
    try:
        return service.create_chapter(novel_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get("/novels/{novel_id}/chapters/{chapter_id}", response_model=ChapterOut)
def get_chapter(novel_id: str, chapter_id: str) -> dict:
    try:
        return service.get_chapter(novel_id, chapter_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.put("/novels/{novel_id}/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(novel_id: str, chapter_id: str, payload: ChapterUpdate) -> dict:
    try:
        return service.update_chapter(novel_id, chapter_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.delete("/novels/{novel_id}/chapters/{chapter_id}", response_model=WorldDeleteResult)
def delete_chapter(novel_id: str, chapter_id: str) -> dict:
    try:
        return service.delete_chapter(novel_id, chapter_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/chapters/{chapter_id}/events",
    response_model=list[PlotEventOut],
)
def chapter_events(novel_id: str, chapter_id: str) -> list[dict]:
    try:
        return plot_event_service.list_by_chapter(novel_id, chapter_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/chapters/{chapter_id}/relation-events",
    response_model=list[ChapterRelationEventOut],
)
def chapter_relation_events(novel_id: str, chapter_id: str) -> list[dict]:
    try:
        return rel_service.list_relation_events_by_chapter(novel_id, chapter_id)
    except ServiceError as exc:
        raise _err(exc) from exc
