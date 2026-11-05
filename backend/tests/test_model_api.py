"""P2 模型接口自动化测试。

覆盖：Provider/Model CRUD、API Key 加密与脱敏、任务模型分配、
级联删除、连接测试错误分类、P1 接口回归。
"""

import sqlite3

SECRET_KEY = "sk-test-secret-1234567890abcd"


def _create_provider(client, **overrides):
    payload = {
        "name": "DeepSeek Official",
        "provider_type": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": SECRET_KEY,
        "enabled": True,
    }
    payload.update(overrides)
    return client.post("/api/providers", json=payload)


def _create_model(client, provider_id, model_id="deepseek-chat", name="剧情模型"):
    return client.post(
        "/api/models",
        json={
            "provider_id": provider_id,
            "name": name,
            "model_id": model_id,
            "remark": "测试模型",
            "enabled": True,
        },
    )


def test_p1_endpoints_still_work(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    info = client.get("/api/system/info")
    assert info.status_code == 200
    assert info.json()["project_name"] == "StoryForge"


def test_create_provider_hides_api_key(client, settings):
    response = _create_provider(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_api_key"] is True
    assert body["api_key_masked"].startswith("sk-")
    assert body["api_key_masked"].endswith("abcd")
    assert SECRET_KEY not in response.text
    assert "api_key_encrypted" not in body

    # 数据库中不得出现明文密钥
    conn = sqlite3.connect(settings.database_path)
    try:
        stored = conn.execute(
            "SELECT api_key_encrypted FROM providers"
        ).fetchone()[0]
    finally:
        conn.close()
    assert SECRET_KEY not in stored
    assert stored.startswith("gAAAAA")  # Fernet Token 前缀


def test_provider_list_and_update(client):
    created = _create_provider(client).json()
    listed = client.get("/api/providers").json()
    assert listed[0]["id"] == created["id"]

    updated = client.put(
        f"/api/providers/{created['id']}",
        json={"name": "DeepSeek 备用", "enabled": False},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "DeepSeek 备用"
    assert body["enabled"] is False
    # 未传 api_key 时密钥保持不变
    assert body["has_api_key"] is True
    assert SECRET_KEY not in updated.text


def test_clear_api_key(client):
    created = _create_provider(client).json()
    updated = client.put(
        f"/api/providers/{created['id']}", json={"api_key": ""}
    )
    assert updated.status_code == 200
    assert updated.json()["has_api_key"] is False
    assert updated.json()["api_key_masked"] == ""


def test_duplicate_provider_name_rejected(client):
    _create_provider(client)
    duplicate = _create_provider(client, name="DeepSeek Official")
    assert duplicate.status_code == 409
    assert "已存在" in duplicate.json()["detail"]


def test_invalid_base_url_rejected(client):
    response = _create_provider(client, base_url="ftp://api.deepseek.com")
    assert response.status_code == 400
    assert "http" in response.json()["detail"]

    private = _create_provider(client, base_url="http://127.0.0.1:11434")
    assert private.status_code == 400
    assert "内网" in private.json()["detail"] or "本机" in private.json()["detail"]


def test_model_crud_and_unique(client):
    provider = _create_provider(client).json()
    model = _create_model(client, provider["id"])
    assert model.status_code == 200, model.text
    body = model.json()
    assert body["provider_name"] == "DeepSeek Official"
    assert body["model_id"] == "deepseek-chat"

    duplicate = _create_model(client, provider["id"])
    assert duplicate.status_code == 409

    updated = client.put(
        f"/api/models/{body['id']}", json={"remark": "已修改", "enabled": False}
    )
    assert updated.status_code == 200
    assert updated.json()["remark"] == "已修改"

    listed = client.get("/api/models").json()
    assert len(listed) == 1

    deleted = client.delete(f"/api/models/{body['id']}")
    assert deleted.status_code == 200
    assert client.get("/api/models").json() == []


def test_model_settings_assign_and_fallback(client):
    provider = _create_provider(client).json()
    model_a = _create_model(client, provider["id"], "deepseek-chat", "模型A").json()
    model_b = _create_model(client, provider["id"], "deepseek-reasoner", "模型B").json()

    saved = client.put(
        "/api/model-settings",
        json={
            "tasks": {"planner": model_a["id"], "writer": model_b["id"]},
            "default_model_id": model_a["id"],
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    tasks = {item["task"]: item["model_id"] for item in body["tasks"]}
    assert tasks["planner"] == model_a["id"]
    assert tasks["writer"] == model_b["id"]
    assert tasks["editor"] is None
    assert body["default_model_id"] == model_a["id"]

    # ModelRouter：未配置任务回退到全局默认模型
    from app.services.model_router import resolve_model_for_task

    assert resolve_model_for_task("editor").resolved_from == "default"
    assert resolve_model_for_task("planner").resolved_from == "task"

    # 删除被引用的模型后，任务分配应自动置空
    client.delete(f"/api/models/{model_b['id']}")
    after = client.get("/api/model-settings").json()
    tasks_after = {item["task"]: item["model_id"] for item in after["tasks"]}
    assert tasks_after["writer"] is None
    assert tasks_after["planner"] == model_a["id"]
    assert resolve_model_for_task("writer").resolved_from == "default"


def test_delete_provider_cascades(client):
    provider = _create_provider(client).json()
    model = _create_model(client, provider["id"]).json()
    client.put(
        "/api/model-settings",
        json={"tasks": {"planner": model["id"]}, "default_model_id": model["id"]},
    )

    response = client.delete(f"/api/providers/{provider['id']}")
    assert response.status_code == 200
    assert response.json()["deleted_models"] == 1

    assert client.get("/api/providers").json() == []
    assert client.get("/api/models").json() == []
    settings_body = client.get("/api/model-settings").json()
    assert all(item["model_id"] is None for item in settings_body["tasks"])
    assert settings_body["default_model_id"] is None


def test_test_model_without_key(client):
    provider = _create_provider(client, api_key=None).json()
    model = _create_model(client, provider["id"]).json()

    result = client.post("/api/models/test", json={"model_id": model["id"]})
    assert result.status_code == 200
    body = result.json()
    assert body["success"] is False
    assert body["error_code"] == "missing_api_key"
    assert "API Key" in body["message"]


def test_test_model_network_error(client):
    provider = _create_provider(
        client, base_url="https://not-exist.example-domain.invalid"
    ).json()
    model = _create_model(client, provider["id"]).json()

    result = client.post("/api/models/test", json={"model_id": model["id"]})
    assert result.status_code == 200
    body = result.json()
    assert body["success"] is False
    assert body["error_code"] in ("network_error", "timeout")
    assert SECRET_KEY not in result.text


def test_model_settings_rejects_unknown_model(client):
    response = client.put(
        "/api/model-settings",
        json={"tasks": {"planner": "not-exist-id"}, "default_model_id": None},
    )
    assert response.status_code == 400
    assert "不存在" in response.json()["detail"]
