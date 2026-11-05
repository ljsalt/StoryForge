"""P3.5 剧情事件接口测试。"""


def _create_novel(client, title="剧情事件测试"):
    r = client.post("/api/novels", json={"title": title})
    assert r.status_code == 200, r.text
    return r.json()


def _create_char(client, novel_id, name, **extra):
    payload = {"name": name}
    payload.update(extra)
    r = client.post(f"/api/novels/{novel_id}/characters", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _create_chapter(client, novel_id, title="第一章"):
    r = client.post(f"/api/novels/{novel_id}/chapters", json={"title": title})
    assert r.status_code == 200, r.text
    return r.json()


def _create_location(client, novel_id, name="青云山"):
    cat = client.post(
        f"/api/novels/{novel_id}/world/categories", json={"name": "地点"}
    )
    assert cat.status_code == 200, cat.text
    r = client.post(
        f"/api/novels/{novel_id}/world/entries",
        json={"name": name, "category_id": cat.json()["id"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _events(client, novel_id):
    return f"/api/novels/{novel_id}/plot-events"


def _create_event(client, novel_id, **payload):
    if "title" not in payload:
        payload["title"] = "剧情事件"
    r = client.post(_events(client, novel_id), json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_and_get_event(client):
    novel = _create_novel(client)
    chapter = _create_chapter(client, novel["id"], "初入宗门")
    data = _create_event(
        client,
        novel["id"],
        title="林远发现身世",
        description="林远在藏经阁发现自己的身世线索",
        event_type="转折",
        story_time="修仙历 3021 年",
        chapter_id=chapter["id"],
        importance="critical",
        sequence=3,
    )
    assert data["novel_id"] == novel["id"]
    assert data["chapter_id"] == chapter["id"]
    assert data["chapter_title"] == "初入宗门"
    assert data["chapter_number"] == 1
    assert data["event_type"] == "转折"
    assert data["importance"] == "critical"
    assert data["story_time"] == "修仙历 3021 年"
    assert data["participants"] == []

    fetched = client.get(f"{_events(client, novel['id'])}/{data['id']}").json()
    assert fetched["description"] == "林远在藏经阁发现自己的身世线索"


def test_update_and_delete_event(client):
    novel = _create_novel(client)
    data = _create_event(client, novel["id"], title="旧事件", importance="low")
    r = client.put(
        f"{_events(client, novel['id'])}/{data['id']}",
        json={"title": "新事件", "importance": "high", "story_time": "第二年"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "新事件"
    assert body["importance"] == "high"
    assert body["story_time"] == "第二年"

    r = client.delete(f"{_events(client, novel['id'])}/{data['id']}")
    assert r.status_code == 200
    assert client.get(f"{_events(client, novel['id'])}/{data['id']}").status_code == 404


def test_event_without_chapter(client):
    novel = _create_novel(client)
    data = _create_event(client, novel["id"], title="未归属章节的事件")
    assert data["chapter_id"] is None
    assert data["chapter_title"] is None


def test_event_with_multiple_participants(client):
    novel = _create_novel(client)
    a = _create_char(client, novel["id"], "林远")
    b = _create_char(client, novel["id"], "顾长生")
    data = _create_event(
        client,
        novel["id"],
        title="拜师",
        participants=[
            {"character_id": a["id"], "participant_role": "主角", "description": "拜师者"},
            {"character_id": b["id"], "participant_role": "师父", "description": "收徒"},
        ],
    )
    assert len(data["participants"]) == 2
    names = {p["character_name"] for p in data["participants"]}
    assert names == {"林远", "顾长生"}
    roles = {p["participant_role"] for p in data["participants"]}
    assert roles == {"主角", "师父"}


def test_duplicate_participant_rejected(client):
    novel = _create_novel(client)
    a = _create_char(client, novel["id"], "林远")
    r = client.post(
        _events(client, novel["id"]),
        json={
            "title": "重复参与",
            "participants": [
                {"character_id": a["id"], "participant_role": "主角"},
                {"character_id": a["id"], "participant_role": "目击者"},
            ],
        },
    )
    assert r.status_code == 400
    assert "重复" in r.json()["detail"]


def test_cross_novel_character_rejected(client):
    novel_a = _create_novel(client, "小说 A")
    novel_b = _create_novel(client, "小说 B")
    outsider = _create_char(client, novel_b["id"], "外书人物")
    r = client.post(
        _events(client, novel_a["id"]),
        json={"title": "跨书关联", "participants": [{"character_id": outsider["id"]}]},
    )
    assert r.status_code == 404


def test_cross_novel_chapter_rejected(client):
    novel_a = _create_novel(client, "小说 A")
    novel_b = _create_novel(client, "小说 B")
    chapter_b = _create_chapter(client, novel_b["id"], "B 章节")
    r = client.post(
        _events(client, novel_a["id"]),
        json={"title": "跨书章节", "chapter_id": chapter_b["id"]},
    )
    assert r.status_code == 404

    # 跨小说篡改事件 ID 同样 404
    event_b = _create_event(client, novel_b["id"], title="B 事件")
    assert client.get(f"{_events(client, novel_a['id'])}/{event_b['id']}").status_code == 404


def test_event_location_entry_and_manual(client):
    novel = _create_novel(client)
    location = _create_location(client, novel["id"], "青云山")
    with_entry = _create_event(
        client, novel["id"], title="山中相遇", location_id=location["id"]
    )
    assert with_entry["location_id"] == location["id"]
    assert with_entry["location_name"] == "青云山"

    manual = _create_event(
        client, novel["id"], title="野外遭遇", location_name="无名山谷"
    )
    assert manual["location_id"] is None
    assert manual["location_name"] == "无名山谷"

    # 跨小说地点不允许关联
    other = _create_novel(client, "另一本")
    r = client.post(
        _events(client, other["id"]),
        json={"title": "跨书地点", "location_id": location["id"]},
    )
    assert r.status_code == 404


def test_filter_events_by_character_and_chapter(client):
    novel = _create_novel(client)
    a = _create_char(client, novel["id"], "林远")
    b = _create_char(client, novel["id"], "顾长生")
    chapter_one = _create_chapter(client, novel["id"], "第一章")
    chapter_two = _create_chapter(client, novel["id"], "第二章")

    one = _create_event(
        client,
        novel["id"],
        title="事件一",
        chapter_id=chapter_one["id"],
        participants=[{"character_id": a["id"], "participant_role": "主角"}],
    )
    _create_event(
        client,
        novel["id"],
        title="事件二",
        chapter_id=chapter_two["id"],
        participants=[{"character_id": b["id"]}],
    )

    by_character = client.get(
        _events(client, novel["id"]), params={"character_id": a["id"]}
    ).json()
    assert [item["id"] for item in by_character] == [one["id"]]

    by_chapter = client.get(
        f"/api/novels/{novel['id']}/chapters/{chapter_two['id']}/events"
    ).json()
    assert [item["title"] for item in by_chapter] == ["事件二"]

    by_type = client.get(
        _events(client, novel["id"]), params={"event_type": "转折"}
    ).json()
    assert by_type == []

    client.put(
        f"{_events(client, novel['id'])}/{one['id']}", json={"event_type": "转折"}
    )
    by_type = client.get(
        _events(client, novel["id"]), params={"event_type": "转折"}
    ).json()
    assert [item["id"] for item in by_type] == [one["id"]]


def test_timeline_ordering_and_untimed(client):
    novel = _create_novel(client)
    late = _create_event(client, novel["id"], title="晚期", story_time="2024-03-01", sequence=1)
    early = _create_event(client, novel["id"], title="早期", story_time="2024-01-01", sequence=9)
    same_a = _create_event(client, novel["id"], title="同期 A", story_time="2024-02-01", sequence=1)
    same_b = _create_event(client, novel["id"], title="同期 B", story_time="2024-02-01", sequence=2)
    untimed = _create_event(client, novel["id"], title="没有时间", sequence=1)

    timeline = client.get(f"{_events(client, novel['id'])}/timeline").json()
    assert [item["title"] for item in timeline["timed"]] == [
        "早期",
        "同期 A",
        "同期 B",
        "晚期",
    ]
    assert [item["id"] for item in timeline["untimed"]] == [untimed["id"]]
    assert early["story_time"] == "2024-01-01"

    # 创建时间不是故事时间：未填写 story_time 的事件不会被自动补成 created_at
    assert all(item["story_time"] for item in timeline["timed"])
    assert all(item["story_time"] is None for item in timeline["untimed"])
    _ = late, same_a, same_b


def test_character_plot_events_endpoint(client):
    novel = _create_novel(client)
    a = _create_char(client, novel["id"], "林远")
    event = _create_event(
        client,
        novel["id"],
        title="林远入门",
        story_time="2024-01-01",
        participants=[{"character_id": a["id"], "participant_role": "主角"}],
    )
    result = client.get(
        f"/api/novels/{novel['id']}/characters/{a['id']}/plot-events"
    ).json()
    assert len(result) == 1
    assert result[0]["id"] == event["id"]
    assert result[0]["participants"][0]["participant_role"] == "主角"

    other = _create_novel(client, "另一本")
    assert client.get(
        f"/api/novels/{other['id']}/characters/{a['id']}/plot-events"
    ).status_code == 404


def test_delete_character_keeps_event(client):
    novel = _create_novel(client)
    a = _create_char(client, novel["id"], "林远")
    b = _create_char(client, novel["id"], "顾长生")
    event = _create_event(
        client,
        novel["id"],
        title="共同事件",
        participants=[
            {"character_id": a["id"], "participant_role": "主角"},
            {"character_id": b["id"], "participant_role": "师父"},
        ],
    )

    r = client.delete(f"/api/novels/{novel['id']}/characters/{a['id']}")
    assert r.status_code == 200, r.text

    still = client.get(f"{_events(client, novel['id'])}/{event['id']}")
    assert still.status_code == 200
    participants = still.json()["participants"]
    assert len(participants) == 1
    assert participants[0]["character_id"] == b["id"]


def test_update_participants_replaces(client):
    novel = _create_novel(client)
    a = _create_char(client, novel["id"], "林远")
    b = _create_char(client, novel["id"], "顾长生")
    event = _create_event(
        client,
        novel["id"],
        title="替换参与",
        participants=[{"character_id": a["id"], "participant_role": "主角"}],
    )
    r = client.put(
        f"{_events(client, novel['id'])}/{event['id']}",
        json={
            "participants": [
                {"character_id": b["id"], "participant_role": "师父"},
            ]
        },
    )
    assert r.status_code == 200, r.text
    participants = r.json()["participants"]
    assert [p["character_id"] for p in participants] == [b["id"]]


def test_delete_novel_cleans_events(client):
    novel = _create_novel(client)
    a = _create_char(client, novel["id"], "林远")
    chapter = _create_chapter(client, novel["id"], "章节")
    _create_event(
        client,
        novel["id"],
        title="将被清理",
        chapter_id=chapter["id"],
        participants=[{"character_id": a["id"]}],
    )

    r = client.delete(f"/api/novels/{novel['id']}")
    assert r.status_code == 200
    assert client.get(_events(client, novel["id"])).status_code == 404


def test_delete_event_keeps_character_and_chapter(client):
    novel = _create_novel(client)
    a = _create_char(client, novel["id"], "林远")
    chapter = _create_chapter(client, novel["id"], "章节")
    event = _create_event(
        client,
        novel["id"],
        title="删除事件",
        chapter_id=chapter["id"],
        participants=[{"character_id": a["id"]}],
    )
    r = client.delete(f"{_events(client, novel['id'])}/{event['id']}")
    assert r.status_code == 200

    assert client.get(f"/api/novels/{novel['id']}/characters/{a['id']}").status_code == 200
    assert client.get(
        f"/api/novels/{novel['id']}/chapters/{chapter['id']}"
    ).status_code == 200
