import sys

from fastapi import APIRouter

from ..core.config import DATA_DIR, get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """健康检查：确认后端服务可用。"""
    settings = get_settings()
    return {
        "status": "ok",
        "version": settings.version,
        "message": "StoryForge 后端服务运行正常",
    }


@router.get("/system/info")
def system_info() -> dict:
    """系统信息：项目名称、版本、Python 版本与数据目录状态。"""
    settings = get_settings()
    novels_dir = DATA_DIR / "novels"
    backups_dir = DATA_DIR / "backups"
    return {
        "project_name": settings.app_name,
        "version": settings.version,
        "python_version": sys.version.split()[0],
        "data_dir": str(DATA_DIR),
        "data_dir_status": {
            "exists": DATA_DIR.exists(),
            "novels_dir": novels_dir.exists(),
            "backups_dir": backups_dir.exists(),
        },
    }
