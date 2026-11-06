"""P4.2 快速写作测试：无计划生成、分段、失败恢复、编辑保存与上下文模式。"""

import json

from app.database.db import get_connection

PLAN_MARKER = "__plan_should_not_be_needed__"


def _novel(client, title="快速写作小说", description="测试世界观"):
    return client.post(
        "/api/novels", json={"title": title, "description": description}
    ).json()


def _chapter(client, novel_id, number, title=None, content="原有正文内容。"):
    return client.post(
        f"/api/novels/{novel_id}/chapters",
        json={
            "title": title or f"第{number}章",
            "chapter_number": number,
            "content": content,
        },
    ).json()


def _session(client, novel_id, **overrides):
    payload = {"user_requirement": "继续上一章，描写主角与对手的冲突"}
    payload.update(overrides)
    response = client.post(
        f"/api/novels/{novel_id}/quick-writing-sessions", json=payload
    )
    assert response.status_code == 200, response.text
    return response.json()


def _generate(client, novel_id, session_id, fake_ai, text, **overrides):
    fake_ai.push_text(text)
    response = client.post(
        f"/api/novels/{novel_id}/quick-writing-sessions/{session_id}/generate",
        json=overrides,
    )
    return response


def _session_get(client, novel_id, session_id):
    response = client.get(
        f"/api/novels/{novel_id}/quick-writing-sessions/{session_id}"
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_quick_writing_without_plan_generates_directly(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"], title="雨夜冲突")

    response = _generate(client, novel["id"], session["id"], fake_ai, "雨声压住了心跳。")
    assert response.status_code == 200, response.text
    data = response.json()
    assert PLAN_MARKER not in json.dumps(data, ensure_ascii=False)
    assert data["session"]["content"] == "雨声压住了心跳。"
    assert data["session"]["segments"][0]["status"] == "completed"
    # 目标字数尚未达到，会话保持 drafting，但正文可直接阅读与保存
    assert data["session"]["status"] == "drafting"
    assert data["session"]["word_count"] > 0
    assert fake_ai.requests[-1].messages[0].role == "system"


def test_long_text_generates_in_segments(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(
        client, novel["id"], target_word_count=2000, segment_words=700
    )

    first = _generate(client, novel["id"], session["id"], fake_ai, "第一段正文。" + "雨" * 700)
    assert first.status_code == 200, first.text
    second = _generate(client, novel["id"], session["id"], fake_ai, "第二段正文。" + "风" * 700)
    assert second.status_code == 200, second.text
    assert len(second.json()["session"]["segments"]) == 2
    assert "第一段正文。" in second.json()["session"]["content"]
    assert "第二段正文。" in second.json()["session"]["content"]

    third = _generate(client, novel["id"], session["id"], fake_ai, "第三段正文，自然收束。")
    assert third.status_code == 200, third.text
    data = third.json()
    assert len(data["session"]["segments"]) == 3
    # 前两段已接近目标字数，第三段按剩余字数收束
    assert "最后一段" in fake_ai.requests[-1].messages[-1].content


def test_failed_segment_can_resume_without_losing_content(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    first = _generate(client, novel["id"], session["id"], fake_ai, "已完成的第一段。")
    assert first.status_code == 200, first.text

    fake_ai.push_error("网络连接失败")
    failed = client.post(
        f"/api/novels/{novel['id']}/quick-writing-sessions/{session['id']}/generate",
        json={},
    )
    assert failed.status_code == 502, failed.text
    assert "网络连接失败" in failed.json()["detail"]

    detail = _session_get(client, novel["id"], session["id"])
    assert detail["content"] == "已完成的第一段。"
    assert detail["error_code"] is not None
    assert detail["segments"][-1]["status"] == "failed"

    resumed = _generate(client, novel["id"], session["id"], fake_ai, "恢复后的第二段。")
    assert resumed.status_code == 200, resumed.text
    data = resumed.json()
    assert "已完成的第一段。" in data["session"]["content"]
    assert "恢复后的第二段。" in data["session"]["content"]
    # 重试复用失败段号，不额外产生空段
    assert len(data["session"]["segments"]) == 2
    assert data["session"]["segments"][-1]["status"] == "completed"


def test_rewrite_current_segment(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    _generate(client, novel["id"], session["id"], fake_ai, "原始段落。")

    rewritten = _generate(
        client, novel["id"], session["id"], fake_ai, "重写后的段落。", seq=1
    )
    assert rewritten.status_code == 200, rewritten.text
    content = rewritten.json()["session"]["content"]
    assert "重写后的段落。" in content
    assert "原始段落。" not in content


def test_edit_draft_then_confirm_persists(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"], title="待保存章节")
    _generate(client, novel["id"], session["id"], fake_ai, "模型生成正文。")

    edited = client.put(
        f"/api/novels/{novel['id']}/quick-writing-sessions/{session['id']}/content",
        json={"content": "人工修改后的正文，必须原样保存。"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["edited"] is True

    confirmed = client.post(
        f"/api/novels/{novel['id']}/quick-writing-sessions/{session['id']}/confirm",
        json={"mode": "new_chapter", "chapter_title": "人工章节"},
    )
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["chapter"]["title"] == "人工章节"
    assert body["reminders"]["auto_continuity"] is False
    assert body["reminders"]["auto_memory"] is False

    chapter = client.get(
        f"/api/novels/{novel['id']}/chapters/{body['chapter']['id']}"
    ).json()
    assert chapter["content"] == "人工修改后的正文，必须原样保存。"


def test_confirm_new_chapter_does_not_overwrite_others(client, fake_ai, ai_task_models):
    novel = _novel(client)
    existing = _chapter(client, novel["id"], 1, content="第一章原始内容。")
    session = _session(client, novel["id"])
    _generate(client, novel["id"], session["id"], fake_ai, "快速写作新章节。")

    confirmed = client.post(
        f"/api/novels/{novel['id']}/quick-writing-sessions/{session['id']}/confirm",
        json={"mode": "new_chapter", "chapter_title": "第二章"},
    )
    assert confirmed.status_code == 200, confirmed.text
    new_chapter = confirmed.json()["chapter"]
    assert new_chapter["chapter_number"] == 2
    assert new_chapter["id"] != existing["id"]

    original = client.get(
        f"/api/novels/{novel['id']}/chapters/{existing['id']}"
    ).json()
    assert original["content"] == "第一章原始内容。"


def test_confirm_replace_existing_only_touches_linked_chapter(client, fake_ai, ai_task_models):
    novel = _novel(client)
    first = _chapter(client, novel["id"], 1, content="第一章原始内容。")
    second = _chapter(client, novel["id"], 2, content="第二章原始内容。")
    session = _session(client, novel["id"], chapter_id=first["id"])
    _generate(client, novel["id"], session["id"], fake_ai, "覆盖后的第一章。")

    confirmed = client.post(
        f"/api/novels/{novel['id']}/quick-writing-sessions/{session['id']}/confirm",
        json={"mode": "replace_existing"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["chapter"]["id"] == first["id"]

    refreshed = client.get(
        f"/api/novels/{novel['id']}/chapters/{first['id']}"
    ).json()
    assert refreshed["content"] == "覆盖后的第一章。"
    untouched = client.get(
        f"/api/novels/{novel['id']}/chapters/{second['id']}"
    ).json()
    assert untouched["content"] == "第二章原始内容。"


def test_context_budget_and_modes(client, fake_ai, ai_task_models):
    novel = _novel(client, description="核心设定标记：寒鸦王朝已经覆灭。")
    _chapter(client, novel["id"], 1, content="第一章内容。" * 400)
    _chapter(client, novel["id"], 2, content="第二章内容。" * 400)

    auto_session = _session(client, novel["id"], context_mode="auto")
    auto = _generate(client, novel["id"], auto_session["id"], fake_ai, "自动模式正文。")
    assert auto.status_code == 200, auto.text
    data = auto.json()
    assert data["context_estimated_tokens"] <= data["context_token_budget"]
    # 自动模式使用最近章节结尾，而不是整部小说全文
    assert "第二章内容" in fake_ai.requests[-1].messages[-1].content

    recent_session = _session(client, novel["id"], context_mode="recent")
    recent = _generate(client, novel["id"], recent_session["id"], fake_ai, "最近章节正文。")
    assert recent.status_code == 200, recent.text
    user_content = fake_ai.requests[-1].messages[-1].content
    # recent 模式剔除核心设定，只保留最近章节正文
    assert "核心设定标记" not in user_content
    assert "第二章内容" in user_content

    custom_session = _session(
        client,
        novel["id"],
        context_mode="custom",
        context_options={"sections": ["current_task"], "include_recent_chapter": False},
    )
    custom = _generate(client, novel["id"], custom_session["id"], fake_ai, "自定义正文。")
    assert custom.status_code == 200, custom.text
    custom_content = fake_ai.requests[-1].messages[-1].content
    assert "核心设定标记" not in custom_content
    assert "第二章内容" not in custom_content


def test_preview_context_does_not_call_model(client, ai_task_models):
    novel = _novel(client)
    _chapter(client, novel["id"], 1, content="上一章正文。")
    session = _session(client, novel["id"], context_mode="recent")

    preview = client.post(
        f"/api/novels/{novel['id']}/quick-writing-sessions/{session['id']}/context-preview"
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["estimated_tokens"] <= body["token_budget"]
    assert any(section["key"] == "recent_chapter" for section in body["sections"])


def test_provider_failure_is_reported_not_disguised(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])

    fake_ai.push_error("content_policy")
    response = client.post(
        f"/api/novels/{novel['id']}/quick-writing-sessions/{session['id']}/generate",
        json={},
    )
    assert response.status_code == 502, response.text
    assert "content_policy" in response.json()["detail"]

    detail = _session_get(client, novel["id"], session["id"])
    assert detail["content"] == ""
    assert detail["segments"][0]["status"] == "failed"
    assert detail["segments"][0]["error_code"] == "content_policy"
    assert "模拟网络错误" in detail["segments"][0]["error_message"]


def test_disabled_continuity_and_memory_do_not_block_or_auto_create(
    client, fake_ai, ai_task_models
):
    novel = _novel(client)
    session = _session(
        client,
        novel["id"],
        auto_continuity=False,
        auto_memory=False,
        remind_memory=True,
    )
    generated = _generate(client, novel["id"], session["id"], fake_ai, "不被记忆审核阻塞的正文。")
    assert generated.status_code == 200, generated.text

    confirmed = client.post(
        f"/api/novels/{novel['id']}/quick-writing-sessions/{session['id']}/confirm",
        json={"mode": "new_chapter", "chapter_title": "无记忆章节"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["reminders"]["remind_memory"] is True

    with get_connection() as conn:
        batches = conn.execute(
            "SELECT COUNT(*) AS n FROM memory_update_batches WHERE novel_id = ?",
            (novel["id"],),
        ).fetchone()
        checks = conn.execute(
            "SELECT COUNT(*) AS n FROM continuity_checks WHERE novel_id = ?",
            (novel["id"],),
        ).fetchone()
    assert batches["n"] == 0
    assert checks["n"] == 0


def test_quick_writing_is_isolated_between_novels(client, fake_ai, ai_task_models):
    novel_a = _novel(client, "甲小说")
    novel_b = _novel(client, "乙小说")
    session_a = _session(client, novel_a["id"])

    hidden = client.get(
        f"/api/novels/{novel_b['id']}/quick-writing-sessions/{session_a['id']}"
    )
    assert hidden.status_code == 404

    confirmed = client.post(
        f"/api/novels/{novel_b['id']}/quick-writing-sessions/{session_a['id']}/confirm",
        json={},
    )
    assert confirmed.status_code == 404
