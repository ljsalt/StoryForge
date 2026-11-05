"""P4.1.1 上下文组装器测试。

覆盖：分区组装、小说隔离、Token 预算截断与省略说明、
秘密视角过滤（作者/叙事/角色）、章节上下文关联。
"""


def _create_novel(client, title="上下文小说"):
    r = client.post("/api/novels", json={"title": title, "description": "一本测试小说"})
    assert r.status_code == 200
    return r.json()


def _create_character(client, novel_id, name, **extra):
    payload = {"name": name, "role": "主角", "personality": "沉稳"}
    payload.update(extra)
    r = client.post(f"/api/novels/{novel_id}/characters", json=payload)
    assert r.status_code == 200
    return r.json()


def _create_world_entry(client, novel_id, name="青云山"):
    cat = client.post(
        f"/api/novels/{novel_id}/world/categories", json={"name": "地点"}
    )
    r = client.post(
        f"/api/novels/{novel_id}/world/entries",
        json={"name": name, "category_id": cat.json()["id"], "summary": "剑修圣地"},
    )
    assert r.status_code == 200
    return r.json()


def _create_secret(client, novel_id, character_id):
    r = client.post(
        f"/api/novels/{novel_id}/characters/{character_id}/secrets",
        json={
            "title": "真实身世",
            "content": "乃是灵族亡国公主，此秘密绝不可随意泄露。",
            "secrecy_level": "secret",
            "reveal_status": "unrevealed",
        },
    )
    assert r.status_code == 200
    return r.json()


def _preview(client, novel_id, **overrides):
    payload = {"novel_id": novel_id, "task_type": "writer"}
    payload.update(overrides)
    return client.post("/api/ai/context/preview", json=payload)


def test_context_basic_sections(client):
    novel = _create_novel(client)
    _create_world_entry(client, novel["id"])
    _create_character(client, novel["id"], "沈璃")
    r = _preview(client, novel["id"])
    assert r.status_code == 200
    body = r.json()
    keys = {s["key"] for s in body["sections"]}
    assert "core_settings" in keys
    assert "characters" in keys
    assert "character_states" in keys
    assert body["estimated_tokens"] > 0
    assert body["token_budget"] >= body["estimated_tokens"]
    assert all(s["estimated"] for s in body["sections"])
    assert "《上下文小说》" in body["context_text"]
    assert "沈璃" in body["context_text"]
    assert "青云山" in body["context_text"]


def test_context_novel_isolation(client):
    n1 = _create_novel(client, "小说甲")
    n2 = _create_novel(client, "小说乙")
    c2 = _create_character(client, n2["id"], "外人")

    assert _preview(client, "ghost-novel").status_code == 404
    # 跨小说人物 ID 一律 404
    r = _preview(client, n1["id"], character_ids=[c2["id"]])
    assert r.status_code == 404
    # 跨小说章节 ID 一律 404
    ch2 = client.post(f"/api/novels/{n2['id']}/chapters", json={"title": "乙章"}).json()
    r2 = _preview(client, n1["id"], chapter_id=ch2["id"])
    assert r2.status_code == 404


def test_context_budget_trimming(client):
    novel = _create_novel(client)
    for i in range(8):
        _create_character(client, novel["id"], f"人物{i}", background="很长的背景" * 20)
    _create_world_entry(client, novel["id"])

    r = _preview(client, novel["id"], token_budget=200)
    assert r.status_code == 200
    body = r.json()
    assert body["token_budget"] == 200
    # 超预算时必须有截断/省略说明
    assert body["omitted_sections"] or body["warnings"]
    assert body["estimated_tokens"] <= 200 + 50  # 必需分区强制截断，允许小误差


def test_context_secret_pov_filtering(client):
    novel = _create_novel(client)
    char = _create_character(client, novel["id"], "沈璃")
    _create_secret(client, novel["id"], char["id"])

    # 作者视角：秘密可见
    author = _preview(client, novel["id"], pov="author").json()
    assert any(s["key"] == "character_secrets" for s in author["sections"])
    assert "真实身世" in author["context_text"]

    # 叙事视角：秘密一律不注入
    narrative = _preview(client, novel["id"], pov="narrative").json()
    assert all(s["key"] != "character_secrets" for s in narrative["sections"])
    assert "亡国公主" not in narrative["context_text"]

    # 角色视角：知识系统尚未实现，必须明确告警且不注入秘密
    character = _preview(client, novel["id"], pov="character").json()
    assert all(s["key"] != "character_secrets" for s in character["sections"])
    assert any("知识状态" in w for w in character["warnings"])
    assert "亡国公主" not in character["context_text"]


def test_context_chapter_and_history(client):
    novel = _create_novel(client)
    chapter = client.post(
        f"/api/novels/{novel['id']}/chapters",
        json={"title": "夜袭", "summary": "敌营夜袭，主角受伤"},
    ).json()
    client.post(
        f"/api/novels/{novel['id']}/plot-events",
        json={
            "title": "夜袭敌营",
            "description": "林远率队夜袭敌营，取得密信。",
            "chapter_id": chapter["id"],
            "story_time": "第三年秋",
        },
    )
    r = _preview(client, novel["id"], chapter_id=chapter["id"], user_requirement="写夜袭后的清晨")
    assert r.status_code == 200
    body = r.json()
    keys = {s["key"]: s for s in body["sections"]}
    assert "current_task" in keys
    assert "夜袭" in keys["current_task"]["content"]
    assert "写夜袭后的清晨" in keys["current_task"]["content"]
    assert "plot_history" in keys
    assert "夜袭敌营" in keys["plot_history"]["content"]
    # 故事时间使用 story_time，不是系统创建时间
    assert "第三年秋" in keys["plot_history"]["content"]


def test_context_does_not_dump_full_chapter_content(client):
    novel = _create_novel(client)
    long_text = "正文内容" * 2000
    client.post(
        f"/api/novels/{novel['id']}/chapters",
        json={"title": "长章", "content": long_text, "status": "completed"},
    )
    body = _preview(client, novel["id"]).json()
    # 长正文不得整体进入上下文
    assert len(body["context_text"]) < len(long_text)
