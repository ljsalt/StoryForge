"""P4.1.3 章节连续性检查与剧情记忆更新接口。

所有接口都按小说隔离：路径包含 novel_id，服务层再校验章节/批次/提案归属。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models.schemas import (
    ContinuityCheckCreate,
    ContinuityCheckOut,
    MemoryApplyResult,
    MemoryBatchCreate,
    MemoryBatchOut,
    MemoryBatchReviewRequest,
    MemoryProposalOut,
    MemoryProposalReviewAction,
    MemoryProposalUpdate,
)
from ..services import continuity_service, memory_service
from ..services.continuity_report_schema import REPORT_SCHEMA
from ..services.errors import ServiceError

router = APIRouter(tags=["continuity"])


def _err(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# ----------------------------- 连续性检查 -----------------------------

@router.get("/continuity/report-schema")
def continuity_report_schema() -> dict:
    """返回检查报告 JSON Schema，供前端展示与文档使用。"""
    return {"report_schema": REPORT_SCHEMA}


@router.post(
    "/novels/{novel_id}/chapters/{chapter_id}/continuity-checks",
    response_model=ContinuityCheckOut,
    status_code=201,
)
async def create_continuity_check(
    novel_id: str, chapter_id: str, payload: ContinuityCheckCreate
) -> dict:
    """创建并执行一次连续性检查（同步等待 AI 结果）。"""
    try:
        return await continuity_service.create_check(novel_id, chapter_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/chapters/{chapter_id}/continuity-checks",
    response_model=list[ContinuityCheckOut],
)
def list_continuity_checks(novel_id: str, chapter_id: str) -> list[dict]:
    """章节的全部历史检查记录（最新在前，永不覆盖）。"""
    try:
        return continuity_service.list_checks(novel_id, chapter_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/continuity-checks/{check_id}",
    response_model=ContinuityCheckOut,
)
def get_continuity_check(novel_id: str, check_id: str) -> dict:
    try:
        return continuity_service.get_check(novel_id, check_id)
    except ServiceError as exc:
        raise _err(exc) from exc


# ----------------------------- 记忆更新批次与提案 -----------------------------

@router.post(
    "/novels/{novel_id}/chapters/{chapter_id}/memory-batches",
    response_model=MemoryBatchOut,
    status_code=201,
)
async def create_memory_batch(
    novel_id: str, chapter_id: str, payload: MemoryBatchCreate
) -> dict:
    """创建并执行一次剧情变化提取（AI 只生成提案，不改正式数据）。"""
    try:
        return await memory_service.create_batch(novel_id, chapter_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/chapters/{chapter_id}/memory-batches",
    response_model=list[MemoryBatchOut],
)
def list_memory_batches(novel_id: str, chapter_id: str) -> list[dict]:
    try:
        return memory_service.list_batches(novel_id, chapter_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get("/novels/{novel_id}/memory-batches/{batch_id}", response_model=MemoryBatchOut)
def get_memory_batch(novel_id: str, batch_id: str) -> dict:
    try:
        return memory_service.get_batch(novel_id, batch_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/memory-batches/{batch_id}/proposals",
    response_model=list[MemoryProposalOut],
)
def list_memory_proposals(novel_id: str, batch_id: str) -> list[dict]:
    try:
        return memory_service.list_proposals(novel_id, batch_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/memory-proposals/{proposal_id}",
    response_model=MemoryProposalOut,
)
def get_memory_proposal(novel_id: str, proposal_id: str) -> dict:
    try:
        return memory_service.get_proposal(novel_id, proposal_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.patch(
    "/novels/{novel_id}/memory-proposals/{proposal_id}",
    response_model=MemoryProposalOut,
)
def update_memory_proposal(
    novel_id: str, proposal_id: str, payload: MemoryProposalUpdate
) -> dict:
    """修改提案内容：用户修改后的内容才是最终提交内容。"""
    try:
        return memory_service.update_proposal(novel_id, proposal_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/memory-proposals/{proposal_id}/accept",
    response_model=MemoryProposalOut,
)
def accept_memory_proposal(
    novel_id: str, proposal_id: str, payload: MemoryProposalReviewAction
) -> dict:
    try:
        return memory_service.accept_proposal(novel_id, proposal_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/memory-proposals/{proposal_id}/reject",
    response_model=MemoryProposalOut,
)
def reject_memory_proposal(
    novel_id: str, proposal_id: str, payload: MemoryProposalReviewAction
) -> dict:
    try:
        return memory_service.reject_proposal(novel_id, proposal_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/memory-batches/{batch_id}/review",
    response_model=MemoryBatchOut,
)
def review_memory_batch(
    novel_id: str, batch_id: str, payload: MemoryBatchReviewRequest
) -> dict:
    """批量审核提案（accept/reject/modify/reset），不绕过任何数据校验。"""
    try:
        return memory_service.review_batch(novel_id, batch_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/memory-batches/{batch_id}/apply",
    response_model=MemoryApplyResult,
)
def apply_memory_batch(novel_id: str, batch_id: str) -> dict:
    """提交已接受提案：单一事务整体应用或整体回滚。"""
    try:
        return memory_service.apply_batch(novel_id, batch_id)
    except ServiceError as exc:
        raise _err(exc) from exc
