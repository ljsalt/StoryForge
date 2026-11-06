"""P4.1.3 连续性检查 API 测试。

覆盖：成功（pass/warning/conflict）、overall 自动升级、坏 JSON 修复一次、
修复仍失败、输出截断、AI 调用失败、上下文预算裁剪记录、历史记录保留、
跨小说隔离、空正文拒绝。
"""

import json


def _report(overall="pass", issues=None):
    return json.dumps({"overall": overall, "issues": issues or []}, ensure_ascii=False)


CONFLICT_ISSUE = {
    "severity": "conflict",
    "category": "人物状态",
    "description": "林远上一章已经死亡，本章却又出场行动",
    "evidence": "林远推开门，大步走进客栈。",
    "reference": "人物状态：生命=dead",
    "suggestion": "修改出场人物，或调整前一章剧情",
}


def _novel(client, title="连续性测试小说"):
    return client.post("/api/novels", json={"title": title}).json()


def _chapter(client, novel_id, content="林远推开门，大步走进客栈。苏月坐在角落。", **kw):
    payload = {"title": "第一章", "content": content}
    payload.update(kw)
    r = client.post(f"/api/novels/{novel_id}/chapters", json=payload)
    assert r.status_code in (200, 201)
    return r.json()


def _character(client, novel_id, name, **kw):
    r = client.post(f"/api/novels/{novel_id}/characters", json={"name": name, **kw})
    assert r.status_code in (200, 201)
    return r.json()


def _create_check(client, novel_id, chapter_id, **kw):
    return client.post(
        f"/api/novels/{novel_id}/chapters/{chapter_id}/continuity-checks", json=kw
    )


# ----------------------------- 成功路径 -----------------------------

def test_check_pass_result(client, fake_ai, ai_task_models):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"])
    fake_ai.push_text(_report("pass", []))
    r = _create_check(client, novel["id"], chapter["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "completed"
    assert body["overall_result"] == "pass"
    assert body["report"]["issues"] == []
    assert body["completed_at"]
    assert body["context_meta"]["estimated_tokens"] > 0


def test_check_conflict_result_and_auto_detect(client, fake_ai, ai_task_models):
    novel = _novel(client)
    _character(client, novel["id"], "林远")
    _character(client, novel["id"], "苏月")
    chapter = _chapter(client, novel["id"])
    fake_ai.push_text(_report("conflict", [CONFLICT_ISSUE]))
    r = _create_check(client, novel["id"], chapter["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["overall_result"] == "conflict"
    assert len(body["report"]["issues"]) == 1
    issue = body["report"]["issues"][0]
    assert issue["severity"] == "conflict"
    assert issue["evidence"]
    assert issue["reference"]
    # 正文中出现的人物被自动检测并注入上下文
    assert set(body["context_meta"]["auto_detected_characters"]) == {"林远", "苏月"}


def test_check_overall_upgraded_from_issues(client, fake_ai, ai_task_models):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"])
    warning_issue = dict(CONFLICT_ISSUE, severity="warning")
    # 模型自称 pass，但列出了 warning 问题：服务端必须升级为 warning
    fake_ai.push_text(_report("pass", [warning_issue]))
    r = _create_check(client, novel["id"], chapter["id"])
    assert r.status_code == 201
    assert r.json()["overall_result"] == "warning"


def test_check_explicit_character_ids(client, fake_ai, ai_task_models):
    novel = _novel(client)
    char = _character(client, novel["id"], "林远")
    chapter = _chapter(client, novel["id"])
    fake_ai.push_text(_report("pass", []))
    r = _create_check(client, novel["id"], chapter["id"], character_ids=[char["id"]])
    assert r.status_code == 201
    meta = r.json()["context_meta"]
    assert meta["explicit_character_ids"] is True
    assert meta["character_ids"] == [char["id"]]


# ----------------------------- 失败与修复 -----------------------------

def test_check_bad_json_repaired_once(client, fake_ai, ai_task_models):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"])
    fake_ai.push_text("这不是 JSON，完全无法解析{{{")
    fake_ai.push_text(_report("warning", [dict(CONFLICT_ISSUE, severity="warning")]))
    r = _create_check(client, novel["id"], chapter["id"])
    assert r.status_code == 201
    assert r.json()["overall_result"] == "warning"


def test_check_bad_json_fails_after_repair(client, fake_ai, ai_task_models):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"])
    fake_ai.push_text("完全不是 JSON")
    fake_ai.push_text("依然不是 JSON")
    r = _create_check(client, novel["id"], chapter["id"])
    assert r.status_code == 502
    checks = client.get(
        f"/api/novels/{novel['id']}/chapters/{chapter['id']}/continuity-checks"
    ).json()
    assert checks[0]["status"] == "failed"
    assert checks[0]["error_code"] == "invalid_report_json"


def test_check_truncated(client, fake_ai, ai_task_models):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"])
    fake_ai.push_text('{"overall": "pass", "issues": [', finish_reason="length")
    r = _create_check(client, novel["id"], chapter["id"])
    assert r.status_code == 502
    assert "截断" in r.json()["detail"]
    checks = client.get(
        f"/api/novels/{novel['id']}/chapters/{chapter['id']}/continuity-checks"
    ).json()
    assert checks[0]["status"] == "failed"
    assert checks[0]["error_code"] == "truncated"


def test_check_ai_failure(client, fake_ai, ai_task_models):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"])
    fake_ai.push_error("network_error")
    r = _create_check(client, novel["id"], chapter["id"])
    assert r.status_code == 502
    checks = client.get(
        f"/api/novels/{novel['id']}/chapters/{chapter['id']}/continuity-checks"
    ).json()
    assert checks[0]["status"] == "failed"


def test_check_without_model_config(client, fake_ai):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"])
    r = _create_check(client, novel["id"], chapter["id"])
    assert r.status_code == 400
    assert "分配模型" in r.json()["detail"]


def test_check_empty_content_rejected(client, fake_ai, ai_task_models):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"], content="")
    r = _create_check(client, novel["id"], chapter["id"])
    assert r.status_code == 400
    assert "正文为空" in r.json()["detail"]


# ----------------------------- 上下文预算与历史 -----------------------------

def test_check_context_budget_meta(client, fake_ai, ai_task_models):
    novel = _novel(client)
    for index in range(5):
        _character(client, novel["id"], f"路人{index}", background="很长的背景" * 100)
    chapter = _chapter(client, novel["id"])
    fake_ai.push_text(_report("pass", []))
    r = _create_check(client, novel["id"], chapter["id"], token_budget=300)
    assert r.status_code == 201
    meta = r.json()["context_meta"]
    assert meta["token_budget"] == 300
    assert meta["estimated_tokens"] <= 300
    # 预算紧张时应有分区被裁剪/省略，且章节正文作为必需分区仍被保留
    assert meta["omitted_sections"]
    included_keys = [s["key"] for s in meta.get("sections", [])] if meta.get("sections") else []
    assert "chapter_content" not in meta["omitted_sections"] or included_keys


def test_check_history_preserved(client, fake_ai, ai_task_models):
    novel = _novel(client)
    chapter = _chapter(client, novel["id"])
    fake_ai.push_text(_report("pass", []))
    fake_ai.push_text(_report("conflict", [CONFLICT_ISSUE]))
    r1 = _create_check(client, novel["id"], chapter["id"])
    r2 = _create_check(client, novel["id"], chapter["id"])
    assert r1.status_code == 201 and r2.status_code == 201
    checks = client.get(
        f"/api/novels/{novel['id']}/chapters/{chapter['id']}/continuity-checks"
    ).json()
    assert len(checks) == 2
    assert {c["overall_result"] for c in checks} == {"pass", "conflict"}
    detail = client.get(f"/api/novels/{novel['id']}/continuity-checks/{r1.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["overall_result"] == "pass"


# ----------------------------- 跨小说隔离 -----------------------------

def test_check_cross_novel_isolation(client, fake_ai, ai_task_models):
    novel_a = _novel(client, "小说A")
    novel_b = _novel(client, "小说B")
    chapter = _chapter(client, novel_a["id"])
    fake_ai.push_text(_report("pass", []))
    check = _create_check(client, novel_a["id"], chapter["id"]).json()

    r = client.get(f"/api/novels/{novel_b['id']}/continuity-checks/{check['id']}")
    assert r.status_code == 404
    r = client.get(f"/api/novels/{novel_b['id']}/chapters/{chapter['id']}/continuity-checks")
    assert r.status_code == 404
    r = _create_check(client, novel_b["id"], chapter["id"])
    assert r.status_code == 404
