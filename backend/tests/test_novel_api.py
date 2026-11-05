"""P3.1 小说项目管理接口测试。"""


def _create(client, **overrides):
    payload = {
        "title": "长夜行",
        "subtitle": "第一卷",
        "description": "一个关于长夜的故事。",
        "genre": "玄幻",
        "tags": ["东方", "群像"],
        "status": "planning",
        "target_word_count": 100000,
    }
    payload.update(overrides)
    return client.post("/api/novels", json=payload)


def test_create_novel_success(client):
    response = _create(client, title="  长夜行  ", tags=["  东方 ", "群像", "东方"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "长夜行"
    assert body["tags"] == ["东方", "群像"]
    assert body["status"] == "planning"
    assert body["target_word_count"] == 100000
    assert body["current_word_count"] == 0
    assert body["is_default"] is False
    assert body["stats"]["chapter_count"] == 0


def test_create_novel_empty_title_fails(client):
    response = _create(client, title="   ")
    assert response.status_code == 422
    assert "小说名称不能为空" in response.text


def test_invalid_status_and_target_word_count(client):
    assert _create(client, status="unknown").status_code == 422
    assert _create(client, target_word_count=0).status_code == 422
    assert _create(client, target_word_count=-5).status_code == 422


def test_list_novels(client):
    _create(client, title="第一本")
    _create(client, title="第二本")
    response = client.get("/api/novels")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_search_by_title(client):
    _create(client, title="星海拾遗")
    _create(client, title="长夜行")
    result = client.get("/api/novels", params={"search": "星海"}).json()
    assert len(result) == 1
    assert result[0]["title"] == "星海拾遗"


def test_filter_by_status(client):
    _create(client, title="构思中的书", status="planning")
    _create(client, title="创作中的书", status="writing")
    result = client.get("/api/novels", params={"status": "writing"}).json()
    assert [item["title"] for item in result] == ["创作中的书"]
    assert client.get("/api/novels", params={"status": "bad"}).status_code == 400


def test_novel_detail(client):
    novel = _create(client).json()
    detail = client.get(f"/api/novels/{novel['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == novel["id"]
    assert body["stats"] == {
        "chapter_count": 0,
        "character_count": 0,
        "character_relation_count": 0,
        "word_count": 0,
        "world_entry_count": 0,
    }

    missing = client.get("/api/novels/not-exist")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "小说不存在"


def test_update_novel(client):
    novel = _create(client).json()
    updated = client.put(
        f"/api/novels/{novel['id']}",
        json={
            "title": "长夜行·改",
            "status": "writing",
            "target_word_count": 300000,
            "tags": ["玄幻"],
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["title"] == "长夜行·改"
    assert body["status"] == "writing"
    assert body["target_word_count"] == 300000
    assert body["tags"] == ["玄幻"]
    assert body["updated_at"] >= novel["updated_at"]


def test_delete_novel(client):
    novel = _create(client).json()
    assert client.delete(f"/api/novels/{novel['id']}").json()["deleted"] is True
    assert client.get("/api/novels").json() == []
    assert client.delete(f"/api/novels/{novel['id']}").status_code == 404


def test_set_default_novel(client):
    first = _create(client, title="第一本").json()
    second = _create(client, title="第二本").json()

    response = client.put(f"/api/novels/{first['id']}/default")
    assert response.status_code == 200
    assert response.json()["is_default"] is True

    default = client.get("/api/novels/default").json()
    assert default["id"] == first["id"]

    client.put(f"/api/novels/{second['id']}/default")
    listed = client.get("/api/novels").json()
    flagged = [item for item in listed if item["is_default"]]
    assert len(flagged) == 1
    assert flagged[0]["id"] == second["id"]


def test_set_default_unknown_novel_fails(client):
    response = client.put("/api/novels/not-exist/default")
    assert response.status_code == 404
    assert response.json()["detail"] == "小说不存在"


def test_delete_default_novel_clears_setting(client):
    novel = _create(client).json()
    client.put(f"/api/novels/{novel['id']}/default")
    result = client.delete(f"/api/novels/{novel['id']}")
    assert result.status_code == 200
    assert result.json()["default_cleared"] is True
    assert client.get("/api/novels/default").json() is None
    assert client.get("/api/novels").json() == []


def test_default_returns_null_when_empty(client):
    response = client.get("/api/novels/default")
    assert response.status_code == 200
    assert response.json() is None
