from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.ai_routes import router as ai_router
from .api.chapter_routes import router as chapter_router
from .api.character_relation_routes import router as character_relation_router
from .api.character_routes import router as character_router
from .api.model_routes import router as model_router
from .api.novel_routes import router as novel_router
from .api.plot_event_routes import router as plot_event_router
from .api.routes import router
from .api.world_routes import router as world_router
from .api.writing_routes import router as writing_router
from .core.config import DATA_DIR, get_settings
from .database.db import init_database
from .services import ai_task_service, prompt_template_service, writing_service

settings = get_settings()

# 放行可信局域网来源（私有网段 + localhost），供手机/其他设备访问开发服务器。
# 仅限本地开发使用，请勿将服务暴露到公网。
CORS_ORIGIN_REGEX = (
    r"https?://(localhost|127\.0\.0\.1"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时确保数据目录存在
    (DATA_DIR / "novels").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "backups").mkdir(parents=True, exist_ok=True)
    # 幂等初始化数据库，不会删除或覆盖已有数据
    init_database()
    # 首次启动播种内置提示词模板（已有模板时跳过）
    prompt_template_service.seed_default_templates()
    # 进程重启前不可能仍有真实执行中的 AI 调用：遗留 running 记录标记为失败
    ai_task_service.interrupt_running_tasks()
    # 创作会话同理：重启时仍在写作/生成中的记录标记为可恢复状态
    writing_service.recover_interrupted_sessions()
    yield


app = FastAPI(title="StoryForge API", version=settings.version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(model_router, prefix="/api")
app.include_router(novel_router, prefix="/api")
app.include_router(world_router, prefix="/api")
app.include_router(character_router, prefix="/api")
app.include_router(character_relation_router, prefix="/api")
app.include_router(chapter_router, prefix="/api")
app.include_router(plot_event_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(writing_router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"message": "StoryForge API", "docs": "/docs"}
