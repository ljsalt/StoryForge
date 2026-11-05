import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    """把数据库与密钥文件隔离到临时目录，避免污染真实数据。"""
    from app.core import security
    from app.core.config import get_settings

    current = get_settings()
    monkeypatch.setattr(current, "database_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        current, "secret_key_file", str(tmp_path / "secrets" / "fernet.key")
    )
    monkeypatch.setattr(current, "model_request_timeout", 2.0)
    security._cached_fernet = None
    security._cached_key_path = None
    return current


@pytest.fixture()
def client(settings):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
