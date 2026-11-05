"""P4.1.1 提示词模板测试。

覆盖：内置模板播种、CRUD、任务类型筛选、版本历史、
恢复旧版本、变量渲染校验（缺失变量拒绝、未替换变量不放行）。
"""


def _list(client, **params):
    return client.get("/api/ai/prompt-templates", params=params)


def test_seed_templates_exist(client):
    body = _list(client).json()
    assert len(body) == 4
    task_types = {t["task_type"] for t in body}
    assert task_types == {"planner", "writer", "editor", "assistant"}
    # 变量占位被正确解析
    writer = next(t for t in body if t["task_type"] == "writer")
    assert set(writer["variables"]) == {"context", "task"}
    assert writer["version"] == 1
    assert writer["is_active"] is True


def test_template_crud_and_filter(client):
    r = client.post(
        "/api/ai/prompt-templates",
        json={
            "name": "自定义规划模板",
            "task_type": "planner",
            "description": "测试用",
            "system_prompt": "你是规划师",
            "user_prompt_template": "上下文：{context}\n任务：{task}",
        },
    )
    assert r.status_code == 200
    created = r.json()
    assert created["version"] == 1
    assert set(created["variables"]) == {"context", "task"}

    planners = _list(client, task_type="planner").json()
    assert len(planners) == 2
    writers = _list(client, task_type="writer").json()
    assert all(t["task_type"] == "writer" for t in writers)

    got = client.get(f"/api/ai/prompt-templates/{created['id']}")
    assert got.status_code == 200

    deleted = client.delete(f"/api/ai/prompt-templates/{created['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/api/ai/prompt-templates/{created['id']}").status_code == 404


def test_invalid_task_type_rejected(client):
    r = client.post(
        "/api/ai/prompt-templates",
        json={"name": "坏模板", "task_type": "ghost"},
    )
    assert r.status_code == 422


def test_version_history_and_restore(client):
    created = client.post(
        "/api/ai/prompt-templates",
        json={
            "name": "版本模板",
            "task_type": "editor",
            "system_prompt": "第一版系统提示",
            "user_prompt_template": "第一版 {text}",
        },
    ).json()

    updated = client.put(
        f"/api/ai/prompt-templates/{created['id']}",
        json={"system_prompt": "第二版系统提示"},
    ).json()
    assert updated["version"] == 2

    versions = client.get(
        f"/api/ai/prompt-templates/{created['id']}/versions"
    ).json()
    assert len(versions) == 2
    assert versions[0]["version"] == 2  # 倒序
    assert versions[1]["version"] == 1
    assert versions[1]["system_prompt"] == "第一版系统提示"

    # 恢复旧版本：生成新版本而不是篡改历史
    restored = client.post(
        f"/api/ai/prompt-templates/{created['id']}/restore/1"
    ).json()
    assert restored["version"] == 3
    assert restored["system_prompt"] == "第一版系统提示"
    versions_after = client.get(
        f"/api/ai/prompt-templates/{created['id']}/versions"
    ).json()
    assert len(versions_after) == 3

    # 删除模板后版本级联清理
    client.delete(f"/api/ai/prompt-templates/{created['id']}")
    assert client.get(
        f"/api/ai/prompt-templates/{created['id']}/versions"
    ).status_code == 404


def test_render_variable_validation(client):
    created = client.post(
        "/api/ai/prompt-templates",
        json={
            "name": "渲染模板",
            "task_type": "writer",
            "system_prompt": "你是作者",
            "user_prompt_template": "上下文：{context}\n要求：{task}",
        },
    ).json()

    # 缺少必需变量 → 400，绝不允许未替换变量发给模型
    missing = client.post(
        "/api/ai/prompt-templates/render",
        json={"template_id": created["id"], "variables": {"context": "资料"}},
    )
    assert missing.status_code == 400
    assert "task" in missing.json()["detail"]

    # 完整变量 → 渲染成功且无占位符残留
    ok = client.post(
        "/api/ai/prompt-templates/render",
        json={
            "template_id": created["id"],
            "variables": {"context": "小说资料", "task": "写第一章"},
        },
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["user_prompt"] == "上下文：小说资料\n要求：写第一章"
    assert "{" not in body["user_prompt"]
    assert body["version"] == 1


def test_render_does_not_execute_template_code(client):
    """类 format 的属性访问/表达式不应被求值，只能作为纯文本变量名。"""
    created = client.post(
        "/api/ai/prompt-templates",
        json={
            "name": "安全模板",
            "task_type": "assistant",
            "system_prompt": "你是助手",
            "user_prompt_template": "数据：{task}",
        },
    ).json()
    r = client.post(
        "/api/ai/prompt-templates/render",
        json={
            "template_id": created["id"],
            "variables": {"task": "{__import__('os')}"},
        },
    )
    assert r.status_code == 200
    # 变量值只做纯文本替换，不会被二次解析执行
    assert "__import__" in r.json()["user_prompt"]
