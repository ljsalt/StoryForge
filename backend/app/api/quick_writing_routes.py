"""P4.2 快速写作与写作预设接口。

所有接口按小说隔离；预设与模型完全解耦，接口不返回任何密钥。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    NovelWritingPresetAssign,
    QuickWritingConfirmRequest,
    QuickWritingContentUpdate,
    QuickWritingGenerateRequest,
    QuickWritingSessionCreate,
    QuickWritingSessionOut,
    QuickWritingSessionUpdate,
    WritingPresetCopy,
    WritingPresetCreate,
    WritingPresetOut,
    WritingPresetUpdate,
)
from ..services import quick_writing_service, writing_preset_service
from ..services.errors import ServiceError

router = APIRouter(tags=["quick-writing"])


def _err(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/quick-writing/meta")
def quick_writing_meta() -> dict:
    """返回上下文模式与可自定义分区，供前端渲染设置面板。"""
    return {
        "context_modes": ["auto", "recent", "full", "custom"],
        "context_mode_labels": {
            "auto": "自动（小说记忆 + 最近章节）",
            "recent": "最近章节优先",
            "full": "完整设定",
            "custom": "自定义注入内容",
        },
        "section_keys": list(quick_writing_service.CONTEXT_SECTION_KEYS),
        "section_labels": {
            "core_settings": "核心设定与世界观",
            "current_task": "当前章节与写作要求",
            "characters": "人物档案",
            "character_states": "人物当前状态",
            "character_relations": "人物关系",
            "character_secrets": "人物秘密",
            "plot_history": "剧情历史与章节摘要",
        },
    }


# ----------------------------- 写作预设 -----------------------------

@router.get("/writing-presets", response_model=list[WritingPresetOut])
def list_writing_presets(
    include_inactive: bool = Query(default=True),
) -> list[dict]:
    try:
        return writing_preset_service.list_presets(include_inactive=include_inactive)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/writing-presets", response_model=WritingPresetOut)
def create_writing_preset(payload: WritingPresetCreate) -> dict:
    try:
        return writing_preset_service.create_preset(payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get("/writing-presets/{preset_id}", response_model=WritingPresetOut)
def get_writing_preset(preset_id: str) -> dict:
    try:
        return writing_preset_service.get_preset(preset_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.put("/writing-presets/{preset_id}", response_model=WritingPresetOut)
def update_writing_preset(preset_id: str, payload: WritingPresetUpdate) -> dict:
    try:
        return writing_preset_service.update_preset(preset_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.delete("/writing-presets/{preset_id}")
def delete_writing_preset(preset_id: str) -> dict:
    try:
        return writing_preset_service.delete_preset(preset_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/writing-presets/{preset_id}/copy", response_model=WritingPresetOut)
def copy_writing_preset(preset_id: str, payload: WritingPresetCopy) -> dict:
    try:
        return writing_preset_service.copy_preset(preset_id, payload.name)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/writing-presets/{preset_id}/default", response_model=WritingPresetOut)
def set_default_writing_preset(preset_id: str) -> dict:
    try:
        return writing_preset_service.set_default_preset(preset_id)
    except ServiceError as exc:
        raise _err(exc) from exc


# ----------------------------- 按小说指定预设 -----------------------------

@router.get("/novels/{novel_id}/writing-preset")
def get_novel_writing_preset(novel_id: str) -> dict:
    try:
        return writing_preset_service.get_novel_preset(novel_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.put("/novels/{novel_id}/writing-preset")
def set_novel_writing_preset(novel_id: str, payload: NovelWritingPresetAssign) -> dict:
    try:
        return writing_preset_service.set_novel_preset(novel_id, payload.preset_id)
    except ServiceError as exc:
        raise _err(exc) from exc


# ----------------------------- 快速写作会话 -----------------------------

@router.get(
    "/novels/{novel_id}/quick-writing-sessions",
    response_model=list[QuickWritingSessionOut],
)
def list_quick_writing_sessions(
    novel_id: str,
    status: str | None = Query(default=None, max_length=20),
) -> list[dict]:
    try:
        return quick_writing_service.list_sessions(novel_id, status=status)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/quick-writing-sessions",
    response_model=QuickWritingSessionOut,
)
def create_quick_writing_session(
    novel_id: str, payload: QuickWritingSessionCreate
) -> dict:
    try:
        return quick_writing_service.create_session(novel_id, payload.model_dump())
    except ServiceError as exc:
        raise _err(exc) from exc


@router.get(
    "/novels/{novel_id}/quick-writing-sessions/{session_id}",
    response_model=QuickWritingSessionOut,
)
def get_quick_writing_session(novel_id: str, session_id: str) -> dict:
    try:
        return quick_writing_service.get_session(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.patch(
    "/novels/{novel_id}/quick-writing-sessions/{session_id}",
    response_model=QuickWritingSessionOut,
)
def update_quick_writing_session(
    novel_id: str, session_id: str, payload: QuickWritingSessionUpdate
) -> dict:
    try:
        return quick_writing_service.update_session(
            novel_id, session_id, payload.model_dump(exclude_unset=True)
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.delete("/novels/{novel_id}/quick-writing-sessions/{session_id}")
def delete_quick_writing_session(novel_id: str, session_id: str) -> dict:
    try:
        return quick_writing_service.delete_session(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/novels/{novel_id}/quick-writing-sessions/{session_id}/discard",
             response_model=QuickWritingSessionOut)
def discard_quick_writing_session(novel_id: str, session_id: str) -> dict:
    try:
        return quick_writing_service.discard_session(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/novels/{novel_id}/quick-writing-sessions/{session_id}/generate")
async def generate_quick_writing_segment(
    novel_id: str, session_id: str, payload: QuickWritingGenerateRequest
) -> dict:
    try:
        return await quick_writing_service.generate_segment(
            novel_id, session_id, payload.model_dump()
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.put(
    "/novels/{novel_id}/quick-writing-sessions/{session_id}/content",
    response_model=QuickWritingSessionOut,
)
def update_quick_writing_content(
    novel_id: str, session_id: str, payload: QuickWritingContentUpdate
) -> dict:
    try:
        return quick_writing_service.update_content(
            novel_id, session_id, payload.content
        )
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post(
    "/novels/{novel_id}/quick-writing-sessions/{session_id}/context-preview"
)
def preview_quick_writing_context(novel_id: str, session_id: str) -> dict:
    try:
        return quick_writing_service.preview_context(novel_id, session_id)
    except ServiceError as exc:
        raise _err(exc) from exc


@router.post("/novels/{novel_id}/quick-writing-sessions/{session_id}/confirm")
def confirm_quick_writing_session(
    novel_id: str, session_id: str, payload: QuickWritingConfirmRequest
) -> dict:
    try:
        return quick_writing_service.confirm_session(
            novel_id, session_id, payload.model_dump()
        )
    except ServiceError as exc:
        raise _err(exc) from exc
