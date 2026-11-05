"""P3.3 人物档案接口测试。"""

import sqlite3


def _create_novel(client, title="人物档案测试小说"):
    response = client.post("/api/novels", json={"title": title})
    assert response.status_code == 200, response.text
    return response.json()


def _create_character(client, novel_id, name="沈璃", **extra):
    payload = {"name": name}
    payload.update(extra)
    response = client.post(f"/api/novels/{novel_id}/characters", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_create_character_minimal_fields(client):
    """仅填写姓名即可创建；同一事务自动初始化默认状态。"""
    novel = _create_novel(client, "P3.3 最小")
    character = _create_character(client, novel["id"])
    assert character["name"] == "沈璃"
    assert character["state"] is not None
    assert character["state"]["life_status"] == "alive"
    assert character["state"]["character_id"] == character["id"]


def test_create_character_full_fields(client):
    novel = _create_novel(client, "P3.3 完整")
    character = _create_character(
        client,
        novel["id"],
        aliases=["璃儿", "清玄道人", " 璃儿 "],
        gender="女",
        age="约两百岁",
        race="灵族",
        identity="青云宗弟子",
        role="主角",
        appearance="一袭白衣，腰间悬挂墨玉笛。",
        personality="清冷孤傲，实则内心柔软。",
        background="自小在孤儿院里长大，被青云宗收养。",
        abilities="精通水系法术与制笛之术。",
        cultivation="金丹后期",
        affiliation="青云宗",
        tags=["主角", "水系"],
        attributes={"佩剑": "墨云", "灵兽": "青鸾", "年龄": 200},
        avatar_color="#3b5bdb",
        sort_order=10,
    )
    assert character["aliases"] == ["璃儿", "清玄道人"]
    assert character["age"] == "约两百岁"
    assert character["role"] == "主角"
    assert character["tags"] == ["主角", "水系"]
    assert character["attributes"] == {"佩剑": "墨云", "灵兽": "青鸾", "年龄": 200}


def test_list_search_and_role_filter(client):
    novel = _create_novel(client, "P3.3 列表")
    _create_character(client, novel["id"], name="沈璃", role="主角", identity="青云宗弟子", background="孤儿", tags=["主角", "水系"])
    _create_character(client, novel["id"], name="玄辰", role="反派", identity="魔道少主", background="皇族")
    _create_character(client, novel["id"], name="苏白", role="配角", identity="医师", background="山野", tags=["配角"])

    listing = client.get(f"/api/novels/{novel['id']}/characters").json()
    assert len(listing) == 3
    assert all("life_status" in item for item in listing)

    role_filter = client.get(f"/api/novels/{novel['id']}/characters", params={"role": "主角"}).json()
    assert [item["name"] for item in role_filter] == ["沈璃"]

    search = client.get(f"/api/novels/{novel['id']}/characters", params={"search": "玄"}).json()
    assert [item["name"] for item in search] == ["玄辰"]

    tag_filter = client.get(
        f"/api/novels/{novel['id']}/characters", params={"tag": "主角"}
    ).json()
    assert len(tag_filter) == 1
    assert tag_filter[0]["name"] == "沈璃"

    sort_name = client.get(
        f"/api/novels/{novel['id']}/characters", params={"sort": "name"}
    ).json()
    names_sorted = sorted([item["name"] for item in sort_name])
    assert [item["name"] for item in sort_name] == names_sorted


def test_get_and_update_character(client):
    novel = _create_novel(client, "P3.3 详情")
    character = _create_character(client, novel["id"], name="沈璃")

    fetched = client.get(f"/api/novels/{novel['id']}/characters/{character['id']}").json()
    assert fetched["name"] == "沈璃"
    assert fetched["state"]["life_status"] == "alive"

    updated = client.put(
        f"/api/novels/{novel['id']}/characters/{character['id']}",
        json={"name": "沈璃·清玄", "role": "反派", "tags": ["改名"]},
    )
    assert updated.status_code == 200
    data = updated.json()
    assert data["name"] == "沈璃·清玄"
    assert data["role"] == "反派"
    assert data["tags"] == ["改名"]


def test_update_without_name_strips_blank(client):
    novel = _create_novel(client, "P3.3 空白")
    character = _create_character(client, novel["id"], name="沈璃")
    updated = client.put(
        f"/api/novels/{novel['id']}/characters/{character['id']}",
        json={"age": "  约两百岁  "},
    )
    assert updated.status_code == 200
    assert updated.json()["age"] == "约两百岁"


def test_create_character_empty_name_rejected(client):
    novel = _create_novel(client)
    response = client.post(
        f"/api/novels/{novel['id']}/characters", json={"name": "   "}
    )
    assert response.status_code == 422


def test_same_novel_allows_same_name(client):
    novel = _create_novel(client, "P3.3 重名")
    _create_character(client, novel["id"], name="沈璃")
    dup = _create_character(client, novel["id"], name="沈璃", aliases=["二号"])
    assert dup["aliases"] == ["二号"]


def test_state_get_and_update(client):
    novel = _create_novel(client, "P3.3 状态")
    character = _create_character(client, novel["id"], name="沈璃")

    state = client.get(
        f"/api/novels/{novel['id']}/characters/{character['id']}/state"
    ).json()
    assert state["life_status"] == "alive"
    assert state["current_location"] == ""

    updated = client.put(
        f"/api/novels/{novel['id']}/characters/{character['id']}/state",
        json={
            "life_status": "dead",
            "current_location": "九幽",
            "current_cultivation": "元婴期",
            "health_status": "已陨落",
            "emotional_state": "悲壮",
            "current_goal": "寻找转世之体",
            "attributes": {"死因": "魔道围攻"},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["life_status"] == "dead"
    assert updated.json()["current_location"] == "九幽"
    assert updated.json()["attributes"] == {"死因": "魔道围攻"}


def test_secret_crud_and_isolation(client):
    novel = _create_novel(client, "P3.3 秘密")
    c1 = _create_character(client, novel["id"], name="沈璃")
    c2 = _create_character(client, novel["id"], name="玄辰")

    secret = client.post(
        f"/api/novels/{novel['id']}/characters/{c1['id']}/secrets",
        json={
            "title": "真实身世",
            "content": "并非孤儿，乃是灵族亡国公主。",
            "secrecy_level": "secret",
            "reveal_status": "unrevealed",
            "notes": "第三卷将公开",
        },
    )
    assert secret.status_code == 200
    secret_id = secret.json()["id"]
    assert secret.json()["secrecy_level"] == "secret"

    secrets = client.get(
        f"/api/novels/{novel['id']}/characters/{c1['id']}/secrets"
    ).json()
    assert len(secrets) == 1

    # c2 的秘密列表为空
    secrets2 = client.get(
        f"/api/novels/{novel['id']}/characters/{c2['id']}/secrets"
    ).json()
    assert secrets2 == []

    # 更新秘密
    updated = client.put(
        f"/api/novels/{novel['id']}/characters/{c1['id']}/secrets/{secret_id}",
        json={"reveal_status": "partially_revealed", "content": "灵族公主，本名沈清玄。"},
    )
    assert updated.status_code == 200
    assert updated.json()["reveal_status"] == "partially_revealed"

    # 篡改 character_id 不返回 c1 的秘密
    wrong = client.get(
        f"/api/novels/{novel['id']}/characters/{c2['id']}/secrets/{secret_id}"
    )
    assert wrong.status_code == 404

    # 删除秘密
    deleted = client.delete(
        f"/api/novels/{novel['id']}/characters/{c1['id']}/secrets/{secret_id}"
    )
    assert deleted.status_code == 200
    assert client.get(
        f"/api/novels/{novel['id']}/characters/{c1['id']}/secrets"
    ).json() == []


def test_cross_novel_access_rejected(client):
    n1 = _create_novel(client, "N1")
    n2 = _create_novel(client, "N2")
    c1 = _create_character(client, n1["id"], name="沈璃")
    s1 = client.post(
        f"/api/novels/{n1['id']}/characters/{c1['id']}/secrets",
        json={"title": "秘密A"},
    ).json()

    # 跨小说获取人物
    assert client.get(f"/api/novels/{n2['id']}/characters/{c1['id']}").status_code == 404
    # 跨小说获取状态
    assert client.get(
        f"/api/novels/{n2['id']}/characters/{c1['id']}/state"
    ).status_code == 404
    # 跨小说获取秘密
    assert client.get(
        f"/api/novels/{n2['id']}/characters/{c1['id']}/secrets"
    ).status_code == 404
    assert client.get(
        f"/api/novels/{n2['id']}/characters/{c1['id']}/secrets/{s1['id']}"
    ).status_code == 404
    # 跨小说修改秘密
    assert client.put(
        f"/api/novels/{n2['id']}/characters/{c1['id']}/secrets/{s1['id']}",
        json={"title": "被篡改"},
    ).status_code == 404
    # 跨小说删除人物
    assert client.delete(
        f"/api/novels/{n2['id']}/characters/{c1['id']}"
    ).status_code == 404

    # n2 的人物列表看不到 n1 的人物
    assert client.get(f"/api/novels/{n2['id']}/characters").json() == []


def test_delete_character_cascade(client):
    novel = _create_novel(client, "P3.3 级联")
    character = _create_character(client, novel["id"], name="沈璃")
    client.put(
        f"/api/novels/{novel['id']}/characters/{character['id']}/state",
        json={"life_status": "alive"},
    )
    client.post(
        f"/api/novels/{novel['id']}/characters/{character['id']}/secrets",
        json={"title": "秘密"},
    )

    deleted = client.delete(
        f"/api/novels/{novel['id']}/characters/{character['id']}"
    )
    assert deleted.status_code == 200

    # 验证数据库清理
    response = client.get(f"/api/novels/{novel['id']}/characters/{character['id']}")
    assert response.status_code == 404

    # 使用 sqlite 直接验证级联
    import os
    from app.core.config import get_settings
    db_path = get_settings().database_path
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    assert conn.execute("SELECT COUNT(*) FROM characters WHERE id = ?", (character["id"],)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM character_states WHERE character_id = ?", (character["id"],)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM character_secrets WHERE character_id = ?", (character["id"],)).fetchone()[0] == 0
    conn.close()


def test_delete_novel_cleans_character_data(client):
    novel = _create_novel(client, "P3.3 删小说")
    c1 = _create_character(client, novel["id"], name="沈璃")
    _create_character(client, novel["id"], name="玄辰")
    client.post(
        f"/api/novels/{novel['id']}/characters/{c1['id']}/secrets",
        json={"title": "秘密"},
    )

    deleted = client.delete(f"/api/novels/{novel['id']}")
    assert deleted.status_code == 200

    import os
    from app.core.config import get_settings
    db_path = get_settings().database_path
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM character_states").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM character_secrets").fetchone()[0] == 0
    conn.close()


def test_novel_detail_includes_character_count(client):
    novel = _create_novel(client, "P3.3 计数")
    _create_character(client, novel["id"], name="沈璃")
    _create_character(client, novel["id"], name="玄辰")
    detail = client.get(f"/api/novels/{novel['id']}").json()
    assert detail["stats"]["character_count"] == 2


def test_secret_title_required(client):
    novel = _create_novel(client, "P3.3 秘密标题")
    c = _create_character(client, novel["id"], name="沈璃")
    assert client.post(
        f"/api/novels/{novel['id']}/characters/{c['id']}/secrets",
        json={"title": "   "},
    ).status_code == 422
