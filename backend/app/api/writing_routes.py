"""P4.1.2 单章节创作工作流接口。

所有接口都按小说隔离：路径包含 novel_id，服务层再校验会话归属。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..database.db import WRITING_SESSION_STATUSES
from ..models.schemas import (
    WritingConfirmRequest,
    WritingDecisionResolveRequest,
    WritingDraftOut,
    WritingDraftUpdate,
    WritingPlanApproveRequest,
    WritingPlanGenerateRequest,
    WritingPlanUpdate,
    WritingSegmentGenerateRequest,
    WritingSegmentOut,
    WritingSessionCreate,
    WritingSessionOut,
    WritingSessionUpdate,
    WorldDeleteResult,
)
from ..services import writing_service
from ..services.errors import ServiceError
from ..services.writing_plan_schema import PLAN_SCHEMA

router = APIRouter(tags=["writing"])


def _err(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# ----------------------------- 工作流元信息 -----------------------------

@router.get("/ai/writing/plan-schema")
def writing_plan_schema() -> dict:
    """返回剧情计划 JSON Schema 与会话状态机，供前端展示与文档使用。"""
    return {
        "plan_schema": PLAN_SCHEMA,
        "session_statuses": list(WRITING_SESSION_STATUSES),
        "transitions": {
            "planning": ["awaiting_plan_approval", "failed", "cancelled"],
            "awaiting_plan_approval": ["writing", "awaiting_plan_approval",
                                       "failed", "cancelled"],
            "writing": ["paused_for_user", "draft_ready", "cancelled", "failed"],
            "paused_for_user": ["writing", "cancelled"],
            "draft_ready": ["completed", "writing", "cancelled"],
            "completed": [],
            "cancelled": [],
            "failed": ["awaiting_plan_approval", "cancelled"],
        },
    }


# ----------------------------- 创作会话 -----------------------------

@router.post("/novels/{novel_id}/writing-sessions")
def create_writing_session(novel_id: str, payload: WritingSessionCreate) -> dict:
    """创建会话；返回会话详情（含计划/决定/草稿的初始空值）。"""
    try:
        return writing_service.create_session(novel_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/writing-sessions", response_model=list[WritingSessionOut]
)
def list_writing_sessions(
    novel_id: str,
    status: str | None = Query(default=None, max_length=30),
) -> list[dict]:
    try:
        return writing_service.list_sessions(novel_id, status=status)
    except ServiceError as exc:
        raise _err(exc) from exc


# 固定子路径必须先于 /{session_id} 声明
@router.post("/novels/{novel_id}/writing-sessions/{session_id}/pause")
def pause_writing_session(novel_id: str, session_id: str) -> dict:
    try:
        return writing_service.pause_session(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/novels/{novel_id}/writing-sessions/{session_id}/resume")
def resume_writing_session(novel_id: str, session_id: str) -> dict:
    try:
        return writing_service.resume_session(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/novels/{novel_id}/writing-sessions/{session_id}/cancel")
def cancel_writing_session(novel_id: str, session_id: str) -> dict:
    try:
        return writing_service.cancel_session(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get("/novels/{novel_id}/writing-sessions/{session_id}")
def get_writing_session(novel_id: str, session_id: str) -> dict:
    """返回会话 + 当前计划 + 决定项 + 草稿与段落进度。"""
    try:
        return writing_service.get_session(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.patch("/novels/{novel_id}/writing-sessions/{session_id}")
def update_writing_session(
    novel_id: str, session_id: str, payload: WritingSessionUpdate
) -> dict:
    try:
        return writing_service.update_session(novel_id, session_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.delete(
    "/novels/{novel_id}/writing-sessions/{session_id}", response_model=WorldDeleteResult
)
def delete_writing_session(novel_id: str, session_id: str) -> dict:
    try:
        return writing_service.delete_session(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


# ----------------------------- 剧情计划 -----------------------------

@router.post("/novels/{novel_id}/writing-sessions/{session_id}/plan/generate")
async def generate_writing_plan(
    novel_id: str, session_id: str, payload: WritingPlanGenerateRequest
) -> dict:
    try:
        return await writing_service.generate_plan(
            novel_id, session_id, payload.model_dump()
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get("/novels/{novel_id}/writing-sessions/{session_id}/plan")
def get_writing_plan(novel_id: str, session_id: str) -> dict:
    try:
        return writing_service.get_current_plan(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get("/novels/{novel_id}/writing-sessions/{session_id}/plan/versions")
def list_writing_plan_versions(novel_id: str, session_id: str) -> list[dict]:
    try:
        return writing_service.list_plan_versions(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.put("/novels/{novel_id}/writing-sessions/{session_id}/plan")
def update_writing_plan(
    novel_id: str, session_id: str, payload: WritingPlanUpdate
) -> dict:
    try:
        return writing_service.update_plan(novel_id, session_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/novels/{novel_id}/writing-sessions/{session_id}/plan/approve")
def approve_writing_plan(
    novel_id: str, session_id: str, payload: WritingPlanApproveRequest
) -> dict:
    try:
        return writing_service.approve_plan(novel_id, session_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/writing-sessions/{session_id}/decisions/{decision_key}/resolve"
)
def resolve_writing_decision(
    novel_id: str,
    session_id: str,
    decision_key: str,
    payload: WritingDecisionResolveRequest,
) -> dict:
    try:
        return writing_service.resolve_decision(
            novel_id, session_id, decision_key, payload.model_dump()
        )
    except ServiceError as exc:
        raise _err(exc) from exc


# ----------------------------- 草稿与分段生成 -----------------------------

@router.get(
    "/novels/{novel_id}/writing-sessions/{session_id}/draft",
    response_model=WritingDraftOut,
)
def get_writing_draft(novel_id: str, session_id: str) -> dict:
    try:
        return writing_service.get_draft(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.put(
    "/novels/{novel_id}/writing-sessions/{session_id}/draft",
    response_model=WritingDraftOut,
)
def update_writing_draft(
    novel_id: str, session_id: str, payload: WritingDraftUpdate
) -> dict:
    try:
        return writing_service.update_draft(novel_id, session_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/writing-sessions/{session_id}/draft/segments/generate"
)
async def generate_writing_segment(
    novel_id: str, session_id: str, payload: WritingSegmentGenerateRequest
) -> dict:
    """生成一个段落（默认取下一个未完成段落），不生成整章。"""
    try:
        return await writing_service.generate_segment(
            novel_id, session_id, payload.model_dump()
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/writing-sessions/{session_id}/draft/segments/{sequence}/regenerate"
)
async def regenerate_writing_segment(
    novel_id: str,
    session_id: str,
    sequence: int,
    payload: WritingSegmentGenerateRequest,
) -> dict:
    try:
        return await writing_service.regenerate_segment(
            novel_id, session_id, sequence, payload.model_dump()
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/novels/{novel_id}/writing-sessions/{session_id}/draft/confirm")
def confirm_writing_draft(
    novel_id: str, session_id: str, payload: WritingConfirmRequest
) -> dict:
    """用户确认后写入正式章节；默认另存为新章节，绝不默认覆盖原章节。"""
    try:
        return writing_service.confirm_draft(
            novel_id, session_id, payload.model_dump()
        )
    except ServiceError as exc:
        raise _err(exc) from exc
