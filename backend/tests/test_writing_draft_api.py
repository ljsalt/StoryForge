"""P4.1.2 分段写作、草稿编辑与正式写入测试。

覆盖：分段顺序与拼接、重复生成防护、截断不落草稿、reasoning_only /
网络错误保留已完成段落、暂停与继续、取消、重启恢复、草稿编辑、
确认写入新章节、显式覆盖原章节、事务与数据清理。
"""

import json
from datetime import datetime, timedelta, timezone

from app.database.db import get_connection
from app.services import writing_service


def _scene(index: int) -> dict:
    return {
        "name": f"场景{index}",
        "location": "敌营",
        "characters": ["主角"],
        "purpose": "取得情报",
        "actions": "主角潜行",
        "conflict": "守卫换岗",
        "result": "拿到情报",
        "transition": "天亮前撤离",
    }


def _plan_obj(*, scenes: int = 2, decisions=None) -> dict:
    return {
        "chapter_goal": "主角潜入敌营取回情报",
        "opening": "雨夜，主角翻过城墙",
        "scenes": [_scene(i + 1) for i in range(scenes)],
        "character_actions": ["主角潜行"],
        "conflicts": ["与守卫的遭遇"],
        "plot_events": [{"title": "潜入敌营", "description": "主角进入敌营"}],
        "foreshadowing": ["墙上的旧地图"],
        "ending": "主角消失在夜色中",
        "estimated_word_count": 2500,
        "major_decisions": list(decisions or []),
    }


REQUIRED_DECISION = {
    "decision_id": "d1",
    "title": "是否杀死守卫",
    "description": "守卫认出了主角",
    "context": "守卫看到了主角的脸",
    "options": ["杀死守卫", "放走守卫"],
    "recommended_option": "放走守卫",
    "consequences": "杀死会引来追查",
    "is_required": True,
}


def _novel(client, title="草稿测试小说"):
    return client.post("/api/novels", json={"title": title}).json()


def _chapter(client, novel_id, title="原有章节", content="这是原有的正文。"):
    return client.post(
        f"/api/novels/{novel_id}/chapters",
        json={"title": title, "chapter_number": 1, "content": content},
    ).json()


def _advance_to_draft(client, fake_ai, *, scenes=2, decisions=None) -> dict:
    """创建会话 → 生成计划 → 处理决定 → 确认计划，返回上下文信息。"""
    novel = _novel(client)
    session = client.post(
        f"/api/novels/{novel['id']}/writing-sessions", json={}
    ).json()
    fake_ai.push_text(
        json.dumps(_plan_obj(scenes=scenes, decisions=decisions), ensure_ascii=False)
    )
    plan_r = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/plan/generate",
        json={},
    )
    assert plan_r.status_code == 200, plan_r.text
    for item in decisions or []:
        if item["is_required"]:
            client.post(
                f"/api/novels/{novel['id']}/writing-sessions/{session['id']}"
                f"/decisions/{item['decision_id']}/resolve",
                json={"selected_option": item["options"][0]},
            )
    approve_r = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/plan/approve",
        json={},
    )
    assert approve_r.status_code == 200, approve_r.text
    return {
        "novel": novel,
        "session_id": session["id"],
        "draft": approve_r.json()["draft"],
    }


def _generate(client, novel_id, session_id, **payload):
    return client.post(
        f"/api/novels/{novel_id}/writing-sessions/{session_id}"
        "/draft/segments/generate",
        json=payload,
    )


def _get_session(client, novel_id, session_id):
    return client.get(
        f"/api/novels/{novel_id}/writing-sessions/{session_id}"
    ).json()


# ----------------------------- 分段生成 -----------------------------

def test_segments_generate_in_order_and_join(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai)
    novel, sid = ctx["novel"], ctx["session_id"]
    fake_ai.push_text("雨夜里，主角翻过城墙。")
    first = _generate(client, novel["id"], sid)
    assert first.status_code == 200
    seg1 = first.json()["segment"]
    assert seg1["sequence"] == 1
    assert seg1["status"] == "completed"
    assert first.json()["draft"]["progress"]["completed_segments"] == 1

    fake_ai.push_text("守卫换岗，主角屏住呼吸。")
    second = _generate(client, novel["id"], sid)
    assert second.status_code == 200
    assert second.json()["segment"]["sequence"] == 2
    draft = second.json()["draft"]
    assert draft["status"] == "ready"
    assert "雨夜里，主角翻过城墙。" in draft["content"]
    assert "守卫换岗，主角屏住呼吸。" in draft["content"]
    assert draft["progress"]["completed_segments"] == 2
    assert draft["word_count"] > 0
    assert _get_session(client, novel["id"], sid)["status"] == "draft_ready"


def test_completed_segment_cannot_be_regenerated_via_generate(
    client, fake_ai, ai_task_models
):
    ctx = _advance_to_draft(client, fake_ai)
    novel, sid = ctx["novel"], ctx["session_id"]
    fake_ai.push_text("第一段正文。")
    assert _generate(client, novel["id"], sid).status_code == 200

    again = _generate(client, novel["id"], sid, sequence=1)
    assert again.status_code == 409
    assert "重新生成" in again.json()["detail"]


def test_generate_when_all_segments_completed_is_rejected(
    client, fake_ai, ai_task_models
):
    ctx = _advance_to_draft(client, fake_ai, scenes=1)
    novel, sid = ctx["novel"], ctx["session_id"]
    fake_ai.push_text("唯一段落。")
    assert _generate(client, novel["id"], sid).status_code == 200
    r = _generate(client, novel["id"], sid)
    assert r.status_code == 409


def test_truncated_segment_is_not_saved(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai, scenes=2)
    novel, sid = ctx["novel"], ctx["session_id"]
    fake_ai.push_text("第一段完整正文。")
    assert _generate(client, novel["id"], sid).status_code == 200

    fake_ai.push_text("被截断的第二段……", finish_reason="length")
    r = _generate(client, novel["id"], sid)
    assert r.status_code == 502
    assert "截断" in r.json()["detail"]

    draft = client.get(
        f"/api/novels/{novel['id']}/writing-sessions/{sid}/draft"
    ).json()
    second = draft["segments"][1]
    assert second["status"] == "failed"
    assert second["truncated"] is True
    assert second["content"] == ""
    # 已成功的第一段必须保留
    assert "第一段完整正文。" in draft["content"]
    assert "被截断的第二段" not in draft["content"]


def test_reasoning_only_segment_keeps_existing_draft(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai, scenes=2)
    novel, sid = ctx["novel"], ctx["session_id"]
    fake_ai.push_text("第一段完整正文。")
    _generate(client, novel["id"], sid)

    fake_ai.push_text("", reasoning="让我先思考一下怎么写……")
    r = _generate(client, novel["id"], sid)
    assert r.status_code == 502
    draft = client.get(
        f"/api/novels/{novel['id']}/writing-sessions/{sid}/draft"
    ).json()
    assert draft["segments"][1]["error_code"] == "reasoning_only"
    assert "第一段完整正文。" in draft["content"]
    assert _get_session(client, novel["id"], sid)["status"] == "writing"


def test_network_error_keeps_previous_segments(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai, scenes=2)
    novel, sid = ctx["novel"], ctx["session_id"]
    fake_ai.push_text("第一段完整正文。")
    _generate(client, novel["id"], sid)

    fake_ai.push_error("network_error")
    r = _generate(client, novel["id"], sid)
    assert r.status_code == 502
    draft = client.get(
        f"/api/novels/{novel['id']}/writing-sessions/{sid}/draft"
    ).json()
    assert draft["segments"][1]["error_code"] == "network_error"
    assert "第一段完整正文。" in draft["content"]


def test_duplicate_generation_guard_and_stale_takeover(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai)
    novel, sid = ctx["novel"], ctx["session_id"]
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        conn.execute(
            "UPDATE writing_draft_segments SET status = 'generating', updated_at = ?"
            " WHERE draft_id = ? AND sequence = 1",
            (now.isoformat(timespec="seconds"), ctx["draft"]["id"]),
        )
    r = _generate(client, novel["id"], sid)
    assert r.status_code == 409
    assert "正在生成中" in r.json()["detail"]

    stale = (now - timedelta(minutes=10)).isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            "UPDATE writing_draft_segments SET updated_at = ?"
            " WHERE draft_id = ? AND sequence = 1",
            (stale, ctx["draft"]["id"]),
        )
    fake_ai.push_text("接管后正常生成。")
    r2 = _generate(client, novel["id"], sid)
    assert r2.status_code == 200
    assert r2.json()["segment"]["status"] == "completed"


def test_pause_blocks_generation_and_resume_restores(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai)
    novel, sid = ctx["novel"], ctx["session_id"]
    paused = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{sid}/pause"
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused_for_user"

    blocked = _generate(client, novel["id"], sid)
    assert blocked.status_code == 409

    resumed = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{sid}/resume"
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "writing"
    fake_ai.push_text("恢复后继续写作。")
    assert _generate(client, novel["id"], sid).status_code == 200


def test_cancel_marks_generating_segment_failed(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai)
    novel, sid = ctx["novel"], ctx["session_id"]
    with get_connection() as conn:
        conn.execute(
            "UPDATE writing_draft_segments SET status = 'generating' WHERE draft_id = ?",
            (ctx["draft"]["id"],),
        )
    r = client.post(f"/api/novels/{novel['id']}/writing-sessions/{sid}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status, error_code FROM writing_draft_segments"
            " WHERE draft_id = ?",
            (ctx["draft"]["id"],),
        ).fetchall()
    assert all(row["status"] == "failed" for row in rows)
    assert all(row["error_code"] == "cancelled" for row in rows)


def test_restart_recovery_pauses_sessions_and_fails_segments(
    client, fake_ai, ai_task_models
):
    ctx = _advance_to_draft(client, fake_ai)
    novel, sid = ctx["novel"], ctx["session_id"]
    with get_connection() as conn:
        conn.execute(
            "UPDATE writing_sessions SET status = 'writing' WHERE id = ?", (sid,)
        )
        conn.execute(
            "UPDATE writing_draft_segments SET status = 'generating' WHERE draft_id = ?",
            (ctx["draft"]["id"],),
        )
    result = writing_service.recover_interrupted_sessions()
    assert result["sessions"] == 1
    assert result["segments"] == 2

    detail = _get_session(client, novel["id"], sid)
    assert detail["status"] == "paused_for_user"
    assert detail["error_code"] == "interrupted_by_restart"
    draft = client.get(f"/api/novels/{novel['id']}/writing-sessions/{sid}/draft").json()
    assert all(s["status"] == "failed" for s in draft["segments"])


# ----------------------------- 草稿编辑 -----------------------------

def test_edit_draft_updates_content_and_word_count(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai)
    novel, sid = ctx["novel"], ctx["session_id"]
    with get_connection() as conn:
        conn.execute(
            "UPDATE writing_draft_segments SET status = 'completed', content = '原始段落。'"
            " WHERE draft_id = ?",
            (ctx["draft"]["id"],),
        )
        conn.execute(
            "UPDATE writing_drafts SET content = '原始段落。', status = 'ready'"
            " WHERE id = ?",
            (ctx["draft"]["id"],),
        )
    r = client.put(
        f"/api/novels/{novel['id']}/writing-sessions/{sid}/draft",
        json={"title": "雨夜潜入", "content": "作者亲手修改后的正文内容。"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "雨夜潜入"
    assert body["edited"] is True
    assert body["word_count"] > 0
    assert body["content"] == "作者亲手修改后的正文内容。"


# ----------------------------- 确认写入章节 -----------------------------

def test_confirm_creates_new_chapter_without_touching_original(
    client, fake_ai, ai_task_models
):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"], content="这是原有的正文。")
    session = client.post(
        f"/api/novels/{novel['id']}/writing-sessions",
        json={"chapter_id": chapter["id"]},
    ).json()
    fake_ai.push_text(json.dumps(_plan_obj(scenes=1), ensure_ascii=False))
    client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/plan/generate",
        json={},
    )
    client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/plan/approve",
        json={},
    )
    fake_ai.push_text("新的章节正文。")
    assert _generate(client, novel["id"], session["id"]).status_code == 200

    r = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/draft/confirm",
        json={"mode": "new_chapter", "chapter_title": "雨夜潜入"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "new_chapter"
    assert body["chapter"]["id"] != chapter["id"]
    assert body["chapter"]["title"] == "雨夜潜入"
    assert body["chapter"]["status"] == "completed"

    chapters = client.get(f"/api/novels/{novel['id']}/chapters").json()
    assert len(chapters) == 2
    original = client.get(
        f"/api/novels/{novel['id']}/chapters/{chapter['id']}"
    ).json()
    assert original["content"] == "这是原有的正文。"
    new_chapter = client.get(
        f"/api/novels/{novel['id']}/chapters/{body['chapter']['id']}"
    ).json()
    assert new_chapter["content"] == "新的章节正文。"

    detail = _get_session(client, novel["id"], session["id"])
    assert detail["status"] == "completed"
    assert detail["draft"]["status"] == "confirmed"
    assert detail["draft"]["chapter_id"] == body["chapter"]["id"]


def test_confirm_replace_existing_requires_explicit_mode(
    client, fake_ai, ai_task_models
):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"], content="旧正文。")
    session = client.post(
        f"/api/novels/{novel['id']}/writing-sessions",
        json={"chapter_id": chapter["id"]},
    ).json()
    fake_ai.push_text(json.dumps(_plan_obj(scenes=1), ensure_ascii=False))
    client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/plan/generate",
        json={},
    )
    client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/plan/approve",
        json={},
    )
    fake_ai.push_text("覆盖后的正文。")
    _generate(client, novel["id"], session["id"])

    r = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/draft/confirm",
        json={"mode": "replace_existing"},
    )
    assert r.status_code == 200
    assert r.json()["mode"] == "replace_existing"
    assert r.json()["chapter"]["id"] == chapter["id"]
    updated = client.get(
        f"/api/novels/{novel['id']}/chapters/{chapter['id']}"
    ).json()
    assert updated["content"] == "覆盖后的正文。"
    assert updated["status"] == "completed"


def test_confirm_requires_all_segments_completed(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai, scenes=2)
    novel, sid = ctx["novel"], ctx["session_id"]
    fake_ai.push_text("只写了第一段。")
    _generate(client, novel["id"], sid)
    r = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{sid}/draft/confirm",
        json={"mode": "new_chapter"},
    )
    assert r.status_code == 409
    assert "未完成" in r.json()["detail"]


def test_confirm_requires_explicit_mode_for_replace(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai, scenes=1)
    novel, sid = ctx["novel"], ctx["session_id"]
    fake_ai.push_text("正文。")
    _generate(client, novel["id"], sid)
    # 会话没有关联章节 → 不允许覆盖
    r = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{sid}/draft/confirm",
        json={"mode": "replace_existing"},
    )
    assert r.status_code == 400


def test_draft_isolation_between_novels(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(client, fake_ai)
    novel, sid = ctx["novel"], ctx["session_id"]
    other = _novel(client, "另一部小说")
    assert client.get(
        f"/api/novels/{other['id']}/writing-sessions/{sid}/draft"
    ).status_code == 404


def test_delete_novel_cleans_all_writing_data(client, fake_ai, ai_task_models):
    ctx = _advance_to_draft(
        client, fake_ai, scenes=1, decisions=[REQUIRED_DECISION]
    )
    novel, sid = ctx["novel"], ctx["session_id"]
    fake_ai.push_text("正文。")
    _generate(client, novel["id"], sid)

    assert client.delete(f"/api/novels/{novel['id']}").status_code == 200
    with get_connection() as conn:
        for table in (
            "writing_sessions", "writing_plans", "writing_decisions",
            "writing_drafts", "writing_draft_segments",
        ):
            count = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE novel_id = ?",
                (novel["id"],),
            ).fetchone()["n"]
            assert count == 0, table
