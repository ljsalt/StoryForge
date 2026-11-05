"""P4.1.2 创作会话管理测试。

覆盖：会话创建（新章节 / 已有章节）、字段校验、列表与详情、
修改、暂停/继续/取消状态流转、跨小说隔离、删除会话与章节时的外键处理。
"""

from app.database.db import get_connection


def _novel(client, title="创作测试小说"):
    r = client.post("/api/novels", json={"title": title})
    assert r.status_code == 200
    return r.json()


def _chapter(client, novel_id, title="第一章", content="原有正文"):
    r = client.post(
        f"/api/novels/{novel_id}/chapters",
        json={"title": title, "chapter_number": 1, "content": content},
    )
    assert r.status_code == 200
    return r.json()


def _create_session(client, novel_id, **overrides):
    payload = {"title": "", "user_instruction": "写一场紧张的追逐戏",
               "target_word_count": 2500}
    payload.update(overrides)
    return client.post(f"/api/novels/{novel_id}/writing-sessions", json=payload)


def test_create_session_for_new_chapter(client):
    novel = _novel(client)
    r = _create_session(client, novel["id"])
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "planning"
    assert body["chapter_id"] is None
    assert body["title"] == "第 1 章"
    assert body["target_word_count"] == 2500
    assert body["plan"] is None
    assert body["draft"] is None
    assert body["decisions"] == []


def test_create_session_from_existing_chapter(client):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"], title="雨夜")
    r = _create_session(client, novel["id"], chapter_id=chapter["id"])
    assert r.status_code == 200
    body = r.json()
    assert body["chapter_id"] == chapter["id"]
    # 未显式指定标题时继承章节标题
    assert body["title"] == "雨夜"


def test_create_session_rejects_foreign_chapter_and_pov(client):
    novel_a = _novel(client, "小说A")
    novel_b = _novel(client, "小说B")
    chapter_b = _chapter(client, novel_b["id"])
    r = _create_session(client, novel_a["id"], chapter_id=chapter_b["id"])
    assert r.status_code == 404

    pov = client.post(
        f"/api/novels/{novel_b['id']}/characters",
        json={"name": "角色B"},
    ).json()
    r2 = _create_session(client, novel_a["id"], pov_character_id=pov["id"])
    assert r2.status_code == 404


def test_create_session_validates_target_word_count(client):
    novel = _novel(client)
    r = client.post(
        f"/api/novels/{novel['id']}/writing-sessions",
        json={"target_word_count": 100},
    )
    assert r.status_code == 422


def test_list_get_update_and_delete_session(client):
    novel = _novel(client)
    created = _create_session(client, novel["id"]).json()
    listing = client.get(f"/api/novels/{novel['id']}/writing-sessions").json()
    assert len(listing) == 1
    assert listing[0]["id"] == created["id"]

    r = client.patch(
        f"/api/novels/{novel['id']}/writing-sessions/{created['id']}",
        json={"title": "夜袭", "target_word_count": 3200,
              "user_instruction": "保持冷峻的叙述语气"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "夜袭"
    assert body["target_word_count"] == 3200
    assert body["user_instruction"] == "保持冷峻的叙述语气"

    r2 = client.delete(f"/api/novels/{novel['id']}/writing-sessions/{created['id']}")
    assert r2.status_code == 200
    assert r2.json()["deleted"] is True
    assert client.get(
        f"/api/novels/{novel['id']}/writing-sessions/{created['id']}"
    ).status_code == 404


def test_session_isolation_between_novels(client):
    novel_a = _novel(client, "小说A")
    novel_b = _novel(client, "小说B")
    session = _create_session(client, novel_a["id"]).json()

    assert client.get(
        f"/api/novels/{novel_b['id']}/writing-sessions/{session['id']}"
    ).status_code == 404
    assert client.get(f"/api/novels/{novel_b['id']}/writing-sessions").json() == []
    assert client.delete(
        f"/api/novels/{novel_b['id']}/writing-sessions/{session['id']}"
    ).status_code == 404


def test_cancel_is_terminal_and_blocks_further_changes(client):
    novel = _novel(client)
    session = _create_session(client, novel["id"]).json()
    r = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/cancel"
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    assert client.patch(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}",
        json={"title": "改名"},
    ).status_code == 409
    assert client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/cancel"
    ).status_code == 409


def test_pause_requires_writing_status(client):
    novel = _novel(client)
    session = _create_session(client, novel["id"]).json()
    r = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/pause"
    )
    assert r.status_code == 409


def test_deleting_chapter_keeps_session_with_null_chapter(client):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"])
    session = _create_session(client, novel["id"], chapter_id=chapter["id"]).json()
    r = client.delete(f"/api/novels/{novel['id']}/chapters/{chapter['id']}")
    assert r.status_code == 200
    body = client.get(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}"
    ).json()
    assert body["chapter_id"] is None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT chapter_id FROM writing_sessions WHERE id = ?", (session["id"],)
        ).fetchone()
    assert row["chapter_id"] is None
