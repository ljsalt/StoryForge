"""P3.5 章节接口测试。"""

LONG_TEXT = "第一段正文。\n" + ("这是一段用来验证长篇正文保存的中文内容。" * 500)


def _create_novel(client, title="章节测试"):
    r = client.post("/api/novels", json={"title": title})
    assert r.status_code == 200, r.text
    return r.json()


def _chapters(client, novel_id):
    return f"/api/novels/{novel_id}/chapters"


def _create_chapter(client, novel_id, **payload):
    if "title" not in payload:
        payload["title"] = "第一章"
    r = client.post(_chapters(client, novel_id), json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_chapter(client):
    novel = _create_novel(client)
    data = _create_chapter(
        client,
        novel["id"],
        title="初入宗门",
        content="林远踏入山门。",
        summary="主角入门",
        status="drafting",
    )
    assert data["novel_id"] == novel["id"]
    assert data["chapter_number"] == 1
    assert data["title"] == "初入宗门"
    assert data["status"] == "drafting"
    # 字数由后端按非空白字符计算
    assert data["word_count"] == 7
    assert data["volume_number"] is None


def test_create_chapter_title_only(client):
    novel = _create_novel(client)
    data = _create_chapter(client, novel["id"], title="只有标题")
    assert data["content"] == ""
    assert data["summary"] == ""
    assert data["word_count"] == 0
    assert data["status"] == "planned"
    # 只填标题也能创建，章节号自动递增
    second = _create_chapter(client, novel["id"], title="第二章")
    assert second["chapter_number"] == 2


def test_update_chapter_and_word_count(client):
    novel = _create_novel(client)
    data = _create_chapter(client, novel["id"], title="旧标题", content="旧的")
    cid = data["id"]
    r = client.put(
        f"{_chapters(client, novel['id'])}/{cid}",
        json={"title": "新标题", "summary": "新摘要", "status": "completed"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "新标题"
    assert body["summary"] == "新摘要"
    assert body["status"] == "completed"

    r = client.put(
        f"{_chapters(client, novel['id'])}/{cid}",
        json={"content": "更新后的正文内容。"},
    )
    assert r.status_code == 200
    assert r.json()["word_count"] == 9
    assert r.json()["content"] == "更新后的正文内容。"


def test_word_count_ignores_client_value(client):
    novel = _create_novel(client)
    data = _create_chapter(
        client, novel["id"], title="伪造字数", content="两个字", word_count=999
    )
    assert data["word_count"] == 3

    cid = data["id"]
    r = client.put(
        f"{_chapters(client, novel['id'])}/{cid}",
        json={"content": "正文", "word_count": 10000},
    )
    assert r.status_code == 200
    assert r.json()["word_count"] == 2


def test_reorder_chapters(client):
    novel = _create_novel(client)
    first = _create_chapter(client, novel["id"], title="一")
    second = _create_chapter(client, novel["id"], title="二")
    third = _create_chapter(client, novel["id"], title="三")

    r = client.patch(
        f"{_chapters(client, novel['id'])}/reorder",
        json={"ordered_ids": [third["id"], first["id"], second["id"]]},
    )
    assert r.status_code == 200, r.text
    ordered = r.json()
    assert [item["id"] for item in ordered] == [third["id"], first["id"], second["id"]]
    assert [item["chapter_number"] for item in ordered] == [1, 2, 3]

    # 排序不依赖数据库自然顺序，列表读取必须与重排结果一致
    listing = client.get(_chapters(client, novel["id"])).json()
    assert [item["id"] for item in listing] == [third["id"], first["id"], second["id"]]

    # 排序列表必须覆盖全部章节
    r = client.patch(
        f"{_chapters(client, novel['id'])}/reorder",
        json={"ordered_ids": [first["id"]]},
    )
    assert r.status_code == 400


def test_delete_chapter(client):
    novel = _create_novel(client)
    data = _create_chapter(client, novel["id"], title="待删除")
    r = client.delete(f"{_chapters(client, novel['id'])}/{data['id']}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert client.get(f"{_chapters(client, novel['id'])}/{data['id']}").status_code == 404


def test_delete_chapter_keeps_plot_events(client):
    novel = _create_novel(client)
    chapter = _create_chapter(client, novel["id"], title="有事件的章节")
    r = client.post(
        f"/api/novels/{novel['id']}/plot-events",
        json={"title": "林远拜师", "chapter_id": chapter["id"]},
    )
    assert r.status_code == 200, r.text
    event_id = r.json()["id"]

    r = client.delete(f"{_chapters(client, novel['id'])}/{chapter['id']}")
    assert r.status_code == 200

    event = client.get(f"/api/novels/{novel['id']}/plot-events/{event_id}")
    assert event.status_code == 200, event.text
    assert event.json()["chapter_id"] is None
    assert event.json()["title"] == "林远拜师"


def test_cross_novel_chapter_returns_404(client):
    novel_a = _create_novel(client, "小说 A")
    novel_b = _create_novel(client, "小说 B")
    chapter_b = _create_chapter(client, novel_b["id"], title="B 的章节")

    assert client.get(f"/api/novels/{novel_a['id']}/chapters/{chapter_b['id']}").status_code == 404
    r = client.put(
        f"/api/novels/{novel_a['id']}/chapters/{chapter_b['id']}", json={"title": "篡改"}
    )
    assert r.status_code == 404
    r = client.delete(f"/api/novels/{novel_a['id']}/chapters/{chapter_b['id']}")
    assert r.status_code == 404


def test_long_content_roundtrip(client):
    novel = _create_novel(client)
    data = _create_chapter(client, novel["id"], title="长篇", content=LONG_TEXT)
    assert data["word_count"] == len("".join(LONG_TEXT.split()))

    fetched = client.get(f"{_chapters(client, novel['id'])}/{data['id']}").json()
    assert fetched["content"] == LONG_TEXT.strip()

    r = client.put(
        f"{_chapters(client, novel['id'])}/{data['id']}",
        json={"content": LONG_TEXT + "新增结尾。"},
    )
    assert r.status_code == 200
    again = client.get(f"{_chapters(client, novel['id'])}/{data['id']}").json()
    assert again["content"].endswith("新增结尾。")
    assert again["word_count"] > data["word_count"]


def test_filter_chapters_by_status_and_search(client):
    novel = _create_novel(client)
    _create_chapter(client, novel["id"], title="已完成章节", status="completed")
    _create_chapter(client, novel["id"], title="写作中章节", status="drafting")
    _create_chapter(client, novel["id"], title="计划章节", status="planned")

    completed = client.get(
        _chapters(client, novel["id"]), params={"status": "completed"}
    ).json()
    assert [item["title"] for item in completed] == ["已完成章节"]

    searched = client.get(_chapters(client, novel["id"]), params={"search": "计划"}).json()
    assert [item["title"] for item in searched] == ["计划章节"]

    assert client.get(
        _chapters(client, novel["id"]), params={"status": "invalid"}
    ).status_code == 400


def test_chapter_stats(client):
    novel = _create_novel(client)
    _create_chapter(client, novel["id"], title="一", content="三个字", status="completed")
    _create_chapter(client, novel["id"], title="二", content="五个字符", status="drafting")

    stats = client.get(f"{_chapters(client, novel['id'])}/stats").json()
    assert stats["chapter_count"] == 2
    assert stats["completed_chapter_count"] == 1
    assert stats["drafting_chapter_count"] == 1
    assert stats["planned_chapter_count"] == 0
    assert stats["total_word_count"] == 7

    detail = client.get(f"/api/novels/{novel['id']}").json()
    assert detail["stats"]["chapter_count"] == 2
    assert detail["stats"]["completed_chapter_count"] == 1
    assert detail["stats"]["word_count"] == 7
    assert detail["current_word_count"] == 7


def test_delete_novel_cleans_chapters(client):
    novel = _create_novel(client)
    _create_chapter(client, novel["id"], title="章节")

    r = client.delete(f"/api/novels/{novel['id']}")
    assert r.status_code == 200
    assert client.get(_chapters(client, novel["id"])).status_code == 404
