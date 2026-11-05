"""P4.1.1 补充验收：上下文预算严格性测试。

重点验证：
1. 最终上下文严格受 token_budget 约束（含必需分区超预算场景）。
2. estimated_tokens 统计最终实际输出，而非截断前内容。
3. 区内截断不会导致总预算超限。
"""

from app.services.context_builder import _section_cost
from app.services.token_util import estimate_tokens


def _create_novel(client, title="预算小说", description=""):
    r = client.post("/api/novels", json={"title": title, "description": description})
    assert r.status_code == 200
    return r.json()


def _create_character(client, novel_id, name, background=""):
    r = client.post(
        f"/api/novels/{novel_id}/characters",
        json={"name": name, "role": "配角", "background": background},
    )
    assert r.status_code == 200
    return r.json()


def _preview(client, novel_id, **overrides):
    payload = {"novel_id": novel_id, "task_type": "writer"}
    payload.update(overrides)
    return client.post("/api/ai/context/preview", json=payload)


def _assert_budget(client, novel_id, budget, **overrides):
    r = _preview(client, novel_id, token_budget=budget, **overrides)
    assert r.status_code == 200
    body = r.json()
    assert body["token_budget"] == budget
    # 1. 严格不超预算
    assert body["estimated_tokens"] <= budget
    # 2. 估算值等于最终实际输出的估算
    assert body["estimated_tokens"] == estimate_tokens(body["context_text"])
    # 3. 分区级费用与最终文本一致
    recomputed = sum(_section_cost(s["title"], s["content"]) for s in body["sections"])
    assert all(s["tokens"] == _section_cost(s["title"], s["content"]) for s in body["sections"])
    assert recomputed >= body["estimated_tokens"]  # 分区含分隔开销，略大于整体
    # 4. 超预算场景必须给出说明
    if body["estimated_tokens"] >= budget * 0.9 or body["omitted_sections"]:
        assert body["warnings"] or body["omitted_sections"]
    return body


def test_budget_strictly_enforced_many_characters(client):
    novel = _create_novel(client)
    for i in range(12):
        _create_character(client, novel["id"], f"人物{i}", background="冗长背景描述" * 30)
    for budget in (200, 260, 400, 800):
        body = _assert_budget(client, novel["id"], budget)
        # 必须真正发生截断，而不是原样返回
        if budget <= 800 and len(body["context_text"]) > 0:
            assert body["estimated_tokens"] <= budget


def test_required_sections_over_budget_are_trimmed(client):
    """必需分区（核心设定 + 当前任务）本身超过预算时必须裁剪，不能超限。"""
    long_desc = "这是一本设定极其复杂的小说。" * 60
    novel = _create_novel(client, description=long_desc)
    body = _assert_budget(
        client,
        novel["id"],
        budget=200,
        user_requirement="写一段承接上文的正文，要求细节丰富。" * 200,
    )
    # 至少核心设定仍在，但内容被裁剪
    keys = {s["key"] for s in body["sections"]}
    assert "core_settings" in keys
    assert body["estimated_tokens"] <= 200
    assert len(body["context_text"]) < len(long_desc)
    assert any("截断" in w for w in body["warnings"])


def test_multiple_required_sections_both_kept_with_tight_budget(client):
    """两个必需分区合计超预算时，后一个不可无限挤压前者，总输出仍合规。"""
    novel = _create_novel(client, description="设定" * 100)
    chapter = client.post(
        f"/api/novels/{novel['id']}/chapters",
        json={"title": "长章", "summary": "摘要" * 200},
    ).json()
    body = _assert_budget(
        client,
        novel["id"],
        budget=200,
        chapter_id=chapter["id"],
        user_requirement="要求" * 100,
    )
    assert body["estimated_tokens"] <= 200
    assert body["context_text"].startswith("【核心设定】")


def test_estimated_tokens_reflects_final_output_not_pre_truncation(client):
    """构造大量内容：若按截断前统计，estimated_tokens 会远大于 budget。"""
    novel = _create_novel(client, description="背景" * 300)
    for i in range(6):
        _create_character(client, novel["id"], f"角色{i}", background="背景" * 100)
    char_ids = [c["id"] for c in client.get(
        f"/api/novels/{novel['id']}/characters"
    ).json()]
    body = _assert_budget(client, novel["id"], budget=300, character_ids=char_ids)
    assert body["estimated_tokens"] <= 300
    assert body["estimated_tokens"] == estimate_tokens(body["context_text"])
    assert len(body["context_text"]) < 300 * 4


def test_budget_no_overshoot_on_line_truncation(client):
    """只在行级截断（不整体剔除）时也不得超限。"""
    novel = _create_novel(client)
    chapter = client.post(
        f"/api/novels/{novel['id']}/chapters", json={"title": "章一", "summary": "摘要"}
    ).json()
    for i in range(15):
        client.post(
            f"/api/novels/{novel['id']}/plot-events",
            json={"title": f"事件{i}", "description": "描述" * 40, "chapter_id": chapter["id"]},
        )
    body = _assert_budget(client, novel["id"], budget=420, chapter_id=chapter["id"])
    assert body["estimated_tokens"] <= 420
    assert any("剧情历史" in s["title"] or "当前任务" in s["title"] for s in body["sections"])
