"""P4.1.2 结构化剧情计划与重大决定测试。

覆盖：计划生成、JSON Schema 严格校验、有限次修复、截断/失败处理、
计划版本、手工修改与决定同步、必需决定阻止写作、自定义选择、
跨小说隔离，以及校验函数的纯单元测试。
"""

import json

import pytest

from app.services.writing_plan_schema import (
    PlanValidationError,
    extract_json_object,
    validate_plan,
)

VALID_DECISION = {
    "decision_id": "d1",
    "title": "是否杀死守卫",
    "description": "守卫认出了主角",
    "context": "守卫看到了主角的脸",
    "options": ["杀死守卫", "放走守卫"],
    "recommended_option": "放走守卫",
    "consequences": "杀死会引来追查，放走会留下隐患",
    "is_required": True,
}


def _scene(index: int) -> dict:
    return {
        "name": f"场景{index}",
        "location": "敌营",
        "characters": ["主角", "守卫"],
        "purpose": "取得情报",
        "actions": "主角潜行绕过守卫",
        "conflict": "守卫突然换岗",
        "result": "主角拿到情报",
        "transition": "天亮前撤离",
    }


def _plan_obj(*, scenes: int = 2, decisions=None) -> dict:
    return {
        "chapter_goal": "主角潜入敌营取回情报",
        "opening": "雨夜，主角翻过城墙",
        "scenes": [_scene(i + 1) for i in range(scenes)],
        "character_actions": ["主角潜行", "守卫换岗"],
        "conflicts": ["主角与守卫的遭遇"],
        "plot_events": [{"title": "潜入敌营", "description": "主角进入敌营"}],
        "foreshadowing": ["墙上的旧地图"],
        "ending": "主角带着情报消失在夜色中",
        "estimated_word_count": 2500,
        "major_decisions": list(decisions or []),
    }


def _novel(client, title="计划测试小说"):
    return client.post("/api/novels", json={"title": title}).json()


def _session(client, novel_id, **overrides):
    r = client.post(f"/api/novels/{novel_id}/writing-sessions", json=overrides or {})
    assert r.status_code == 200
    return r.json()


def _generate_plan(client, novel_id, session_id, *, extra=""):
    return client.post(
        f"/api/novels/{novel_id}/writing-sessions/{session_id}/plan/generate",
        json={"extra_instruction": extra},
    )


def _approve(client, novel_id, session_id):
    return client.post(
        f"/api/novels/{novel_id}/writing-sessions/{session_id}/plan/approve",
        json={},
    )


# ----------------------------- 生成与校验 -----------------------------

def test_generate_plan_success_and_task_record(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    fake_ai.push_text(json.dumps(_plan_obj(), ensure_ascii=False))
    r = _generate_plan(client, novel["id"], session["id"])
    assert r.status_code == 200
    body = r.json()
    assert body["plan"]["version"] == 1
    assert body["plan"]["is_current"] is True
    assert len(body["plan"]["scenes"]) == 2
    assert body["decisions"] == []
    assert body["usage"]["completion_tokens"] == 20

    detail = client.get(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}"
    ).json()
    assert detail["status"] == "awaiting_plan_approval"
    assert detail["plan"]["id"] == body["plan"]["id"]

    # 生成过程必须留下一条 planner 任务记录
    tasks = client.get(
        f"/api/ai/tasks?novel_id={novel['id']}&task_type=planner"
    ).json()
    assert len(tasks) == 1
    assert tasks[0]["status"] == "completed"
    assert tasks[0]["input_tokens"] == 10
    assert tasks[0]["output_tokens"] == 20


def test_invalid_json_is_repaired_once(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    fake_ai.push_text("这不是 JSON，只是解释文字")
    fake_ai.push_text(json.dumps(_plan_obj(), ensure_ascii=False))
    r = _generate_plan(client, novel["id"], session["id"])
    assert r.status_code == 200
    # 第一次失败 + 一次修复请求
    assert len(
        client.get(f"/api/ai/tasks?novel_id={novel['id']}&task_type=planner").json()
    ) == 2
    assert r.json()["plan"]["version"] == 1


def test_invalid_json_twice_marks_session_failed(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    fake_ai.push_text("```json\n{\"chapter_goal\": 1}\n```")
    fake_ai.push_text("仍然不是合法计划")
    r = _generate_plan(client, novel["id"], session["id"])
    assert r.status_code == 502
    detail = client.get(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}"
    ).json()
    assert detail["status"] == "failed"
    assert detail["error_code"] == "invalid_plan_json"


def test_truncated_plan_is_rejected(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    fake_ai.push_text(
        json.dumps(_plan_obj(), ensure_ascii=False), finish_reason="length"
    )
    r = _generate_plan(client, novel["id"], session["id"])
    assert r.status_code == 502
    detail = client.get(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}"
    ).json()
    assert detail["status"] == "failed"
    assert detail["error_code"] == "truncated"


def test_plan_requires_json_mode_configuration(client, fake_ai):
    """未配置任务模型时明确报错，而不是伪造计划。"""
    novel = _novel(client)
    session = _session(client, novel["id"])
    r = _generate_plan(client, novel["id"], session["id"])
    assert r.status_code == 400
    assert "配置可用模型" in r.json()["detail"]


# ----------------------------- 版本与修改 -----------------------------

def test_regenerate_plan_creates_new_current_version(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    fake_ai.push_text(json.dumps(_plan_obj(), ensure_ascii=False))
    _generate_plan(client, novel["id"], session["id"])

    second = _plan_obj(decisions=[VALID_DECISION])
    fake_ai.push_text(json.dumps(second, ensure_ascii=False))
    _generate_plan(client, novel["id"], session["id"], extra="加入一个重大决定")

    versions = client.get(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/plan/versions"
    ).json()
    assert [v["version"] for v in versions] == [2, 1]
    assert [v["is_current"] for v in versions] == [True, False]
    detail = client.get(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}"
    ).json()
    assert len(detail["decisions"]) == 1


def test_update_plan_resyncs_decisions(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    fake_ai.push_text(
        json.dumps(_plan_obj(decisions=[VALID_DECISION]), ensure_ascii=False)
    )
    _generate_plan(client, novel["id"], session["id"])
    client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}"
        f"/decisions/d1/resolve",
        json={"selected_option": "放走守卫"},
    )

    edited = _plan_obj(decisions=[])
    edited["chapter_goal"] = "改为潜入失败"
    r = client.put(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/plan",
        json=edited,
    )
    assert r.status_code == 200
    assert r.json()["chapter_goal"] == "改为潜入失败"
    assert r.json()["decisions"] == []


def test_update_plan_rejects_invalid_structure(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    fake_ai.push_text(json.dumps(_plan_obj(), ensure_ascii=False))
    _generate_plan(client, novel["id"], session["id"])

    broken = _plan_obj()
    del broken["ending"]
    r = client.put(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/plan",
        json=broken,
    )
    assert r.status_code == 422

    no_scenes = _plan_obj(scenes=0)
    r2 = client.put(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}/plan",
        json=no_scenes,
    )
    assert r2.status_code == 422


# ----------------------------- 重大决定 -----------------------------

def test_required_decision_blocks_writing_until_resolved(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    fake_ai.push_text(
        json.dumps(_plan_obj(decisions=[VALID_DECISION]), ensure_ascii=False)
    )
    _generate_plan(client, novel["id"], session["id"])

    blocked = _approve(client, novel["id"], session["id"])
    assert blocked.status_code == 400
    assert "必需重大决定" in blocked.json()["detail"]

    bad_option = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}"
        f"/decisions/d1/resolve",
        json={"selected_option": "不在选项里的回答"},
    )
    assert bad_option.status_code == 400

    ok = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}"
        f"/decisions/d1/resolve",
        json={"selected_option": "放走守卫"},
    )
    assert ok.status_code == 200
    decision = ok.json()["decisions"][0]
    assert decision["resolved"] is True

    approved = _approve(client, novel["id"], session["id"])
    assert approved.status_code == 200
    assert approved.json()["session"]["status"] == "writing"
    assert len(approved.json()["draft"]["segments"]) == 2
    assert approved.json()["draft"]["progress"]["total_segments"] == 2


def test_custom_answer_resolves_decision(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    fake_ai.push_text(
        json.dumps(_plan_obj(decisions=[VALID_DECISION]), ensure_ascii=False)
    )
    _generate_plan(client, novel["id"], session["id"])
    r = client.post(
        f"/api/novels/{novel['id']}/writing-sessions/{session['id']}"
        f"/decisions/d1/resolve",
        json={"custom_answer": "让守卫失忆后离开"},
    )
    assert r.status_code == 200
    assert r.json()["decisions"][0]["resolved"] is True
    assert _approve(client, novel["id"], session["id"]).status_code == 200


def test_optional_decision_does_not_block_writing(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    decision = dict(VALID_DECISION, is_required=False)
    fake_ai.push_text(
        json.dumps(_plan_obj(decisions=[decision]), ensure_ascii=False)
    )
    _generate_plan(client, novel["id"], session["id"])
    assert _approve(client, novel["id"], session["id"]).status_code == 200


def test_approve_requires_awaiting_status(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    r = _approve(client, novel["id"], session["id"])
    assert r.status_code == 409  # 还没有计划，阶段不匹配


def test_plan_endpoints_are_novel_isolated(client, fake_ai, ai_task_models):
    novel_a = _novel(client, "小说A")
    novel_b = _novel(client, "小说B")
    session = _session(client, novel_a["id"])
    fake_ai.push_text(json.dumps(_plan_obj(), ensure_ascii=False))
    _generate_plan(client, novel_a["id"], session["id"])

    assert client.get(
        f"/api/novels/{novel_b['id']}/writing-sessions/{session['id']}/plan"
    ).status_code == 404
    assert client.post(
        f"/api/novels/{novel_b['id']}/writing-sessions/{session['id']}"
        "/plan/generate",
        json={},
    ).status_code == 404


def test_generate_plan_wrong_stage_rejected(client, fake_ai, ai_task_models):
    novel = _novel(client)
    session = _session(client, novel["id"])
    fake_ai.push_text(json.dumps(_plan_obj(), ensure_ascii=False))
    _generate_plan(client, novel["id"], session["id"])
    assert _approve(client, novel["id"], session["id"]).status_code == 200
    # 已进入写作阶段后不允许重新生成计划
    r = _generate_plan(client, novel["id"], session["id"])
    assert r.status_code == 409


# ----------------------------- 纯校验单元测试 -----------------------------

def test_extract_json_object_handles_fence_and_prose():
    text = "好的，这是计划：\n```json\n{\"a\": 1}\n```\n请查收"
    assert extract_json_object(text) == {"a": 1}


def test_validate_plan_normalizes_loose_values():
    data = _plan_obj()
    data["scenes"][0]["characters"] = "主角"
    data["plot_events"] = ["只有标题的事件"]
    normalized = validate_plan(data)
    assert normalized["scenes"][0]["characters"] == ["主角"]
    assert normalized["plot_events"][0]["title"] == "只有标题的事件"


def test_validate_plan_rejects_missing_scene_field():
    data = _plan_obj()
    del data["scenes"][1]["transition"]
    with pytest.raises(PlanValidationError) as exc:
        validate_plan(data)
    assert "transition" in str(exc.value)


def test_validate_plan_rejects_bad_recommended_option():
    data = _plan_obj(decisions=[dict(VALID_DECISION, recommended_option="第三条路")])
    with pytest.raises(PlanValidationError) as exc:
        validate_plan(data)
    assert "recommended_option" in str(exc.value)
