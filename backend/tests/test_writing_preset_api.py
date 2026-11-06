"""P4.2 写作预设管理测试：CRUD、复制、默认、按小说指定、提示词注入。"""


def _novel(client, title="预设测试小说"):
    return client.post("/api/novels", json={"title": title}).json()


def _preset(client, name="冷峻预设", **overrides):
    payload = {
        "name": name,
        "description": "测试预设",
        "system_prompt": f"系统提示::{name}",
        "config": {"writing_style": "冷峻克制", "person": "第三人称"},
    }
    payload.update(overrides)
    response = client.post("/api/writing-presets", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _provider_and_model(client, model_identifier="test-writer-alt"):
    provider = client.post(
        "/api/providers",
        json={
            "name": f"Preset Provider {model_identifier}",
            "provider_type": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-preset-test-1234567890",
            "enabled": True,
        },
    ).json()
    return client.post(
        "/api/models",
        json={
            "provider_id": provider["id"],
            "name": "备用模型",
            "model_id": model_identifier,
            "enabled": True,
        },
    ).json()


def _generate(client, novel_id, session_id, fake_ai, text="第一段正文。"):
    fake_ai.push_text(text)
    response = client.post(
        f"/api/novels/{novel_id}/quick-writing-sessions/{session_id}/generate",
        json={},
    )
    assert response.status_code == 200, response.text
    return response.json(), fake_ai.requests[-1]


def test_preset_crud_copy_and_default(client):
    preset = _preset(client)
    assert preset["config"]["writing_style"] == "冷峻克制"
    assert preset["is_default"] is False

    listed = client.get("/api/writing-presets").json()
    assert any(item["id"] == preset["id"] for item in listed)

    updated = client.put(
        f"/api/writing-presets/{preset['id']}",
        json={"name": "改名预设", "config": {"language_style": "文言文"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "改名预设"
    assert updated.json()["config"]["language_style"] == "文言文"
    assert updated.json()["version"] == preset["version"] + 1

    copied = client.post(
        f"/api/writing-presets/{preset['id']}/copy", json={"name": "副本预设"}
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["name"] == "副本预设"
    assert copied.json()["id"] != preset["id"]

    defaulted = client.post(f"/api/writing-presets/{preset['id']}/default")
    assert defaulted.status_code == 200
    assert defaulted.json()["is_default"] is True

    deleted = client.delete(f"/api/writing-presets/{copied.json()['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/api/writing-presets/{copied.json()['id']}").status_code == 404


def test_preset_is_isolated_from_prompt_templates(client):
    _preset(client, name="不应出现在模板列表")
    templates = client.get("/api/ai/prompt-templates").json()
    assert all(item["name"] != "不应出现在模板列表" for item in templates)


def test_novel_preset_assignment(client):
    novel = _novel(client)
    preset = _preset(client, name="小说指定预设")

    assigned = client.put(
        f"/api/novels/{novel['id']}/writing-preset",
        json={"preset_id": preset["id"]},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["preset_id"] == preset["id"]

    fetched = client.get(f"/api/novels/{novel['id']}/writing-preset").json()
    assert fetched["preset"]["name"] == "小说指定预设"

    cleared = client.put(
        f"/api/novels/{novel['id']}/writing-preset", json={"preset_id": None}
    )
    assert cleared.json()["preset_id"] is None


def test_generation_without_preset_uses_default_writer(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = client.post(
        f"/api/novels/{novel['id']}/quick-writing-sessions",
        json={"user_requirement": "写一段雨夜追逐", "preset_id": None},
    ).json()
    assert session["preset_id"] is None

    data, request = _generate(client, novel["id"], session["id"], fake_ai)
    system_prompt = request.messages[0].content
    assert "长篇小说的正文作者" in system_prompt
    assert data["session"]["content"] == "第一段正文。"


def test_preset_injected_and_overrides_are_temporary(client, fake_ai, ai_task_models):
    novel = _novel(client)
    preset = _preset(client, name="注入预设")
    session = client.post(
        f"/api/novels/{novel['id']}/quick-writing-sessions",
        json={"preset_id": preset["id"], "user_requirement": "继续写冲突"},
    ).json()
    assert session["preset_id"] == preset["id"]
    assert session["preset_name"] == "注入预设"

    _, request = _generate(client, novel["id"], session["id"], fake_ai)
    system_prompt = request.messages[0].content
    assert "系统提示::注入预设" in system_prompt
    assert "冷峻克制" in system_prompt

    # 临时覆盖只作用于本次会话，不改动原预设
    client.patch(
        f"/api/novels/{novel['id']}/quick-writing-sessions/{session['id']}",
        json={
            "style_overrides": {"writing_style": "临时热辣风格"},
            "user_requirement": "临时要求：加强环境描写",
        },
    )
    _, second_request = _generate(client, novel["id"], session["id"], fake_ai, "第二段。")
    second_system = second_request.messages[0].content
    assert "临时热辣风格" in second_system
    assert "冷峻克制" not in second_system

    refreshed = client.get(f"/api/writing-presets/{preset['id']}").json()
    assert refreshed["config"]["writing_style"] == "冷峻克制"
    assert refreshed["system_prompt"] == "系统提示::注入预设"


def test_model_switch_uses_selected_model(client, fake_ai, ai_task_models):
    novel = _novel(client)
    alt_model = _provider_and_model(client)
    session = client.post(
        f"/api/novels/{novel['id']}/quick-writing-sessions",
        json={"model_id": alt_model["id"], "user_requirement": "测试模型切换"},
    ).json()
    assert session["model_label"] == "备用模型"

    _, request = _generate(client, novel["id"], session["id"], fake_ai)
    assert request.model == "test-writer-alt"


def test_different_novels_use_different_presets(client, fake_ai, ai_task_models):
    novel_a = _novel(client, "小说甲")
    novel_b = _novel(client, "小说乙")
    preset_a = _preset(client, name="甲预设", system_prompt="甲标记提示")
    preset_b = _preset(client, name="乙预设", system_prompt="乙标记提示")
    client.put(
        f"/api/novels/{novel_a['id']}/writing-preset",
        json={"preset_id": preset_a["id"]},
    )
    client.put(
        f"/api/novels/{novel_b['id']}/writing-preset",
        json={"preset_id": preset_b["id"]},
    )

    session_a = client.post(
        f"/api/novels/{novel_a['id']}/quick-writing-sessions", json={}
    ).json()
    session_b = client.post(
        f"/api/novels/{novel_b['id']}/quick-writing-sessions", json={}
    ).json()
    assert session_a["preset_id"] == preset_a["id"]
    assert session_b["preset_id"] == preset_b["id"]

    _, request_a = _generate(client, novel_a["id"], session_a["id"], fake_ai)
    _, request_b = _generate(client, novel_b["id"], session_b["id"], fake_ai)
    assert "甲标记提示" in request_a.messages[0].content
    assert "乙标记提示" in request_b.messages[0].content
