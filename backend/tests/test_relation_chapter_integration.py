"""P3.5：人物关系变化历史与章节的关联测试。"""


def _create_novel(client, title="关系章节集成"):
    r = client.post("/api/novels", json={"title": title})
    assert r.status_code == 200, r.text
    return r.json()


def _create_char(client, novel_id, name):
    r = client.post(f"/api/novels/{novel_id}/characters", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()


def _create_chapter(client, novel_id, title="第一章"):
    r = client.post(f"/api/novels/{novel_id}/chapters", json={"title": title})
    assert r.status_code == 200, r.text
    return r.json()


def _relations(client, novel_id):
    return f"/api/novels/{novel_id}/character-relations"


def _setup(client):
    novel = _create_novel(client)
    a = _create_char(client, novel["id"], "林远")
    b = _create_char(client, novel["id"], "顾长生")
    chapter = _create_chapter(client, novel["id"], "藏经阁")
    return novel, a, b, chapter


def test_create_relation_with_chapter(client):
    novel, a, b, chapter = _setup(client)
    r = client.post(
        _relations(client, novel["id"]),
        json={
            "source_character_id": a["id"],
            "target_character_id": b["id"],
            "relation_type": "师徒",
            "chapter_id": chapter["id"],
        },
    )
    assert r.status_code == 200, r.text
    relation = r.json()

    events = client.get(
        f"{_relations(client, novel['id'])}/{relation['id']}/events"
    ).json()
    assert events[0]["chapter_id"] == chapter["id"]
    assert events[0]["chapter_title"] == "藏经阁"
    assert events[0]["chapter_number"] == 1

    # 原有 P3.4 查询不受影响
    assert client.get(_relations(client, novel["id"])) .json()[0]["id"] == relation["id"]


def test_legacy_relation_without_chapter_still_works(client):
    novel, a, b, _chapter = _setup(client)
    r = client.post(
        _relations(client, novel["id"]),
        json={
            "source_character_id": a["id"],
            "target_character_id": b["id"],
            "relation_type": "师徒",
        },
    )
    assert r.status_code == 200, r.text
    relation = r.json()
    events = client.get(
        f"{_relations(client, novel['id'])}/{relation['id']}/events"
    ).json()
    assert events[0]["chapter_id"] is None
    assert events[0]["chapter_title"] is None


def test_update_relation_with_chapter_records_event(client):
    novel, a, b, chapter = _setup(client)
    relation = client.post(
        _relations(client, novel["id"]),
        json={
            "source_character_id": a["id"],
            "target_character_id": b["id"],
            "relation_type": "师徒",
        },
    ).json()

    r = client.put(
        f"{_relations(client, novel['id'])}/{relation['id']}",
        json={"description": "信任下降", "chapter_id": chapter["id"]},
    )
    assert r.status_code == 200, r.text
    events = client.get(
        f"{_relations(client, novel['id'])}/{relation['id']}/events"
    ).json()
    assert len(events) == 2
    assert events[-1]["event_type"] == "updated"
    assert events[-1]["chapter_id"] == chapter["id"]

    # 跨小说章节不能关联到关系事件
    other = _create_novel(client, "另一本")
    other_chapter = _create_chapter(client, other["id"], "别的章节")
    r = client.put(
        f"{_relations(client, novel['id'])}/{relation['id']}",
        json={"chapter_id": other_chapter["id"]},
    )
    assert r.status_code == 404


def test_chapter_relation_events_endpoint(client):
    novel, a, b, chapter = _setup(client)
    relation = client.post(
        _relations(client, novel["id"]),
        json={
            "source_character_id": a["id"],
            "target_character_id": b["id"],
            "relation_type": "师徒",
            "chapter_id": chapter["id"],
        },
    ).json()
    r = client.get(
        f"/api/novels/{novel['id']}/chapters/{chapter['id']}/relation-events"
    )
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 1
    assert items[0]["source_name"] == "林远"
    assert items[0]["target_name"] == "顾长生"
    assert items[0]["relation_id"] == relation["id"]

    other = _create_novel(client, "另一本")
    assert client.get(
        f"/api/novels/{other['id']}/chapters/{chapter['id']}/relation-events"
    ).status_code == 404


def test_delete_chapter_keeps_relation_event(client):
    novel, a, b, chapter = _setup(client)
    relation = client.post(
        _relations(client, novel["id"]),
        json={
            "source_character_id": a["id"],
            "target_character_id": b["id"],
            "relation_type": "师徒",
            "chapter_id": chapter["id"],
        },
    ).json()

    r = client.delete(f"/api/novels/{novel['id']}/chapters/{chapter['id']}")
    assert r.status_code == 200

    events = client.get(
        f"{_relations(client, novel['id'])}/{relation['id']}/events"
    ).json()
    assert len(events) == 1
    assert events[0]["chapter_id"] is None
    assert events[0]["chapter_title"] is None
    # 关系本身与事件历史都保留
    assert client.get(
        f"{_relations(client, novel['id'])}/{relation['id']}"
    ).status_code == 200
