"""P3.2.2 世界观关系管理接口测试。"""

import sqlite3
from itertools import count

_seq = count(1)


def _create_novel(client, title=None):
    title = title or f"关系测试小说{next(_seq)}"
    response = client.post("/api/novels", json={"title": title})
    assert response.status_code == 200, response.text
    return response.json()


def _category_id(client, novel_id, name="地理与区域"):
    response = client.get(f"/api/novels/{novel_id}/world/categories")
    assert response.status_code == 200, response.text
    for item in response.json():
        if item["name"] == name:
            return item["id"]
    raise AssertionError(f"未找到分类 {name}")


def _create_entry(client, novel_id, name, category_name="地理与区域", **extra):
    payload = {
        "name": name,
        "category_id": _category_id(client, novel_id, category_name),
    }
    payload.update(extra)
    response = client.post(f"/api/novels/{novel_id}/world/entries", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _create_relation(
    client,
    novel_id,
    source_id,
    target_id,
    relation_type="管辖",
    description="",
    expect=200,
):
    response = client.post(
        f"/api/novels/{novel_id}/world/relations",
        json={
            "source_entry_id": source_id,
            "target_entry_id": target_id,
            "relation_type": relation_type,
            "description": description,
        },
    )
    assert response.status_code == expect, response.text
    return response.json()


def _relations(client, novel_id, **params):
    response = client.get(f"/api/novels/{novel_id}/world/relations", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _entry_relations(client, novel_id, entry_id):
    response = client.get(
        f"/api/novels/{novel_id}/world/entries/{entry_id}/relations"
    )
    assert response.status_code == 200, response.text
    return response.json()


def _world(client, novel_id):
    """远东皇朝 / 青木府城 / 北明府城 / 北境城邦联盟 基础场景。"""
    empire = _create_entry(client, novel_id, "远东皇朝", "势力与组织")
    qingmu = _create_entry(client, novel_id, "青木府城", "地理与区域")
    beiming = _create_entry(client, novel_id, "北明府城", "地理与区域")
    alliance = _create_entry(client, novel_id, "北境城邦联盟", "势力与组织")
    return empire, qingmu, beiming, alliance


def test_create_relation_with_endpoint_summaries(client):
    novel = _create_novel(client)
    empire, qingmu, _, _ = _world(client, novel["id"])

    relation = _create_relation(
        client, novel["id"], empire["id"], qingmu["id"], "管辖", "远东皇朝管辖青木府城"
    )
    assert relation["source_entry_id"] == empire["id"]
    assert relation["target_entry_id"] == qingmu["id"]
    assert relation["relation_type"] == "管辖"
    assert relation["description"] == "远东皇朝管辖青木府城"
    assert relation["source"]["name"] == "远东皇朝"
    assert relation["source"]["category_name"] == "势力与组织"
    assert relation["target"]["name"] == "青木府城"
    assert relation["target"]["category_name"] == "地理与区域"
    assert relation["created_at"] and relation["updated_at"]


def test_list_relations_and_filters(client):
    novel = _create_novel(client)
    empire, qingmu, beiming, alliance = _world(client, novel["id"])

    first = _create_relation(
        client, novel["id"], empire["id"], qingmu["id"], "管辖", "皇朝直辖区"
    )
    second = _create_relation(
        client, novel["id"], empire["id"], beiming["id"], "管辖", "皇朝北部辖区"
    )
    third = _create_relation(
        client, novel["id"], alliance["id"], empire["id"], "敌对", "北境长期敌对"
    )

    all_relations = _relations(client, novel["id"])
    assert {item["id"] for item in all_relations} == {
        first["id"],
        second["id"],
        third["id"],
    }

    by_type = _relations(client, novel["id"], relation_type="管辖")
    assert {item["id"] for item in by_type} == {first["id"], second["id"]}

    by_source = _relations(client, novel["id"], source_entry_id=empire["id"])
    assert {item["id"] for item in by_source} == {first["id"], second["id"]}

    by_target = _relations(client, novel["id"], target_entry_id=qingmu["id"])
    assert [item["id"] for item in by_target] == [first["id"]]

    by_keyword = _relations(client, novel["id"], search="北部")
    assert [item["id"] for item in by_keyword] == [second["id"]]

    combined = _relations(
        client, novel["id"], relation_type="管辖", source_entry_id=empire["id"]
    )
    assert len(combined) == 2


def test_update_relation(client):
    novel = _create_novel(client)
    empire, qingmu, beiming, alliance = _world(client, novel["id"])
    relation = _create_relation(
        client, novel["id"], empire["id"], qingmu["id"], "管辖", "旧描述"
    )

    updated = client.put(
        f"/api/novels/{novel['id']}/world/relations/{relation['id']}",
        json={
            "target_entry_id": beiming["id"],
            "relation_type": "控制",
            "description": "改为控制北明府城",
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["source_entry_id"] == empire["id"]
    assert body["target_entry_id"] == beiming["id"]
    assert body["target"]["name"] == "北明府城"
    assert body["relation_type"] == "控制"
    assert body["description"] == "改为控制北明府城"
    assert body["updated_at"] >= relation["updated_at"]

    changed_source = client.put(
        f"/api/novels/{novel['id']}/world/relations/{relation['id']}",
        json={"source_entry_id": alliance["id"]},
    )
    assert changed_source.status_code == 200
    assert changed_source.json()["source"]["name"] == "北境城邦联盟"


def test_update_relation_validation(client):
    novel = _create_novel(client)
    empire, qingmu, beiming, _ = _world(client, novel["id"])
    relation = _create_relation(
        client, novel["id"], empire["id"], qingmu["id"], "管辖"
    )

    same = client.put(
        f"/api/novels/{novel['id']}/world/relations/{relation['id']}",
        json={"target_entry_id": empire["id"]},
    )
    assert same.status_code == 400
    assert "同一条设定" in same.json()["detail"]

    blank_type = client.put(
        f"/api/novels/{novel['id']}/world/relations/{relation['id']}",
        json={"relation_type": "   "},
    )
    assert blank_type.status_code == 422

    duplicate_source = client.put(
        f"/api/novels/{novel['id']}/world/relations/{relation['id']}",
        json={"target_entry_id": beiming["id"], "relation_type": "管辖"},
    )
    assert duplicate_source.status_code == 200

    other = _create_relation(
        client, novel["id"], empire["id"], qingmu["id"], "管辖"
    )
    duplicate = client.put(
        f"/api/novels/{novel['id']}/world/relations/{other['id']}",
        json={"target_entry_id": beiming["id"]},
    )
    assert duplicate.status_code == 400
    assert "已存在" in duplicate.json()["detail"]


def test_delete_relation_keeps_entries(client):
    novel = _create_novel(client)
    empire, qingmu, _, _ = _world(client, novel["id"])
    relation = _create_relation(
        client, novel["id"], empire["id"], qingmu["id"], "管辖"
    )

    deleted = client.delete(
        f"/api/novels/{novel['id']}/world/relations/{relation['id']}"
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    assert (
        client.get(
            f"/api/novels/{novel['id']}/world/relations/{relation['id']}"
        ).status_code
        == 404
    )
    assert client.get(
        f"/api/novels/{novel['id']}/world/entries/{empire['id']}"
    ).status_code == 200
    assert client.get(
        f"/api/novels/{novel['id']}/world/entries/{qingmu['id']}"
    ).status_code == 200


def test_entry_outgoing_and_incoming_relations(client):
    novel = _create_novel(client)
    empire, qingmu, _, alliance = _world(client, novel["id"])
    outgoing = _create_relation(
        client, novel["id"], empire["id"], qingmu["id"], "管辖", "正向"
    )
    incoming = _create_relation(
        client, novel["id"], alliance["id"], empire["id"], "敌对", "反向"
    )

    data = _entry_relations(client, novel["id"], empire["id"])
    assert data["entry_id"] == empire["id"]
    assert len(data["outgoing"]) == 1 and len(data["incoming"]) == 1
    assert data["outgoing"][0]["id"] == outgoing["id"]
    assert data["outgoing"][0]["direction"] == "outgoing"
    assert data["outgoing"][0]["target"]["name"] == "青木府城"
    assert data["incoming"][0]["id"] == incoming["id"]
    assert data["incoming"][0]["direction"] == "incoming"
    assert data["incoming"][0]["source"]["name"] == "北境城邦联盟"

    qingmu_data = _entry_relations(client, novel["id"], qingmu["id"])
    assert qingmu_data["outgoing"] == []
    assert [item["id"] for item in qingmu_data["incoming"]] == [outgoing["id"]]


def test_custom_relation_type(client):
    novel = _create_novel(client)
    empire, _, _, alliance = _world(client, novel["id"])
    relation = _create_relation(
        client, novel["id"], alliance["id"], empire["id"], "供奉", "自定义类型"
    )
    assert relation["relation_type"] == "供奉"
    assert _relations(client, novel["id"], relation_type="供奉")[0]["id"] == relation["id"]

    stats = client.get(f"/api/novels/{novel['id']}/world/stats").json()
    types = {item["relation_type"] for item in stats["relation_by_type"]}
    assert "供奉" in types


def test_same_source_and_target_rejected(client):
    novel = _create_novel(client)
    empire = _create_entry(client, novel["id"], "远东皇朝", "势力与组织")
    response = client.post(
        f"/api/novels/{novel['id']}/world/relations",
        json={
            "source_entry_id": empire["id"],
            "target_entry_id": empire["id"],
            "relation_type": "管辖",
        },
    )
    assert response.status_code == 400
    assert "同一条设定" in response.json()["detail"]


def test_duplicate_relation_rejected(client):
    novel = _create_novel(client)
    empire, qingmu, _, _ = _world(client, novel["id"])
    _create_relation(client, novel["id"], empire["id"], qingmu["id"], "管辖")

    duplicate = client.post(
        f"/api/novels/{novel['id']}/world/relations",
        json={
            "source_entry_id": empire["id"],
            "target_entry_id": qingmu["id"],
            "relation_type": "管辖",
        },
    )
    assert duplicate.status_code == 400
    assert "已存在" in duplicate.json()["detail"]

    # 同一条目对改用其他关系类型则允许
    allowed = _create_relation(
        client, novel["id"], empire["id"], qingmu["id"], "控制"
    )
    assert allowed["id"]


def test_reverse_relation_is_independent(client):
    novel = _create_novel(client)
    first = _create_entry(client, novel["id"], "甲城", "地理与区域")
    second = _create_entry(client, novel["id"], "乙城", "地理与区域")

    forward = _create_relation(
        client, novel["id"], first["id"], second["id"], "联盟", "甲与乙结盟"
    )
    backward = _create_relation(
        client, novel["id"], second["id"], first["id"], "联盟", "乙与甲结盟"
    )
    assert forward["id"] != backward["id"]
    assert forward["source_entry_id"] == backward["target_entry_id"]
    assert forward["target_entry_id"] == backward["source_entry_id"]

    data = _entry_relations(client, novel["id"], first["id"])
    assert len(data["outgoing"]) == 1
    assert len(data["incoming"]) == 1


def test_cross_novel_endpoints_rejected(client):
    novel_a = _create_novel(client, "小说A")
    novel_b = _create_novel(client, "小说B")
    entry_a = _create_entry(client, novel_a["id"], "A国", "势力与组织")
    entry_b = _create_entry(client, novel_b["id"], "B国", "势力与组织")

    cross_source = client.post(
        f"/api/novels/{novel_b['id']}/world/relations",
        json={
            "source_entry_id": entry_a["id"],
            "target_entry_id": entry_b["id"],
            "relation_type": "管辖",
        },
    )
    assert cross_source.status_code == 404
    assert "起点设定不存在" in cross_source.json()["detail"]

    cross_target = client.post(
        f"/api/novels/{novel_b['id']}/world/relations",
        json={
            "source_entry_id": entry_b["id"],
            "target_entry_id": entry_a["id"],
            "relation_type": "管辖",
        },
    )
    assert cross_target.status_code == 404
    assert "终点设定不存在" in cross_target.json()["detail"]

    missing = client.post(
        f"/api/novels/{novel_b['id']}/world/relations",
        json={
            "source_entry_id": "not-exist",
            "target_entry_id": entry_b["id"],
            "relation_type": "管辖",
        },
    )
    assert missing.status_code == 404


def test_tampered_url_cannot_access_other_novel_relation(client):
    novel_a = _create_novel(client, "小说A")
    novel_b = _create_novel(client, "小说B")
    entry_a = _create_entry(client, novel_a["id"], "A国", "势力与组织")
    entry_a2 = _create_entry(client, novel_a["id"], "A城", "地理与区域")
    relation = _create_relation(
        client, novel_a["id"], entry_a["id"], entry_a2["id"], "管辖"
    )

    assert (
        client.get(
            f"/api/novels/{novel_b['id']}/world/relations/{relation['id']}"
        ).status_code
        == 404
    )
    assert client.put(
        f"/api/novels/{novel_b['id']}/world/relations/{relation['id']}",
        json={"relation_type": "敌对"},
    ).status_code == 404
    assert client.delete(
        f"/api/novels/{novel_b['id']}/world/relations/{relation['id']}"
    ).status_code == 404

    assert _relations(client, novel_b["id"]) == []


def test_deleting_entry_cascades_relations(client, settings):
    novel = _create_novel(client)
    empire, qingmu, beiming, _ = _world(client, novel["id"])
    _create_relation(client, novel["id"], empire["id"], qingmu["id"], "管辖")
    _create_relation(client, novel["id"], qingmu["id"], beiming["id"], "贸易")

    assert client.delete(
        f"/api/novels/{novel['id']}/world/entries/{qingmu['id']}"
    ).status_code == 200

    remaining = _relations(client, novel["id"])
    assert remaining == []
    with sqlite3.connect(settings.database_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM world_relations WHERE novel_id = ?", (novel["id"],)
        ).fetchone()[0]
    assert count == 0


def test_deleting_novel_cascades_relations(client, settings):
    novel = _create_novel(client)
    empire, qingmu, _, _ = _world(client, novel["id"])
    _create_relation(client, novel["id"], empire["id"], qingmu["id"], "管辖")

    assert client.delete(f"/api/novels/{novel['id']}").status_code == 200
    assert client.get(f"/api/novels/{novel['id']}/world/relations").status_code == 404

    with sqlite3.connect(settings.database_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM world_relations WHERE novel_id = ?", (novel["id"],)
        ).fetchone()[0]
    assert count == 0


def test_relation_stats(client):
    novel = _create_novel(client)
    empire, qingmu, beiming, alliance = _world(client, novel["id"])
    _create_relation(client, novel["id"], empire["id"], qingmu["id"], "管辖")
    _create_relation(client, novel["id"], empire["id"], beiming["id"], "管辖")
    _create_relation(client, novel["id"], alliance["id"], empire["id"], "敌对")

    stats = client.get(f"/api/novels/{novel['id']}/world/stats").json()
    assert stats["total_relations"] == 3
    assert stats["relation_type_count"] == 2
    by_type = {item["relation_type"]: item["count"] for item in stats["relation_by_type"]}
    assert by_type == {"管辖": 2, "敌对": 1}
    assert stats["related_entry_count"] == 4
    assert stats["latest_updated_at"] is not None

    empty_novel = _create_novel(client, "空关系小说")
    empty_stats = client.get(f"/api/novels/{empty_novel['id']}/world/stats").json()
    assert empty_stats["total_relations"] == 0
    assert empty_stats["relation_type_count"] == 0
    assert empty_stats["relation_by_type"] == []
    assert empty_stats["related_entry_count"] == 0


def test_relation_validation_and_404(client):
    novel = _create_novel(client)
    empire, qingmu, _, _ = _world(client, novel["id"])

    blank_type = client.post(
        f"/api/novels/{novel['id']}/world/relations",
        json={
            "source_entry_id": empire["id"],
            "target_entry_id": qingmu["id"],
            "relation_type": "   ",
        },
    )
    assert blank_type.status_code == 422

    missing_novel = client.get("/api/novels/not-exist/world/relations")
    assert missing_novel.status_code == 404

    assert (
        client.get(
            f"/api/novels/{novel['id']}/world/entries/not-exist/relations"
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/novels/{novel['id']}/world/relations/not-exist"
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/novels/not-exist/world/relations",
            json={
                "source_entry_id": empire["id"],
                "target_entry_id": qingmu["id"],
                "relation_type": "管辖",
            },
        ).status_code
        == 404
    )


def test_relation_coexists_with_parent_hierarchy(client):
    """parent_id 与关系表互不替代：青木府城既有父级，也参与跨类关系。"""
    novel = _create_novel(client)
    east = _create_entry(client, novel["id"], "东部区域", "地理与区域")
    empire = _create_entry(client, novel["id"], "远东皇朝", "势力与组织")
    city = _create_entry(
        client, novel["id"], "青木府城", "地理与区域", parent_id=east["id"]
    )
    other_city = _create_entry(client, novel["id"], "白河城", "地理与区域")

    _create_relation(client, novel["id"], empire["id"], city["id"], "管辖")
    trade = _create_relation(
        client, novel["id"], city["id"], other_city["id"], "贸易", "沿河贸易"
    )

    assert city["parent_id"] == east["id"]
    data = _entry_relations(client, novel["id"], city["id"])
    assert data["incoming"][0]["relation_type"] == "管辖"
    assert data["outgoing"][0]["id"] == trade["id"]
