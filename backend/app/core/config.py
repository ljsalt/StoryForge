from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（StoryForge/）
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "storyforge.db"
DEFAULT_SECRET_KEY_FILE = DATA_DIR / "secrets" / "fernet.key"


class Settings(BaseSettings):
    """应用配置。默认值即可运行，也可用项目根目录的 .env 覆盖。"""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "StoryForge"
    version: str = "0.4.0-P3.3"
    host: str = "0.0.0.0"
    port: int = 8000
    # 允许的前端来源（逗号分隔），局域网来源由 main.py 中的正则统一放行
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # SQLite 数据库文件
    database_path: str = str(DEFAULT_DB_PATH)
    # API Key 加密主密钥文件（仅保存在后端本地，禁止提交 Git）
    secret_key_file: str = str(DEFAULT_SECRET_KEY_FILE)

    # 调用第三方模型接口的超时（秒）
    model_request_timeout: float = 20.0
    # 是否允许把模型 Base URL 指向本机/内网地址。
    # 默认关闭以降低 SSRF 风险；本地部署模型时可显式开启。
    allow_private_endpoints: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
