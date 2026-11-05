"""P4.1.1 AI 调用测试接口与统一调用服务测试。

覆盖：任务模型路由（显式 > 任务 > 默认）、各类失败（网络/超时/密钥/
模型不存在）、HTTP 200 空正文、reasoning_only、截断标记、usage 缺失、
任务记录（成功/失败）、任务查询与小说隔离、删除小说清理任务。
"""

import pytest
from app.adapters.base import AdapterError, CompletionResult
from app.services import model_router

SECRET_KEY = "sk-test-secret-1234567890abcd"


class FakeAdapter:
    """测试用假适配器：按预设返回结果或抛出错误。"""

    next_result: CompletionResult | None = None
    next_error: AdapterError | None = None

    def __init__(self, *args, **kwargs):
        self.timeout = 20.0

    async def chat(self, request):
        if FakeAdapter.next_error is not None:
            raise FakeAdapter.next_error
        result = FakeAdapter.next_result or CompletionResult(content="正文", model="m")
        result.model = result.model or request.model
        return result

    async def close(self):
        return None


@pytest.fixture()
def fake_factory(monkeypatch):
    monkeypatch.setattr(model_router.factory, "create_adapter", lambda *a, **kw: FakeAdapter())
    yield
    FakeAdapter.next_result = None
    FakeAdapter.next_error = None


def _create_novel(client, title="AI 测试小说"):
    r = client.post("/api/novels", json={"title": title})
    assert r.status_code == 200
    return r.json()


def _create_provider(client, **overrides):
    payload = {
        "name": "DeepSeek Official",
        "provider_type": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": SECRET_KEY,
        "enabled": True,
    }
    payload.update(overrides)
    r = client.post("/api/providers", json=payload)
    assert r.status_code == 200
    return r.json()


def _create_model(client, provider_id, model_id="deepseek-chat", name="剧情模型"):
    r = client.post(
        "/api/models",
        json={
            "provider_id": provider_id,
            "name": name,
            "model_id": model_id,
            "remark": "测试模型",
            "enabled": True,
        },
    )
    assert r.status_code == 200
    return r.json()


def _set_tasks(client, tasks=None, default_model_id=None):
    r = client.put(
        "/api/model-settings",
        json={"tasks": tasks or {}, "default_model_id": default_model_id},
    )
    assert r.status_code == 200
    return r.json()


def _generate(client, novel_id, **overrides):
    payload = {
        "novel_id": novel_id,
        "task_type": "writer",
        "user_prompt": "写一段测试文字",
    }
    payload.update(overrides)
    return client.post("/api/ai/generate", json=payload)


# ----------------------------- 模型路由 -----------------------------

def test_route_priority_explicit_task_default(client, fake_factory):
    novel = _create_novel(client)
    provider = _create_provider(client)
    model_a = _create_model(client, provider["id"], model_id="model-planner", name="规划模型")
    model_b = _create_model(client, provider["id"], model_id="model-default", name="默认模型")
    _set_tasks(client, tasks={"planner": model_a["id"]}, default_model_id=model_b["id"])

    FakeAdapter.next_result = CompletionResult(content="正文内容", model="model-planner")
    r = _generate(client, novel["id"], task_type="planner")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["resolved_from"] == "task"
    assert body["model"] == "model-planner"

    # writer 未配置任务模型 → 回退全局默认
    r2 = _generate(client, novel["id"], task_type="writer")
    body2 = r2.json()
    assert body2["success"] is True
    assert body2["resolved_from"] == "default"

    # 显式指定模型优先级最高
    r3 = _generate(client, novel["id"], task_type="planner", model_id=model_b["id"])
    body3 = r3.json()
    assert body3["success"] is True
    assert body3["resolved_from"] == "explicit"

    # 路由预览不发起请求
    preview = client.get("/api/ai/route", params={"task_type": "planner"}).json()
    assert preview["resolved"] is True
    assert preview["resolved_from"] == "task"
    assert preview["model_id"] == model_a["id"]


def test_explicit_model_not_found_and_no_model_configured(client, fake_factory):
    novel = _create_novel(client)
    # 完全没有任何模型配置
    r = _generate(client, novel["id"])
    assert r.status_code == 400
    assert "尚未" in r.json()["detail"]

    provider = _create_provider(client)
    model = _create_model(client, provider["id"])
    _set_tasks(client, default_model_id=model["id"])

    r2 = _generate(client, novel["id"], model_id="not-exist-model")
    assert r2.status_code == 400
    assert "不存在" in r2.json()["detail"] or "停用" in r2.json()["detail"]


def test_generate_novel_isolation(client, fake_factory):
    r = _generate(client, "ghost-novel")
    assert r.status_code == 404


def test_generate_response_never_leaks_api_key(client, fake_factory):
    novel = _create_novel(client)
    provider = _create_provider(client)
    model = _create_model(client, provider["id"])
    _set_tasks(client, default_model_id=model["id"])
    FakeAdapter.next_error = AdapterError("network", "连接失败")
    r = _generate(client, novel["id"])
    assert SECRET_KEY not in r.text


# ----------------------------- 响应处理 -----------------------------

def _setup_default_model(client):
    novel = _create_novel(client)
    provider = _create_provider(client)
    model = _create_model(client, provider["id"])
    _set_tasks(client, default_model_id=model["id"])
    return novel, model


def test_adapter_errors_mapped(client, fake_factory):
    novel, _ = _setup_default_model(client)
    cases = [
        ("timeout", "请求超时"),
        ("network", "连接失败"),
        ("invalid_key", "密钥无效"),
        ("model_not_found", "模型不存在"),
        ("server_error", "服务异常"),
    ]
    for code, message in cases:
        FakeAdapter.next_error = AdapterError(code, message)
        r = _generate(client, novel["id"])
        body = r.json()
        assert body["success"] is False
        assert body["error_code"] == code
        assert body["content"] == ""
        FakeAdapter.next_error = None


def test_empty_content_is_business_error(client, fake_factory):
    novel, _ = _setup_default_model(client)
    FakeAdapter.next_result = CompletionResult(content="", reasoning="", model="m")
    r = _generate(client, novel["id"])
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "empty_content"


def test_reasoning_only_is_not_success(client, fake_factory):
    novel, _ = _setup_default_model(client)
    FakeAdapter.next_result = CompletionResult(
        content="", reasoning="先思考世界观……", model="deepseek-reasoner"
    )
    r = _generate(client, novel["id"], include_reasoning=True)
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "reasoning_only"
    # 思维链必须能被区分返回，而不是伪装成正文
    assert body["reasoning"] == "先思考世界观……"
    assert body["content"] == ""

    # 默认不返回 reasoning
    r2 = _generate(client, novel["id"])
    assert r2.json()["reasoning"] == ""


def test_truncated_flag_on_length_finish(client, fake_factory):
    novel, _ = _setup_default_model(client)
    FakeAdapter.next_result = CompletionResult(
        content="被截断的正文", model="m", finish_reason="length"
    )
    r = _generate(client, novel["id"])
    body = r.json()
    assert body["success"] is True
    assert body["truncated"] is True
    assert body["finish_reason"] == "length"


def test_usage_missing_tolerated(client, fake_factory):
    novel, _ = _setup_default_model(client)
    FakeAdapter.next_result = CompletionResult(content="正文", model="m", usage={})
    r = _generate(client, novel["id"])
    body = r.json()
    assert body["success"] is True
    assert body["usage"] == {}


def test_unexpected_exception_handled(client, fake_factory, monkeypatch):
    novel, _ = _setup_default_model(client)

    class BoomAdapter(FakeAdapter):
        async def chat(self, request):
            raise RuntimeError("unexpected boom")

    monkeypatch.setattr(
        model_router.factory, "create_adapter", lambda *a, **kw: BoomAdapter()
    )
    r = _generate(client, novel["id"])
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "server_error"


# ----------------------------- 任务记录 -----------------------------

def test_tasks_recorded_for_success_and_failure(client, fake_factory):
    novel, model = _setup_default_model(client)
    FakeAdapter.next_result = CompletionResult(
        content="成功的正文内容，足够长用于摘要截断测试" * 3,
        model="deepseek-chat",
        usage={"prompt_tokens": 12, "completion_tokens": 34},
    )
    r = _generate(client, novel["id"])
    assert r.json()["success"] is True

    FakeAdapter.next_result = None
    FakeAdapter.next_error = AdapterError("timeout", "请求超时")
    r2 = _generate(client, novel["id"], task_type="editor")
    assert r2.json()["success"] is False

    tasks = client.get("/api/ai/tasks", params={"novel_id": novel["id"]}).json()
    assert len(tasks) == 2
    failed = [t for t in tasks if t["status"] == "failed"]
    done = [t for t in tasks if t["status"] == "completed"]
    assert len(failed) == 1 and len(done) == 1
    assert failed[0]["error_code"] == "timeout"
    assert done[0]["input_tokens"] == 12
    assert done[0]["output_tokens"] == 34
    assert done[0]["model_id"] == model["id"]
    assert done[0]["estimated_tokens"] is not None
    # 只保存摘要：不允许出现完整正文
    assert len(done[0]["output_summary"]) <= 220
    # 绝不记录密钥
    assert SECRET_KEY not in str(tasks)

    # 状态与类型筛选
    failed_only = client.get(
        "/api/ai/tasks", params={"novel_id": novel["id"], "status": "failed"}
    ).json()
    assert len(failed_only) == 1
    editor_only = client.get(
        "/api/ai/tasks", params={"novel_id": novel["id"], "task_type": "editor"}
    ).json()
    assert len(editor_only) == 1

    # 任务详情 + 跨小说隔离
    detail = client.get(
        f"/api/ai/tasks/{done[0]['id']}", params={"novel_id": novel["id"]}
    )
    assert detail.status_code == 200
    other = _create_novel(client, "另一本小说")
    cross = client.get(
        f"/api/ai/tasks/{done[0]['id']}", params={"novel_id": other["id"]}
    )
    assert cross.status_code == 404
    assert client.get(
        "/api/ai/tasks", params={"novel_id": other["id"]}
    ).json() == []


def test_delete_novel_cleans_ai_tasks(client, fake_factory):
    novel, _ = _setup_default_model(client)
    FakeAdapter.next_result = CompletionResult(content="正文", model="m")
    _generate(client, novel["id"])
    assert len(client.get("/api/ai/tasks", params={"novel_id": novel["id"]}).json()) == 1

    r = client.delete(f"/api/novels/{novel['id']}")
    assert r.status_code == 200
    assert client.get(
        "/api/ai/tasks", params={"novel_id": novel["id"]}
    ).status_code == 404
