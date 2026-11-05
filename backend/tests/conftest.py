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


class FakeAIQueue:
    """可编程的假模型适配器队列，供 P4.1.2 创作工作流测试使用。"""

    def __init__(self) -> None:
        self.items: list = []

    def push(self, item) -> None:
        self.items.append(item)

    def push_text(self, content: str, *, reasoning: str = "",
                  finish_reason: str | None = None, usage: dict | None = None) -> None:
        from app.adapters.base import CompletionResult

        self.push(
            CompletionResult(
                content=content,
                model="",
                reasoning=reasoning,
                finish_reason=finish_reason,
                usage=usage or {"prompt_tokens": 10, "completion_tokens": 20},
                latency_ms=123,
            )
        )

    def push_error(self, code: str = "network_error") -> None:
        from app.adapters.base import AdapterError

        self.push(AdapterError(code, "模拟网络错误"))

    def __len__(self) -> int:
        return len(self.items)


@pytest.fixture()
def fake_ai(monkeypatch):
    """替换适配器工厂，所有 AI 调用都从队列取结果。"""
    from app.services import model_router

    queue = FakeAIQueue()

    class _Adapter:
        def __init__(self, *args, **kwargs):
            self.timeout = 20.0

        async def chat(self, request):
            from app.adapters.base import CompletionResult

            if not queue.items:
                return CompletionResult(content="默认正文内容。", model=request.model)
            item = queue.items.pop(0)
            if isinstance(item, Exception):
                raise item
            item.model = item.model or request.model
            return item

        async def close(self) -> None:
            return None

    monkeypatch.setattr(
        model_router.factory, "create_adapter", lambda *a, **kw: _Adapter()
    )
    return queue


@pytest.fixture()
def ai_task_models(client):
    """配置 planner / writer 任务模型，返回模型 id。"""
    provider = client.post(
        "/api/providers",
        json={
            "name": "Writing Test Provider",
            "provider_type": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-writing-test-1234567890",
            "enabled": True,
        },
    ).json()
    planner = client.post(
        "/api/models",
        json={
            "provider_id": provider["id"],
            "name": "规划模型",
            "model_id": "test-planner",
            "enabled": True,
        },
    ).json()
    writer = client.post(
        "/api/models",
        json={
            "provider_id": provider["id"],
            "name": "写作模型",
            "model_id": "test-writer",
            "enabled": True,
        },
    ).json()
    client.put(
        "/api/model-settings",
        json={"tasks": {"planner": planner["id"], "writer": writer["id"]},
              "default_model_id": writer["id"]},
    )
    return {"planner": planner["id"], "writer": writer["id"]}
