"""P4.1.3 记忆更新正式提交 API 测试。

覆盖：状态/事件/关系（含历史事件）/摘要/秘密应用成功、事务中途失败整体回滚、
目标对象已删除、before_json 过期标 conflict、重复提交幂等、
已拒绝/未审核不能提交、部分接受部分拒绝时提交结果正确。
"""

import json

CONTENT = "林远在战斗中被剑气划伤了左臂，随后被苏月带回客栈。苏月替他包扎伤口。"


def _changes(changes):
    return json.dumps({"changes": changes}, ensure_ascii=False)


def _novel(client, title="记忆提交测试小说"):
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


def _get_state(client, novel_id, character_id):
    return client.get(
        f"/api/novels/{novel_id}/characters/{character_id}/state"
    ).json()


def _relation(client, novel_id, source_id, target_id, relation_type="同伴", **kw):
    r = client.post(
        f"/api/novels/{novel_id}/character-relations",
        json={"source_character_id": source_id, "target_character_id": target_id,
              "relation_type": relation_type, **kw},
    )
    assert r.status_code in (200, 201)
    return r.json()


def _make_batch(client, novel_id, chapter_id, changes):
    fake_payload = _changes(changes)
    return fake_payload


def _create_batch(client, novel_id, chapter_id, **kw):
    return client.post(
        f"/api/novels/{novel_id}/chapters/{chapter_id}/memory-batches", json=kw
    )


def _accept_all(client, novel_id, batch):
    items = [
        {"id": p["id"], "action": "accept"}
        for p in batch["proposals"]
        if p["status"] == "pending"
    ]
    r = client.post(
        f"/api/novels/{novel_id}/memory-batches/{batch['id']}/review",
        json={"items": items},
    )
    assert r.status_code == 200
    return r.json()


def _apply(client, novel_id, batch_id):
    return client.post(f"/api/novels/{novel_id}/memory-batches/{batch_id}/apply")


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
    "reason": "正文明确",
    "source_excerpt": "林远在战斗中被剑气划伤了左臂，随后被苏月带回客栈。",
    "confidence": 0.9,
    "uncertainty": "",
}

EVENT_CHANGE = {
    "proposal_type": "plot_event",
    "operation": "create",
    "event": {
        "title": "林远受伤返回客栈",
        "description": "林远战斗受伤，被苏月带回客栈",
        "event_type": "战斗",
        "participants": [{"name": "林远", "role": "伤者"}, {"name": "苏月", "role": "救助者"}],
    },
    "reason": "正文明确",
    "source_excerpt": "随后被苏月带回客栈。",
    "confidence": 0.9,
    "uncertainty": "",
}

SUMMARY_CHANGE = {
    "proposal_type": "chapter_summary",
    "operation": "update",
    "summary": "林远受伤，苏月带他回客栈包扎。",
    "reason": "概括本章",
    "source_excerpt": "苏月替他包扎伤口。",
    "confidence": 0.8,
    "uncertainty": "",
}

SECRET_CHANGE = {
    "proposal_type": "character_secret",
    "operation": "create",
    "character_name": "林远",
    "secret": {"title": "剑气入体", "content": "剑气残留在林远经脉中", "secrecy_level": "restricted"},
    "reason": "正文暗示",
    "source_excerpt": "被剑气划伤了左臂",
    "confidence": 0.4,
    "uncertainty": "正文未明确说明剑气残留",
}


def _extract(client, fake_ai, novel_id, chapter_id, changes):
    fake_ai.push_text(_changes(changes))
    r = _create_batch(client, novel_id, chapter_id)
    assert r.status_code == 201
    return r.json()


# ----------------------------- 成功应用 -----------------------------

def test_apply_state_update(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [STATE_CHANGE])
    _accept_all(client, novel["id"], batch)
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 200
    body = r.json()
    assert body["batch"]["status"] == "applied"
    assert body["batch"]["applied_at"]
    assert body["applied"][0]["proposal_id"] == batch["proposals"][0]["id"]
    state = _get_state(client, novel["id"], lin["id"])
    assert state["current_location"] == "悦来客栈"
    assert state["health_status"] == "左臂受伤"
    proposal = client.get(
        f"/api/novels/{novel['id']}/memory-proposals/{batch['proposals'][0]['id']}"
    ).json()
    assert proposal["status"] == "applied"
    assert proposal["applied_at"]


def test_apply_plot_event_with_participants(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [EVENT_CHANGE])
    _accept_all(client, novel["id"], batch)
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 200
    events = client.get(
        f"/api/novels/{novel['id']}/plot-events", params={"chapter_id": chapter["id"]}
    ).json()
    assert len(events) == 1
    assert events[0]["title"] == "林远受伤返回客栈"
    assert {p["character_id"] for p in events[0]["participants"]} == {lin["id"], su["id"]}
    # create 类提案应用后回写真实 target_id
    proposal = client.get(
        f"/api/novels/{novel['id']}/memory-proposals/{batch['proposals'][0]['id']}"
    ).json()
    assert proposal["target_id"] == events[0]["id"]


def test_apply_relation_create_and_end_with_history(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    create_change = {
        "proposal_type": "character_relation",
        "operation": "create",
        "source_name": "苏月",
        "target_name": "林远",
        "relation_type": "救助",
        "relation": {"description": "苏月救助受伤的林远"},
        "reason": "正文明确",
        "source_excerpt": "苏月替他包扎伤口。",
        "confidence": 0.8,
        "uncertainty": "",
    }
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [create_change])
    _accept_all(client, novel["id"], batch)
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 200
    relations = client.get(f"/api/novels/{novel['id']}/character-relations").json()
    assert len(relations) == 1
    relation = relations[0]
    assert relation["relation_type"] == "救助"
    assert relation["status"] == "active"
    events = client.get(
        f"/api/novels/{novel['id']}/character-relations/{relation['id']}/events"
    ).json()
    assert [e["event_type"] for e in events] == ["created"]
    assert events[0]["chapter_id"] == chapter["id"]

    # 第二章：结束这条关系
    chapter2 = _chapter(client, novel["id"], content="苏月与林远在客栈门口告别。",
                        title="第二章")
    end_change = {
        "proposal_type": "character_relation",
        "operation": "end",
        "source_name": "苏月",
        "target_name": "林远",
        "relation_type": "救助",
        "relation": {"event_title": "告别"},
        "reason": "正文写到告别",
        "source_excerpt": "苏月与林远在客栈门口告别。",
        "confidence": 0.7,
        "uncertainty": "",
    }
    batch2 = _extract(client, fake_ai, novel["id"], chapter2["id"], [end_change])
    assert batch2["proposals"][0]["target_id"] == relation["id"]
    _accept_all(client, novel["id"], batch2)
    r = _apply(client, novel["id"], batch2["id"])
    assert r.status_code == 200
    relation_after = client.get(
        f"/api/novels/{novel['id']}/character-relations/{relation['id']}"
    ).json()
    assert relation_after["status"] == "ended"
    events = client.get(
        f"/api/novels/{novel['id']}/character-relations/{relation['id']}/events"
    ).json()
    assert [e["event_type"] for e in events] == ["created", "ended"]
    assert events[1]["chapter_id"] == chapter2["id"]


def test_apply_chapter_summary(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [SUMMARY_CHANGE])
    _accept_all(client, novel["id"], batch)
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 200
    detail = client.get(f"/api/novels/{novel['id']}/chapters/{chapter['id']}").json()
    assert detail["summary"] == "林远受伤，苏月带他回客栈包扎。"
    assert detail["content"] == CONTENT  # 正文不受影响


def test_apply_secret_create_unrevealed(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [SECRET_CHANGE])
    _accept_all(client, novel["id"], batch)
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 200
    secrets = client.get(
        f"/api/novels/{novel['id']}/characters/{lin['id']}/secrets"
    ).json()
    assert len(secrets) == 1
    assert secrets[0]["title"] == "剑气入体"
    assert secrets[0]["reveal_status"] == "unrevealed"  # 绝不自动公开


def test_apply_modified_proposal_uses_final_json(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [STATE_CHANGE])
    proposal = batch["proposals"][0]
    modified = dict(proposal["proposed"])
    modified["fields"] = {"current_location": "城南客栈"}
    r = client.patch(
        f"/api/novels/{novel['id']}/memory-proposals/{proposal['id']}",
        json={"final_json": modified},
    )
    assert r.status_code == 200
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 200
    state = _get_state(client, novel["id"], lin["id"])
    assert state["current_location"] == "城南客栈"
    # 未在 final 中的字段保持原值（health_status 未被修改）
    assert state["health_status"] == ""


# ----------------------------- 失败与回滚 -----------------------------

def test_apply_rolls_back_on_mid_failure(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    end_change = {
        "proposal_type": "character_relation",
        "operation": "end",
        "source_name": "苏月",
        "target_name": "林远",
        "relation_type": "救助",
        "relation": {},
        "reason": "测试",
        "source_excerpt": "苏月替他包扎伤口。",
        "confidence": 0.8,
        "uncertainty": "",
    }
    relation = _relation(client, novel["id"], su["id"], lin["id"], "救助")
    batch = _extract(client, fake_ai, novel["id"], chapter["id"],
                     [STATE_CHANGE, end_change])
    _accept_all(client, novel["id"], batch)
    # 提取后删除目标人物：关系被级联删除，应用第二条时必然失败
    client.delete(f"/api/novels/{novel['id']}/characters/{su['id']}")
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 409
    # 整体回滚：第一条状态更新也没有落库
    state = _get_state(client, novel["id"], lin["id"])
    assert state["current_location"] == "青云城"
    assert state["health_status"] == ""
    detail = client.get(f"/api/novels/{novel['id']}/memory-batches/{batch['id']}").json()
    assert detail["status"] != "applied"


def test_apply_before_stale_marks_conflict(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [STATE_CHANGE])
    _accept_all(client, novel["id"], batch)
    # 提案生成后，状态被其他操作修改：before_json 过期
    _set_state(client, novel["id"], lin["id"], current_location="城主府")
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 409
    assert "重新审核" in r.json()["detail"]
    proposal = client.get(
        f"/api/novels/{novel['id']}/memory-proposals/{batch['proposals'][0]['id']}"
    ).json()
    assert proposal["status"] == "conflict"
    # 数据未被提案覆盖
    state = _get_state(client, novel["id"], lin["id"])
    assert state["current_location"] == "城主府"


def test_apply_target_chapter_deleted(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [SUMMARY_CHANGE])
    _accept_all(client, novel["id"], batch)
    client.delete(f"/api/novels/{novel['id']}/chapters/{chapter['id']}")
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 409


def test_apply_twice_rejected_and_no_duplicate(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [EVENT_CHANGE])
    _accept_all(client, novel["id"], batch)
    assert _apply(client, novel["id"], batch["id"]).status_code == 200
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 409
    events = client.get(
        f"/api/novels/{novel['id']}/plot-events", params={"chapter_id": chapter["id"]}
    ).json()
    assert len(events) == 1  # 重复提交不产生重复数据


def test_apply_rejected_batch_blocked(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [STATE_CHANGE])
    pid = batch["proposals"][0]["id"]
    client.post(
        f"/api/novels/{novel['id']}/memory-batches/{batch['id']}/review",
        json={"items": [{"id": pid, "action": "reject"}]},
    )
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 409
    state = _get_state(client, novel["id"], lin["id"])
    assert state["current_location"] == "青云城"


def test_apply_unreviewed_batch_blocked(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [STATE_CHANGE])
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 409
    state = _get_state(client, novel["id"], lin["id"])
    assert state["current_location"] == "青云城"


def test_apply_partial_accept_partial_reject(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    batch = _extract(client, fake_ai, novel["id"], chapter["id"],
                     [STATE_CHANGE, SUMMARY_CHANGE])
    state_p = next(p for p in batch["proposals"] if p["proposal_type"] == "character_state")
    summary_p = next(p for p in batch["proposals"] if p["proposal_type"] == "chapter_summary")
    client.post(
        f"/api/novels/{novel['id']}/memory-batches/{batch['id']}/review",
        json={"items": [
            {"id": state_p["id"], "action": "accept"},
            {"id": summary_p["id"], "action": "reject"},
        ]},
    )
    r = _apply(client, novel["id"], batch["id"])
    assert r.status_code == 200
    assert len(r.json()["applied"]) == 1
    # 状态已更新，摘要保持原值（被拒绝的提案不提交）
    assert _get_state(client, novel["id"], lin["id"])["current_location"] == "悦来客栈"
    detail = client.get(f"/api/novels/{novel['id']}/chapters/{chapter['id']}").json()
    assert detail["summary"] == ""
    proposals = {p["id"]: p["status"] for p in r.json()["batch"]["proposals"]}
    assert proposals[state_p["id"]] == "applied"
    assert proposals[summary_p["id"]] == "rejected"


def test_apply_cross_novel_blocked(client, fake_ai, ai_task_models):
    novel, lin, su, chapter = _setup(client)
    other = _novel(client, "另一本小说")
    batch = _extract(client, fake_ai, novel["id"], chapter["id"], [STATE_CHANGE])
    _accept_all(client, novel["id"], batch)
    r = _apply(client, other["id"], batch["id"])
    assert r.status_code == 404
    assert _get_state(client, novel["id"], lin["id"])["current_location"] == "青云城"
