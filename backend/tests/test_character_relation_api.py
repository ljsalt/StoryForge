"""P3.4 人物关系接口测试。"""

import sqlite3


def _create_novel(client, title="人物关系测试"):
    r = client.post("/api/novels", json={"title": title})
    assert r.status_code == 200, r.text
    return r.json()


def _create_char(client, novel_id, name, **extra):
    payload = {"name": name}
    payload.update(extra)
    r = client.post(f"/api/novels/{novel_id}/characters", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _api_base(client, novel_id):
    return f"/api/novels/{novel_id}/character-relations"


def test_create_relation_generates_event(client):
    novel = _create_novel(client, "P3.4 创建")
    a = _create_char(client, novel["id"], "林远")
    b = _create_char(client, novel["id"], "顾长生")

    payload = {
        "source_character_id": a["id"],
        "target_character_id": b["id"],
        "relation_type": "师徒",
        "description": "顾长生收林远为徒",
        "strength": 60.0,
        "attributes": {"信任度": 60},
        "start_time": "修仙历 3021 年",
    }
    r = client.post(_api_base(client, novel["id"]), json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "active"
    assert data["source_name"] == "林远"
    assert data["target_name"] == "顾长生"
    assert data["strength"] == 60.0
    assert data["attributes"] == {"信任度": 60}
    rid = data["id"]

    # 查询历史事件
    events = client.get(f"/api/novels/{novel['id']}/character-relations/{rid}/events").json()
    assert len(events) == 1
    assert events[0]["event_type"] == "created"
    assert events[0]["new_data"]["relation_type"] == "师徒"


def test_ab_ba_are_independent(client):
    novel = _create_novel(client, "P3.4 双向独立")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    r1 = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "徒弟",
    })
    r2 = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": b["id"], "target_character_id": a["id"], "relation_type": "师父",
    })
    assert r1.status_code == 200
    assert r2.status_code == 200
    listing = client.get(_api_base(client, novel["id"])).json()
    assert len(listing) == 2
    types = {x["relation_type"] for x in listing}
    assert types == {"徒弟", "师父"}


def test_active_duplicate_rejected(client):
    novel = _create_novel(client, "P3.4 重复")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "师父",
    })
    dup = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "师父",
    })
    assert dup.status_code == 400


def test_ended_allows_recreate(client):
    novel = _create_novel(client, "P3.4 结束重开")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    created = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "师父",
    }).json()
    r1 = created["id"]

    client.post(f"/api/novels/{novel['id']}/character-relations/{r1}/end").json()

    # 已结束可以再新建一条同方向同类型的关系（是新 relation，不是恢复）
    created2 = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "师父",
    })
    assert created2.status_code == 200
    assert created2.json()["id"] != r1


def test_self_relation_rejected(client):
    novel = _create_novel(client, "P3.4 自己")
    a = _create_char(client, novel["id"], "A")
    r = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": a["id"], "relation_type": "自己",
    })
    assert r.status_code == 400


def test_cross_novel_rejected(client):
    n1 = _create_novel(client, "N1")
    n2 = _create_novel(client, "N2")
    a = _create_char(client, n1["id"], "A")
    b = _create_char(client, n2["id"], "B")
    r = client.post(_api_base(client, n1["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "认识",
    })
    assert r.status_code == 404


def test_update_writes_event_with_prev_new(client):
    novel = _create_novel(client, "P3.4 修改")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    created = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"],
        "relation_type": "陌生人", "description": "初遇", "strength": 10,
    }).json()
    rid = created["id"]

    updated = client.put(
        f"/api/novels/{novel['id']}/character-relations/{rid}",
        json={"relation_type": "师徒", "strength": 60},
    )
    assert updated.status_code == 200
    assert updated.json()["relation_type"] == "师徒"
    assert updated.json()["strength"] == 60.0

    events = client.get(f"/api/novels/{novel['id']}/character-relations/{rid}/events").json()
    assert [e["event_type"] for e in events] == ["created", "updated"]
    upd = events[1]
    assert upd["previous_data"]["relation_type"] == "陌生人"
    assert upd["previous_data"]["strength"] == 10
    assert upd["new_data"]["relation_type"] == "师徒"
    assert upd["new_data"]["strength"] == 60


def test_end_and_restore(client):
    novel = _create_novel(client, "P3.4 结束恢复")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    created = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"],
        "relation_type": "师徒",
    }).json()
    rid = created["id"]

    ended = client.post(f"/api/novels/{novel['id']}/character-relations/{rid}/end").json()
    assert ended["status"] == "ended"
    assert ended["end_time"] is not None

    restored = client.post(f"/api/novels/{novel['id']}/character-relations/{rid}/restore").json()
    assert restored["status"] == "active"
    assert restored["end_time"] is None

    events = client.get(f"/api/novels/{novel['id']}/character-relations/{rid}/events").json()
    assert [e["event_type"] for e in events] == ["created", "ended", "restored"]
    # restored 事件必须有 previous/new 快照
    assert events[2]["previous_data"]["status"] == "ended"
    assert events[2]["new_data"]["status"] == "active"


def test_ended_relation_still_returns_history(client):
    novel = _create_novel(client, "P3.4 历史保留")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    created = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "师徒",
    }).json()
    rid = created["id"]
    client.post(f"/api/novels/{novel['id']}/character-relations/{rid}/end")
    events = client.get(f"/api/novels/{novel['id']}/character-relations/{rid}/events").json()
    assert [e["event_type"] for e in events] == ["created", "ended"]


def test_event_order_stable(client):
    novel = _create_novel(client, "P3.4 顺序")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    created = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"],
        "relation_type": "陌生人",
    }).json()
    rid = created["id"]
    client.put(f"/api/novels/{novel['id']}/character-relations/{rid}", json={"relation_type": "朋友"})
    client.post(f"/api/novels/{novel['id']}/character-relations/{rid}/end")
    events = client.get(f"/api/novels/{novel['id']}/character-relations/{rid}/events").json()
    types = [e["event_type"] for e in events]
    assert types == ["created", "updated", "ended"]
    times = [e["created_at"] for e in events]
    assert times == sorted(times)  # 时间升序


def test_event_write_protected_no_api(client):
    """事件表只有 GET 列表接口；POST 到精确 events 路径返回 405，
    带子路径的写操作因根本无对应路由返回 404。"""
    novel = _create_novel(client, "P3.4 写保护")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    created = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "认识",
    }).json()
    rid = created["id"]
    events_url = f"/api/novels/{novel['id']}/character-relations/{rid}/events"
    # 对已注册精确路径的 POST 返回 405 Method Not Allowed
    assert client.post(events_url, json={"event_type": "foo"}).status_code == 405
    # 对未注册的子路径（事件详情写接口）返回 404
    assert client.put(events_url + "/xxx", json={"title": "bar"}).status_code == 404
    assert client.delete(events_url + "/xxx").status_code == 404


def test_tamper_relation_id_returns_404(client):
    n1 = _create_novel(client, "N1")
    n2 = _create_novel(client, "N2")
    a = _create_char(client, n1["id"], "A")
    b = _create_char(client, n1["id"], "B")
    created = client.post(_api_base(client, n1["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "认识",
    }).json()
    rid = created["id"]

    # 用 n2 的 novel_id 篡改 relation_id
    assert client.get(f"/api/novels/{n2['id']}/character-relations/{rid}").status_code == 404
    assert client.put(
        f"/api/novels/{n2['id']}/character-relations/{rid}",
        json={"relation_type": "X"},
    ).status_code == 404
    assert client.post(
        f"/api/novels/{n2['id']}/character-relations/{rid}/end"
    ).status_code == 404
    assert client.get(
        f"/api/novels/{n2['id']}/character-relations/{rid}/events"
    ).status_code == 404


def test_tamper_character_id_in_relation_access_returns_404(client):
    n1 = _create_novel(client, "N1")
    n2 = _create_novel(client, "N2")
    a = _create_char(client, n1["id"], "A")
    b = _create_char(client, n1["id"], "B")
    created = client.post(_api_base(client, n1["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "认识",
    }).json()
    rid = created["id"]

    # 用 n2 的 novel_id 访问 n1 里的人物关系
    assert client.get(
        f"/api/novels/{n2['id']}/characters/{a['id']}/relations"
    ).status_code == 404


def test_delete_character_cascades_relations_and_events(client):
    novel = _create_novel(client, "P3.4 删人物级联")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    c = _create_char(client, novel["id"], "C")
    r1 = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "师徒",
    }).json()["id"]
    client.post(_api_base(client, novel["id"]), json={
        "source_character_id": b["id"], "target_character_id": c["id"], "relation_type": "朋友",
    }).json()
    # 给 r1 多一条事件
    client.put(
        f"/api/novels/{novel['id']}/character-relations/{r1}",
        json={"description": "改下描述"},
    )
    # 记录事件数量
    before_events = client.get(
        f"/api/novels/{novel['id']}/character-relations/{r1}/events"
    ).json()
    assert len(before_events) == 2

    client.delete(f"/api/novels/{novel['id']}/characters/{b['id']}")

    # 直查 sqlite 验证级联
    from app.core.config import get_settings
    conn = sqlite3.connect(get_settings().database_path)
    conn.execute("PRAGMA foreign_keys = ON")
    rel_count = conn.execute(
        "SELECT COUNT(*) FROM character_relations WHERE novel_id = ?", (novel["id"],)
    ).fetchone()[0]
    ev_count = conn.execute(
        "SELECT COUNT(*) FROM character_relation_events WHERE novel_id = ?", (novel["id"],)
    ).fetchone()[0]
    conn.close()
    # b 是 source 和 target 两条关系，都应该被删（通过 OR source=? OR target=?）
    assert rel_count == 0, f"relation_count={rel_count}"
    assert ev_count == 0, f"event_count={ev_count}"


def test_delete_novel_cascades_all(client):
    novel = _create_novel(client, "P3.4 删小说级联")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "认识",
    })
    # 小说外的另一 novel，确保它不受影响
    n_other = _create_novel(client, "Other")

    client.delete(f"/api/novels/{novel['id']}")

    from app.core.config import get_settings
    conn = sqlite3.connect(get_settings().database_path)
    conn.execute("PRAGMA foreign_keys = ON")
    assert conn.execute("SELECT COUNT(*) FROM character_relations WHERE novel_id = ?", (novel["id"],)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM character_relation_events WHERE novel_id = ?", (novel["id"],)).fetchone()[0] == 0
    # 其他小说仍然保留
    assert conn.execute("SELECT COUNT(*) FROM novels WHERE id = ?", (n_other["id"],)).fetchone()[0] == 1
    conn.close()


# ---------------------------------------------------------------------------
# 数据库层约束：复合外键（同小说一致性）+ 活跃关系部分唯一索引（并发兜底）
# ---------------------------------------------------------------------------


def test_db_composite_fk_blocks_cross_novel(client):
    """直接绕过 API 写库时，数据库复合外键必须拦截跨小说关系。"""
    from app.core.config import get_settings

    novel_a = _create_novel(client, "复合外键A")
    novel_b = _create_novel(client, "复合外键B")
    a1 = _create_char(client, novel_a["id"], "甲")
    b1 = _create_char(client, novel_b["id"], "乙")

    conn = sqlite3.connect(get_settings().database_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        # source 属于小说 A，target 属于小说 B，关系挂在小说 A 下 → 必须被拒绝
        conn.execute(
            "INSERT INTO character_relations"
            " (id, novel_id, source_character_id, target_character_id,"
            "  relation_type, status, created_at, updated_at)"
            " VALUES ('fk_bad1', ?, ?, ?, '认识', 'active', '2026-01-01', '2026-01-01')",
            (novel_a["id"], a1["id"], b1["id"]),
        )
        raise AssertionError("跨小说关系应被数据库复合外键拒绝")
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.rollback()
        conn.close()


def test_db_partial_unique_index_blocks_duplicate_active(client):
    """直接绕过 API 写库时，同方向同类型 active 关系被部分唯一索引拦截；ended 不受限。"""
    from app.core.config import get_settings

    novel = _create_novel(client, "部分唯一索引")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    created = client.post(
        _api_base(client, novel["id"]),
        json={"source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "盟友"},
    ).json()

    conn = sqlite3.connect(get_settings().database_path)
    conn.execute("PRAGMA foreign_keys = ON")
    insert_sql = (
        "INSERT INTO character_relations"
        " (id, novel_id, source_character_id, target_character_id,"
        "  relation_type, status, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, '2026-01-01', '2026-01-01')"
    )
    try:
        # 同方向同类型 active → 数据库拒绝
        conn.execute(insert_sql, ("uq_dup1", novel["id"], a["id"], b["id"], "盟友", "active"))
        raise AssertionError("重复有效关系应被部分唯一索引拒绝")
    except sqlite3.IntegrityError:
        pass
    # 同方向同类型 ended → 允许（历史关系可复开，不占用唯一约束）
    conn.execute(insert_sql, ("uq_dup2", novel["id"], a["id"], b["id"], "盟友", "ended"))
    conn.rollback()
    conn.close()

    # API 侧读取不受影响
    assert client.get(
        f"/api/novels/{novel['id']}/character-relations/{created['id']}"
    ).status_code == 200


def test_duplicate_active_race_returns_400(client, monkeypatch):
    """模拟并发绕过服务层预检：预检被跳过后，数据库唯一索引兜底并翻译为 400 而非 500。"""
    from app.services import character_relation_service

    monkeypatch.setattr(
        character_relation_service, "_check_active_duplicate", lambda *a, **k: None
    )
    novel = _create_novel(client, "并发兜底")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    payload = {
        "source_character_id": a["id"],
        "target_character_id": b["id"],
        "relation_type": "盟友",
    }
    assert client.post(_api_base(client, novel["id"]), json=payload).status_code == 200

    r2 = client.post(_api_base(client, novel["id"]), json=payload)
    assert r2.status_code == 400, r2.text
    assert "有效关系已存在" in r2.json()["detail"]


def test_relation_table_migration_rebuilds_with_composite_fk(monkeypatch, tmp_path):
    """老库（单列外键）升级：重建表后数据与事件完整保留，并获得复合外键与部分唯一索引。"""
    import app.database.db as db_mod

    old_db = tmp_path / "legacy.db"
    conn = sqlite3.connect(old_db)
    # 模拟 P3.4 初版（单列外键）老库：novels/characters 与现行结构一致，
    # 仅 character_relations 使用旧的单列外键定义
    conn.executescript(
        """
        CREATE TABLE novels (
            id                TEXT PRIMARY KEY,
            title             TEXT NOT NULL,
            subtitle          TEXT NOT NULL DEFAULT '',
            description       TEXT NOT NULL DEFAULT '',
            genre             TEXT NOT NULL DEFAULT '',
            tags              TEXT NOT NULL DEFAULT '[]',
            status            TEXT NOT NULL DEFAULT 'planning'
                              CHECK (status IN ('planning', 'writing', 'paused', 'completed')),
            cover_color       TEXT NOT NULL DEFAULT '',
            target_word_count INTEGER NOT NULL DEFAULT 100000
                              CHECK (target_word_count > 0),
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );
        CREATE TABLE characters (
            id            TEXT PRIMARY KEY,
            novel_id      TEXT NOT NULL REFERENCES novels (id) ON DELETE CASCADE,
            name          TEXT NOT NULL,
            aliases       TEXT NOT NULL DEFAULT '[]',
            gender        TEXT NOT NULL DEFAULT '',
            age           TEXT NOT NULL DEFAULT '',
            race          TEXT NOT NULL DEFAULT '',
            identity      TEXT NOT NULL DEFAULT '',
            role          TEXT NOT NULL DEFAULT '',
            appearance    TEXT NOT NULL DEFAULT '',
            personality   TEXT NOT NULL DEFAULT '',
            background    TEXT NOT NULL DEFAULT '',
            abilities     TEXT NOT NULL DEFAULT '',
            cultivation   TEXT NOT NULL DEFAULT '',
            affiliation   TEXT NOT NULL DEFAULT '',
            tags          TEXT NOT NULL DEFAULT '[]',
            attributes    TEXT NOT NULL DEFAULT '{}',
            avatar_color  TEXT NOT NULL DEFAULT '',
            sort_order    INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL
        );
        CREATE TABLE character_relations (
            id TEXT PRIMARY KEY,
            novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
            source_character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
            target_character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
            relation_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            description TEXT NOT NULL DEFAULT '',
            strength REAL,
            attributes TEXT NOT NULL DEFAULT '{}',
            start_time TEXT,
            end_time TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE character_relation_events (
            id TEXT PRIMARY KEY,
            novel_id TEXT NOT NULL,
            relation_id TEXT NOT NULL REFERENCES character_relations(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            previous_data TEXT NOT NULL DEFAULT '{}',
            new_data TEXT NOT NULL DEFAULT '{}',
            story_time TEXT,
            chapter_id TEXT,
            created_at TEXT NOT NULL
        );
        INSERT INTO novels
            (id, title, created_at, updated_at)
        VALUES ('n1', '老小说', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00');
        INSERT INTO characters
            (id, novel_id, name, created_at, updated_at)
        VALUES ('c1', 'n1', '甲', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00');
        INSERT INTO characters
            (id, novel_id, name, created_at, updated_at)
        VALUES ('c2', 'n1', '乙', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00');
        INSERT INTO character_relations
            (id, novel_id, source_character_id, target_character_id,
             relation_type, status, created_at, updated_at)
        VALUES ('r1', 'n1', 'c1', 'c2', '师徒', 'active',
                '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00');
        INSERT INTO character_relation_events
            (id, novel_id, relation_id, event_type, title, description,
             previous_data, new_data, created_at)
        VALUES ('e1', 'n1', 'r1', 'created', '建立师徒关系', '', '{}', '{}',
                '2026-01-01T00:00:00+00:00');
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db_mod, "db_path", lambda: old_db)
    db_mod.init_database()

    conn = sqlite3.connect(old_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # 关系数据完整保留
    rel = conn.execute("SELECT * FROM character_relations WHERE id = 'r1'").fetchone()
    assert rel is not None and rel["status"] == "active"
    # 历史事件完整保留（未被重建过程清空）
    events = conn.execute(
        "SELECT * FROM character_relation_events WHERE relation_id = 'r1'"
    ).fetchall()
    assert len(events) == 1 and events[0]["event_type"] == "created"
    # 复合外键已生效
    fks = conn.execute("PRAGMA foreign_key_list(character_relations)").fetchall()
    assert any(fk["table"] == "characters" and fk["from"] == "novel_id" for fk in fks)
    # 部分唯一索引已创建
    indexes = [r[1] for r in conn.execute("PRAGMA index_list(character_relations)").fetchall()]
    assert "uq_char_relations_active" in indexes
    # 重建后的表在数据库层面拦截跨小说关系
    conn.execute(
        "INSERT INTO novels (id, title, created_at, updated_at)"
        " VALUES ('OTHER_NOVEL', '另一本小说', '2026-01-01', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO characters"
        " (id, novel_id, name, created_at, updated_at)"
        " VALUES ('c3', 'OTHER_NOVEL', '丙', '2026-01-01', '2026-01-01')"
    )
    try:
        conn.execute(
            "INSERT INTO character_relations"
            " (id, novel_id, source_character_id, target_character_id,"
            "  relation_type, status, created_at, updated_at)"
            " VALUES ('r_bad', 'n1', 'c1', 'c3', '师徒', 'active', '2026-01-01', '2026-01-01')"
        )
        raise AssertionError("重建后的表应拒绝跨小说关系")
    except sqlite3.IntegrityError:
        pass
    # sequence 迁移也已补齐
    cols = [r[1] for r in conn.execute("PRAGMA table_info(character_relation_events)").fetchall()]
    assert "sequence" in cols
    conn.rollback()
    conn.close()


def test_transaction_rollback_on_failure(client):
    """创建后再做一个本应失败的更新（改 type 后与另一条 active 冲突），
    验证失败时 relation 和 event 都没出现脏数据。"""
    novel = _create_novel(client, "P3.4 事务")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    c = _create_char(client, novel["id"], "C")
    client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "师徒",
    })
    other = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "朋友",
    }).json()["id"]

    # 尝试把 other 改成 "师徒"——同方向同类型 active 已存在，应该 400
    bad = client.put(
        f"/api/novels/{novel['id']}/character-relations/{other}",
        json={"relation_type": "师徒"},
    )
    assert bad.status_code == 400

    # other 应该还保持 "朋友"
    got = client.get(f"/api/novels/{novel['id']}/character-relations/{other}").json()
    assert got["relation_type"] == "朋友"

    # other 的事件应该仍然只有 created（那条失败的 update event 不应写进去）
    events = client.get(
        f"/api/novels/{novel['id']}/character-relations/{other}/events"
    ).json()
    assert [e["event_type"] for e in events] == ["created"]


def test_bidirectional_creates_two_independent(client):
    novel = _create_novel(client, "P3.4 双向")
    a = _create_char(client, novel["id"], "林远")
    b = _create_char(client, novel["id"], "顾长生")

    r = client.post(
        f"/api/novels/{novel['id']}/character-relations/bidirectional",
        json={
            "source_character_id": a["id"],
            "target_character_id": b["id"],
            "relation_type": "师徒",
            "description": "双向快捷",
        },
    )
    assert r.status_code == 200
    pair = r.json()
    first, second = pair[0], pair[1]
    assert first["source_name"] == "林远" and first["target_name"] == "顾长生"
    assert second["source_name"] == "顾长生" and second["target_name"] == "林远"
    assert first["id"] != second["id"]
    listing = client.get(_api_base(client, novel["id"])).json()
    assert len(listing) == 2

    # 每条都有自己的 created event
    e1 = client.get(
        f"/api/novels/{novel['id']}/character-relations/{first['id']}/events"
    ).json()
    e2 = client.get(
        f"/api/novels/{novel['id']}/character-relations/{second['id']}/events"
    ).json()
    assert [x["event_type"] for x in e1] == ["created"]
    assert [x["event_type"] for x in e2] == ["created"]


def test_restore_does_not_overwrite_history(client):
    novel = _create_novel(client, "P3.4 恢复不覆盖历史")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    rid = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "师徒",
    }).json()["id"]
    client.post(f"/api/novels/{novel['id']}/character-relations/{rid}/end")
    client.post(f"/api/novels/{novel['id']}/character-relations/{rid}/restore")
    client.post(f"/api/novels/{novel['id']}/character-relations/{rid}/end")
    events = client.get(
        f"/api/novels/{novel['id']}/character-relations/{rid}/events"
    ).json()
    types = [e["event_type"] for e in events]
    assert types == ["created", "ended", "restored", "ended"]


def test_listing_with_filters(client):
    novel = _create_novel(client, "P3.4 列表筛选")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    c = _create_char(client, novel["id"], "C")
    client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "师徒",
    })
    client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": c["id"], "relation_type": "朋友",
    })
    # 结束一条
    rid = client.post(_api_base(client, novel["id"]), json={
        "source_character_id": b["id"], "target_character_id": c["id"], "relation_type": "认识",
    }).json()["id"]
    client.post(f"/api/novels/{novel['id']}/character-relations/{rid}/end")

    all_r = client.get(_api_base(client, novel["id"])).json()
    assert len(all_r) == 3

    by_type = client.get(_api_base(client, novel["id"]), params={"relation_type": "师徒"}).json()
    assert len(by_type) == 1

    only_active = client.get(_api_base(client, novel["id"]), params={"only_active": "true"}).json()
    assert len(only_active) == 2
    assert all(x["status"] == "active" for x in only_active)

    by_source = client.get(
        _api_base(client, novel["id"]), params={"source_character_id": a["id"]}
    ).json()
    assert len(by_source) == 2


def test_character_relations_endpoints(client):
    novel = _create_novel(client, "P3.4 人物关系聚合")
    a = _create_char(client, novel["id"], "A")
    b = _create_char(client, novel["id"], "B")
    c = _create_char(client, novel["id"], "C")

    # A→B (outgoing), C→A (incoming), A→B 另一个方向（不，A→C outgoing 替代）
    client.post(_api_base(client, novel["id"]), json={
        "source_character_id": a["id"], "target_character_id": b["id"], "relation_type": "师父",
    })
    client.post(_api_base(client, novel["id"]), json={
        "source_character_id": c["id"], "target_character_id": a["id"], "relation_type": "徒弟",
    })

    r = client.get(f"/api/novels/{novel['id']}/characters/{a['id']}/relations").json()
    assert r["character_id"] == a["id"]
    assert len(r["outgoing"]) == 1 and r["outgoing"][0]["direction"] == "outgoing"
    assert len(r["incoming"]) == 1 and r["incoming"][0]["direction"] == "incoming"

    # 跨小说人物访问 404
    n2 = _create_novel(client, "N2")
    assert client.get(
        f"/api/novels/{n2['id']}/characters/{a['id']}/relations"
    ).status_code == 404
