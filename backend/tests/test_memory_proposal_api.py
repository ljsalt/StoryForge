"""P4.1.3 记忆更新提案 API 测试。

覆盖：多类型提案生成、事件去重、不确定信息降置信、无变化跳过、
目标未解析标 conflict、提案修改/接受/拒绝、批量审核、跨小说隔离、
world_entry 仅作参考不可接受、坏 JSON 修复与失败。
"""

import json

CONTENT = "林远在战斗中被剑气划伤了左臂，随后被苏月带回客栈。苏月替他包扎伤口。"


def _changes(changes):
    return json.dumps({"changes": changes}, ensure_ascii=False)


def _novel(client, title="记忆提案测试小说"):
    return client.post("/api/novels", json={"title": title}).json()


def _chapter(client, novel_id, content=CONTENT, **kw):
    payload = {"title": "第一章", "content": content}
    payload.update(kw)
    r = client.post(f"/api/novels/{novel_id}/chapters", json=payload)
    assert r.status_code in (200, 201)
    return r.json()


def _character(client, novel_id, name, **kw):
    r = client.post(f"/api/novels/{novel_id}/characters", json={"name": name, **kw})
    assert r.status_code in (200, 201)
    return r.json()


def _set_state(client, novel_id, character_id, **fields):
    r = client.put(
        f"/api/novels/{novel_id}/characters/{character_id}/state", json=fields
    )
    assert r.status_code == 200
    return r.json()


def _create_batch(client, novel_id, chapter_id, **kw):
    return client.post(
        f"/api/novels/{novel_id}/chapters/{chapter_id}/memory-batches", json=kw
    )


def _setup(client):
    novel = _novel(client)
    lin = _character(client, novel["id"], "林远")
    su = _character(client, novel["id"], "苏月")
    _set_state(client, novel["id"], lin["id"], current_location="青云城")
    chapter = _chapter(client, novel["id"])
    return novel, lin, su, chapter


STATE_CHANGE = {
    "proposal_type": "character_state",
    "operation": "update",
    "character_name": "林远",
    "fields": {"current_location": "悦来客栈", "health_status": "左臂受伤"},
    "reason": "正文明确写到受伤并被带回客栈",
    "source_excerpt": "林远在战斗中被剑气划伤了左臂，随后被苏月带回客栈。",
    "confidence": 0.9,
    "uncertainty": "",
}

EVENT_CHANGE = {
    "proposal_type": "plot_event",
    "operation": "create",
    "event": {
        "title": "林远受伤返回客栈",
        "description": "林远战斗受伤，被苏月带回悦来客栈包扎",
        "event_type": "战斗",
        "importance": "normal",
        "participants": [
            {"name": "林远", "role": "伤者"},
            {"name": "苏月", "role": "救助者"},
        ],
    },
    "reason": "正文明确发生",
    "source_excerpt": "随后被苏月带回客栈。",
    "confidence": 0.9,
    "uncertainty": "",
}

SUMMARY_CHANGE = {
    "proposal_type": "chapter_summary",
    "operation": "update",
    "summary": "林远战斗受伤，苏月将其带回客栈包扎。",
    "reason": "概括本章主要剧情",
    "source_excerpt": "随后被苏月带回客栈。苏月替他包扎伤口。",
    "confidence": 0.8,
    "uncertainty": "",
}

RELATION_CHANGE = {
    "proposal_type": "character_relation",
    "operation": "create",
    "source_name": "苏月",
    "target_name": "林远",
    "relation_type": "救助",
    "relation": {"description": "苏月救助受伤的林远"},
    "reason": "正文明确写到救助行为",
    "source_excerpt": "苏月替他包扎伤口。",
    "confidence": 0.7,
    "uncertainty": "",
}


# ----------------------------- 提取与解析 -----------------------------

def test_extract_multi_type_proposals(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    fake_ai.push_text(_changes([STATE_CHANGE, EVENT_CHANGE, SUMMARY_CHANGE, RELATION_CHANGE]))
    r = _create_batch(client, novel["id"], chapter["id"])
    assert r.status_code == 201
    batch = r.json()
    assert batch["status"] == "pending_review"
    proposals = batch["proposals"]
    assert len(proposals) == 4

    state = next(p for p in proposals if p["proposal_type"] == "character_state")
    assert state["target_id"] == lin["id"]
    assert state["before"] == {"current_location": "青云城", "health_status": ""}
    assert state["proposed"]["fields"]["current_location"] == "悦来客栈"
    assert state["status"] == "pending"
    assert state["current"]["state"]["current_location"] == "青云城"

    event = next(p for p in proposals if p["proposal_type"] == "plot_event")
    ids = {p["character_id"] for p in event["proposed"]["participants"]}
    assert ids == {lin["id"], su["id"]}

    summary = next(p for p in proposals if p["proposal_type"] == "chapter_summary")
    assert summary["target_type"] == "chapter"
    assert summary["before"] == {"summary": ""}

    relation = next(p for p in proposals if p["proposal_type"] == "character_relation")
    assert relation["proposed"]["source_character_id"] == su["id"]
    assert relation["proposed"]["target_character_id"] == lin["id"]


def test_extract_dedup_event(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    # 本章已有同名事件
    client.post(
        f"/api/novels/{novel['id']}/plot-events",
        json={"title": "林远受伤返回客栈", "chapter_id": chapter["id"]},
    )
    duplicate = dict(EVENT_CHANGE)
    second = dict(EVENT_CHANGE, event=dict(EVENT_CHANGE["event"], title="包扎伤口"))
    fake_ai.push_text(_changes([duplicate, second, second]))  # 第二条重复出现两次
    r = _create_batch(client, novel["id"], chapter["id"])
    assert r.status_code == 201
    batch = r.json()
    events = [p for p in batch["proposals"] if p["proposal_type"] == "plot_event"]
    assert len(events) == 1
    assert events[0]["proposed"]["title"] == "包扎伤口"
    skipped = "；".join(batch["report"].get("skipped", []))
    assert "林远受伤返回客栈" in skipped
    assert "包扎伤口" in skipped  # 同批次内重复也被去重


def test_extract_uncertainty_lowers_confidence(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    change = dict(STATE_CHANGE, confidence=0.95, uncertainty="正文未明确说明伤势程度")
    fake_ai.push_text(_changes([change]))
    r = _create_batch(client, novel["id"], chapter["id"])
    proposal = r.json()["proposals"][0]
    assert proposal["confidence"] <= 0.5
    assert "不确定" in proposal["reason"]


def test_extract_no_change_skipped(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    same = dict(STATE_CHANGE, fields={"current_location": "青云城"})
    fake_ai.push_text(_changes([same]))
    r = _create_batch(client, novel["id"], chapter["id"])
    batch = r.json()
    assert batch["proposals"] == []
    assert batch["report"]["counts"]["created"] == 0


def test_extract_unresolved_target_marked_conflict(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    ghost = dict(STATE_CHANGE, character_name="不存在的人")
    fake_ai.push_text(_changes([ghost]))
    r = _create_batch(client, novel["id"], chapter["id"])
    proposal = r.json()["proposals"][0]
    assert proposal["status"] == "conflict"
    assert proposal["target_id"] is None
    assert r.json()["report"]["unresolved"] == 1


def test_extract_bad_json_repair_once(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    fake_ai.push_text("不是 JSON")
    fake_ai.push_text(_changes([SUMMARY_CHANGE]))
    r = _create_batch(client, novel["id"], chapter["id"])
    assert r.status_code == 201
    assert len(r.json()["proposals"]) == 1


def test_extract_bad_json_fails(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    fake_ai.push_text("不是 JSON")
    fake_ai.push_text("仍然不是 JSON")
    r = _create_batch(client, novel["id"], chapter["id"])
    assert r.status_code == 502
    # 失败不留半成品批次
    batches = client.get(
        f"/api/novels/{novel['id']}/chapters/{chapter['id']}/memory-batches"
    ).json()
    assert batches == []


def test_extract_truncated(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    fake_ai.push_text('{"changes": [', finish_reason="length")
    r = _create_batch(client, novel["id"], chapter["id"])
    assert r.status_code == 502
    assert "截断" in r.json()["detail"]


def test_extract_ai_failure(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    fake_ai.push_error("network_error")
    r = _create_batch(client, novel["id"], chapter["id"])
    assert r.status_code == 502


# ----------------------------- 审核 -----------------------------

def test_proposal_update_accept_reject(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    fake_ai.push_text(_changes([STATE_CHANGE, SUMMARY_CHANGE]))
    batch = _create_batch(client, novel["id"], chapter["id"]).json()
    state = next(p for p in batch["proposals"] if p["proposal_type"] == "character_state")
    summary = next(p for p in batch["proposals"] if p["proposal_type"] == "chapter_summary")

    # 修改后接受：final_json 才是最终提交内容
    modified = dict(state["proposed"])
    modified["fields"] = {"current_location": "城南客栈", "health_status": "左臂轻伤"}
    r = client.patch(
        f"/api/novels/{novel['id']}/memory-proposals/{state['id']}",
        json={"final_json": modified, "user_note": "按润色后正文修正"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "modified"
    assert body["final"]["fields"]["current_location"] == "城南客栈"
    assert body["user_note"] == "按润色后正文修正"

    r = client.post(
        f"/api/novels/{novel['id']}/memory-proposals/{summary['id']}/reject",
        json={"user_note": "摘要再议"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"

    # 全部处理完毕（modified + rejected）→ approved
    detail = client.get(f"/api/novels/{novel['id']}/memory-batches/{batch['id']}").json()
    assert detail["status"] == "approved"
    assert detail["reviewed_at"]


def test_batch_review_mixed(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    fake_ai.push_text(_changes([STATE_CHANGE, EVENT_CHANGE, SUMMARY_CHANGE]))
    batch = _create_batch(client, novel["id"], chapter["id"]).json()
    items = [
        {"id": p["id"], "action": "accept"}
        for p in batch["proposals"][:1]
    ] + [
        {"id": p["id"], "action": "reject", "user_note": "不需要"}
        for p in batch["proposals"][1:2]
    ]
    r = client.post(
        f"/api/novels/{novel['id']}/memory-batches/{batch['id']}/review",
        json={"items": items},
    )
    assert r.status_code == 200
    # 还剩一条 pending → partially_approved
    assert r.json()["status"] == "partially_approved"
    statuses = {p["id"]: p["status"] for p in r.json()["proposals"]}
    assert statuses[batch["proposals"][0]["id"]] == "accepted"
    assert statuses[batch["proposals"][1]["id"]] == "rejected"
    assert statuses[batch["proposals"][2]["id"]] == "pending"


def test_batch_review_reset_to_pending(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    fake_ai.push_text(_changes([STATE_CHANGE]))
    batch = _create_batch(client, novel["id"], chapter["id"]).json()
    pid = batch["proposals"][0]["id"]
    client.post(
        f"/api/novels/{novel['id']}/memory-batches/{batch['id']}/review",
        json={"items": [{"id": pid, "action": "accept"}]},
    )
    r = client.post(
        f"/api/novels/{novel['id']}/memory-batches/{batch['id']}/review",
        json={"items": [{"id": pid, "action": "reset"}]},
    )
    assert r.status_code == 200
    assert r.json()["proposals"][0]["status"] == "pending"
    assert r.json()["status"] == "pending_review"


def test_world_entry_proposal_cannot_be_accepted(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    world_change = {
        "proposal_type": "world_entry",
        "operation": "create",
        "world_entry": {"name": "剑气", "category": "力量体系", "content": "剑修外放的锋锐之气"},
        "reason": "正文出现剑气",
        "source_excerpt": "被剑气划伤了左臂",
        "confidence": 0.6,
        "uncertainty": "",
    }
    fake_ai.push_text(_changes([world_change]))
    batch = _create_batch(client, novel["id"], chapter["id"]).json()
    proposal = batch["proposals"][0]
    assert proposal["apply_supported"] is False
    r = client.post(
        f"/api/novels/{novel['id']}/memory-proposals/{proposal['id']}/accept", json={}
    )
    assert r.status_code == 400
    r = client.patch(
        f"/api/novels/{novel['id']}/memory-proposals/{proposal['id']}",
        json={"final_json": {"name": "剑气"}},
    )
    assert r.status_code == 400


# ----------------------------- 跨小说隔离 -----------------------------

def test_memory_cross_novel_isolation(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    other = _novel(client, "另一本小说")
    fake_ai.push_text(_changes([STATE_CHANGE]))
    batch = _create_batch(client, novel["id"], chapter["id"]).json()
    pid = batch["proposals"][0]["id"]

    assert client.get(f"/api/novels/{other['id']}/memory-batches/{batch['id']}").status_code == 404
    assert client.get(
        f"/api/novels/{other['id']}/memory-batches/{batch['id']}/proposals"
    ).status_code == 404
    assert client.get(f"/api/novels/{other['id']}/memory-proposals/{pid}").status_code == 404
    assert client.patch(
        f"/api/novels/{other['id']}/memory-proposals/{pid}",
        json={"final_json": {"x": 1}},
    ).status_code == 404
    assert client.post(
        f"/api/novels/{other['id']}/memory-proposals/{pid}/accept", json={}
    ).status_code == 404
    assert client.post(
        f"/api/novels/{other['id']}/memory-batches/{batch['id']}/apply"
    ).status_code == 404
    assert _create_batch(client, other["id"], chapter["id"]).status_code == 404
