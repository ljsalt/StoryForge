"""P3.2.1 世界观基础管理接口测试。"""

import sqlite3

from app.database.db import DEFAULT_WORLD_CATEGORIES


def _create_novel(client, title="世界观测试小说"):
    response = client.post("/api/novels", json={"title": title})
    assert response.status_code == 200, response.text
    return response.json()


def _categories(client, novel_id):
    response = client.get(f"/api/novels/{novel_id}/world/categories")
    assert response.status_code == 200, response.text
    return response.json()


def _category_id(client, novel_id, name="地理与区域"):
    for item in _categories(client, novel_id):
        if item["name"] == name:
            return item["id"]
    raise AssertionError(f"未找到分类 {name}")


def _create_entry(client, novel_id, category_id, name="青木府城", **extra):
    payload = {"name": name, "category_id": category_id}
    payload.update(extra)
    response = client.post(f"/api/novels/{novel_id}/world/entries", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_novel_creation_seeds_default_categories(client):
    novel = _create_novel(client)
    categories = _categories(client, novel["id"])
    assert [item["name"] for item in categories] == list(DEFAULT_WORLD_CATEGORIES)
    assert all(item["entry_count"] == 0 for item in categories)


def test_create_category_and_update(client):
    novel = _create_novel(client)
    response = client.post(
        f"/api/novels/{novel['id']}/world/categories",
        json={"name": "自定义分类", "description": "专属设定", "sort_order": 100},
    )
    assert response.status_code == 200
    category = response.json()
    assert category["name"] == "自定义分类"
    assert category["entry_count"] == 0

    updated = client.put(
        f"/api/novels/{novel['id']}/world/categories/{category['id']}",
        json={"name": "自定义分类改名", "description": "更新说明", "sort_order": 5},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "自定义分类改名"
    assert updated.json()["description"] == "更新说明"
    assert updated.json()["sort_order"] == 5

    duplicate = client.post(
        f"/api/novels/{novel['id']}/world/categories",
        json={"name": "地理与区域"},
    )
    assert duplicate.status_code == 400
    assert "同名分类" in duplicate.json()["detail"]


def test_create_entry_with_attributes_and_tags(client):
    novel = _create_novel(client)
    category_id = _category_id(client, novel["id"], "地理与区域")
    entry = _create_entry(
        client,
        novel["id"],
        category_id,
        summary="东部重镇",
        content="青木府城是远东皇朝东部最大的府城，人口稠密，商贸发达。",
        tags=["东方", "城邦", " 东方 "],
        attributes={"类型": "府城", "人口": 120000, "是否核心": True},
        sort_order=10,
    )
    assert entry["category_name"] == "地理与区域"
    assert entry["tags"] == ["东方", "城邦"]
    assert entry["attributes"] == {"类型": "府城", "人口": 120000, "是否核心": True}
    assert entry["parent_id"] is None

    stats = client.get(f"/api/novels/{novel['id']}/world/stats").json()
    assert stats["total_entries"] == 1
    assert stats["category_count"] == len(DEFAULT_WORLD_CATEGORIES)
    geo = next(item for item in stats["by_category"] if item["name"] == "地理与区域")
    assert geo["count"] == 1
    assert stats["latest_updated_at"] is not None


def test_entry_validation(client):
    novel = _create_novel(client)
    category_id = _category_id(client, novel["id"])
    empty_name = client.post(
        f"/api/novels/{novel['id']}/world/entries",
        json={"name": "   ", "category_id": category_id},
    )
    assert empty_name.status_code == 422

    bad_tags = client.post(
        f"/api/novels/{novel['id']}/world/entries",
        json={"name": "设定", "category_id": category_id, "tags": "不是数组"},
    )
    assert bad_tags.status_code == 422

    bad_attributes = client.post(
        f"/api/novels/{novel['id']}/world/entries",
        json={"name": "设定", "category_id": category_id, "attributes": ["不是对象"]},
    )
    assert bad_attributes.status_code == 422


def test_update_entry(client):
    novel = _create_novel(client)
    category_id = _category_id(client, novel["id"])
    entry = _create_entry(client, novel["id"], category_id)
    updated = client.put(
        f"/api/novels/{novel['id']}/world/entries/{entry['id']}",
        json={
            "name": "青木府城（新）",
            "summary": "更新后的简介",
            "content": "更新后的详细描述",
            "tags": ["东方", "重镇"],
            "attributes": {"类型": "府城", "规模": "大型"},
            "sort_order": 99,
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "青木府城（新）"
    assert body["summary"] == "更新后的简介"
    assert body["tags"] == ["东方", "重镇"]
    assert body["attributes"] == {"类型": "府城", "规模": "大型"}
    assert body["sort_order"] == 99


def test_delete_entry(client):
    novel = _create_novel(client)
    category_id = _category_id(client, novel["id"])
    entry = _create_entry(client, novel["id"], category_id)
    deleted = client.delete(f"/api/novels/{novel['id']}/world/entries/{entry['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/api/novels/{novel['id']}/world/entries/{entry['id']}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "世界观设定不存在"
    stats = client.get(f"/api/novels/{novel['id']}/world/stats").json()
    assert stats["total_entries"] == 0


def test_list_search_category_and_tag_filters(client):
    novel = _create_novel(client)
    geo = _category_id(client, novel["id"], "地理与区域")
    power = _category_id(client, novel["id"], "势力与组织")
    first = _create_entry(
        client,
        novel["id"],
        geo,
        name="青木府城",
        summary="东部重镇",
        content="位于远东皇朝东部。",
        tags=["东方", "城邦"],
        sort_order=1,
    )
    second = _create_entry(
        client,
        novel["id"],
        geo,
        name="黑石山脉",
        summary="横贯大陆的山脉",
        content="山脉中蕴藏灵石。",
        tags=["地理", "山脉"],
        sort_order=2,
    )
    third = _create_entry(
        client, novel["id"], power, name="青云宗", tags=["东方", "宗门"], sort_order=3
    )

    all_entries = client.get(f"/api/novels/{novel['id']}/world/entries").json()
    assert [item["id"] for item in all_entries] == [
        first["id"],
        second["id"],
        third["id"],
    ]

    keyword = client.get(
        f"/api/novels/{novel['id']}/world/entries", params={"search": "青木"}
    ).json()
    assert len(keyword) == 1 and keyword[0]["name"] == "青木府城"

    content_keyword = client.get(
        f"/api/novels/{novel['id']}/world/entries", params={"search": "灵石"}
    ).json()
    assert len(content_keyword) == 1 and content_keyword[0]["name"] == "黑石山脉"

    by_category = client.get(
        f"/api/novels/{novel['id']}/world/entries", params={"category_id": geo}
    ).json()
    assert {item["name"] for item in by_category} == {"青木府城", "黑石山脉"}

    by_tag = client.get(
        f"/api/novels/{novel['id']}/world/entries", params={"tag": "东方"}
    ).json()
    assert {item["name"] for item in by_tag} == {"青木府城", "青云宗"}


def test_category_delete_restriction(client):
    novel = _create_novel(client)
    category = client.post(
        f"/api/novels/{novel['id']}/world/categories",
        json={"name": "临时分类"},
    ).json()
    entry = _create_entry(client, novel["id"], category["id"], name="临时设定")

    blocked = client.delete(
        f"/api/novels/{novel['id']}/world/categories/{category['id']}"
    )
    assert blocked.status_code == 400
    assert "仍有 1 个设定条目" in blocked.json()["detail"]
    assert "迁移" in blocked.json()["detail"]

    moved = client.put(
        f"/api/novels/{novel['id']}/world/entries/{entry['id']}",
        json={"category_id": _category_id(client, novel["id"], "其他")},
    )
    assert moved.status_code == 200
    deleted = client.delete(
        f"/api/novels/{novel['id']}/world/categories/{category['id']}"
    )
    assert deleted.status_code == 200


def test_parent_reference_and_delete_restriction(client):
    novel = _create_novel(client)
    category_id = _category_id(client, novel["id"])
    parent = _create_entry(client, novel["id"], category_id, name="东部区域")
    child = _create_entry(
        client, novel["id"], category_id, name="青木府城", parent_id=parent["id"]
    )
    assert child["parent_id"] == parent["id"]
    assert child["parent_name"] == "东部区域"

    children = client.get(
        f"/api/novels/{novel['id']}/world/entries", params={"parent_id": parent["id"]}
    ).json()
    assert len(children) == 1 and children[0]["id"] == child["id"]

    blocked = client.delete(f"/api/novels/{novel['id']}/world/entries/{parent['id']}")
    assert blocked.status_code == 400
    assert "子设定" in blocked.json()["detail"]

    detached = client.put(
        f"/api/novels/{novel['id']}/world/entries/{child['id']}",
        json={"parent_id": None},
    )
    assert detached.status_code == 200
    assert detached.json()["parent_id"] is None
    assert client.delete(
        f"/api/novels/{novel['id']}/world/entries/{parent['id']}"
    ).status_code == 200


def test_cycle_parent_forbidden(client):
    novel = _create_novel(client)
    category_id = _category_id(client, novel["id"])
    first = _create_entry(client, novel["id"], category_id, name="条目A")
    second = _create_entry(client, novel["id"], category_id, name="条目B")

    set_parent = client.put(
        f"/api/novels/{novel['id']}/world/entries/{first['id']}",
        json={"parent_id": second["id"]},
    )
    assert set_parent.status_code == 200

    cycle = client.put(
        f"/api/novels/{novel['id']}/world/entries/{second['id']}",
        json={"parent_id": first["id"]},
    )
    assert cycle.status_code == 400
    assert "循环" in cycle.json()["detail"]

    self_parent = client.put(
        f"/api/novels/{novel['id']}/world/entries/{first['id']}",
        json={"parent_id": first["id"]},
    )
    assert self_parent.status_code == 400
    assert "自己的父级" in self_parent.json()["detail"]


def test_cross_novel_isolation(client):
    novel_a = _create_novel(client, "小说A")
    novel_b = _create_novel(client, "小说B")
    category_a = _category_id(client, novel_a["id"])
    entry_a = _create_entry(client, novel_a["id"], category_a, name="A的设定")

    assert client.get(f"/api/novels/{novel_b['id']}/world/entries/{entry_a['id']}").status_code == 404
    assert client.put(
        f"/api/novels/{novel_b['id']}/world/entries/{entry_a['id']}", json={"name": "越权修改"}
    ).status_code == 404
    assert client.delete(
        f"/api/novels/{novel_b['id']}/world/entries/{entry_a['id']}"
    ).status_code == 404

    cross_create = client.post(
        f"/api/novels/{novel_b['id']}/world/entries",
        json={"name": "跨小说分类", "category_id": category_a},
    )
    assert cross_create.status_code == 404

    category_b_id = _category_id(client, novel_b["id"])
    assert client.get(
        f"/api/novels/{novel_a['id']}/world/entries", params={"category_id": category_b_id}
    ).status_code == 404

    list_b = client.get(f"/api/novels/{novel_b['id']}/world/entries").json()
    assert list_b == []

    cross_parent = client.post(
        f"/api/novels/{novel_b['id']}/world/entries",
        json={"name": "跨小说父级", "category_id": category_b_id, "parent_id": entry_a["id"]},
    )
    assert cross_parent.status_code == 404


def test_nonexistent_novel_returns_404(client):
    fake = "not-exist-novel"
    assert client.get(f"/api/novels/{fake}/world/entries").status_code == 404
    assert client.get(f"/api/novels/{fake}/world/categories").status_code == 404
    assert client.get(f"/api/novels/{fake}/world/stats").status_code == 404
    assert client.post(
        f"/api/novels/{fake}/world/categories", json={"name": "分类"}
    ).status_code == 404
    assert client.post(
        f"/api/novels/{fake}/world/entries",
        json={"name": "设定", "category_id": "any"},
    ).status_code == 404


def test_delete_novel_cascades_world_data(client, settings):
    novel = _create_novel(client)
    category_id = _category_id(client, novel["id"])
    parent = _create_entry(client, novel["id"], category_id, name="父级")
    _create_entry(client, novel["id"], category_id, name="子级", parent_id=parent["id"])

    deleted = client.delete(f"/api/novels/{novel['id']}")
    assert deleted.status_code == 200

    assert client.get(f"/api/novels/{novel['id']}/world/entries").status_code == 404
    assert client.get(f"/api/novels/{novel['id']}/world/stats").status_code == 404

    with sqlite3.connect(settings.database_path) as conn:
        entries = conn.execute(
            "SELECT COUNT(*) FROM world_entries WHERE novel_id = ?", (novel["id"],)
        ).fetchone()[0]
        categories = conn.execute(
            "SELECT COUNT(*) FROM world_categories WHERE novel_id = ?", (novel["id"],)
        ).fetchone()[0]
    assert entries == 0
    assert categories == 0


def test_novel_detail_exposes_world_entry_count(client):
    novel = _create_novel(client)
    category_id = _category_id(client, novel["id"])
    _create_entry(client, novel["id"], category_id, name="设定一")
    detail = client.get(f"/api/novels/{novel['id']}").json()
    assert detail["stats"]["world_entry_count"] == 1
