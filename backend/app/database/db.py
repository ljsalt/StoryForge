"""SQLite 基础设施。

- 首次启动创建数据库与表结构，之后仅做幂等检查（CREATE ... IF NOT EXISTS）。
- 不会删除、重建或覆盖已有数据。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..core.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS providers (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    provider_type     TEXT NOT NULL
                      CHECK (provider_type IN ('deepseek', 'openai_compatible', 'custom')),
    base_url          TEXT NOT NULL,
    api_key_encrypted TEXT,
    api_key_hint      TEXT NOT NULL DEFAULT '',
    enabled           INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_providers_name ON providers (name);

CREATE TABLE IF NOT EXISTS models (
    id          TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL REFERENCES providers (id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    model_id    TEXT NOT NULL,
    remark      TEXT NOT NULL DEFAULT '',
    enabled     INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (provider_id, model_id)
);

CREATE INDEX IF NOT EXISTS idx_models_provider ON models (provider_id);

CREATE TABLE IF NOT EXISTS task_model_settings (
    task       TEXT PRIMARY KEY,
    model_id   TEXT REFERENCES models (id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL
);

-- 小说项目：所有后续业务表（章节、人物、世界观、剧情记忆等）
-- 都必须以 novel_id 外键关联，并声明 ON DELETE CASCADE。
CREATE TABLE IF NOT EXISTS novels (
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

CREATE INDEX IF NOT EXISTS idx_novels_updated ON novels (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_novels_status ON novels (status);

-- 应用级键值配置（当前用于保存默认小说 default_novel_id）
CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL
);

-- 世界观分类：每部小说独立的分类体系，用户可自定义
CREATE TABLE IF NOT EXISTS world_categories (
    id          TEXT PRIMARY KEY,
    novel_id    TEXT NOT NULL REFERENCES novels (id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (novel_id, name)
);

CREATE INDEX IF NOT EXISTS idx_world_categories_novel
    ON world_categories (novel_id, sort_order);

-- 世界观条目：结构化属性 + 自然语言描述
-- 分类被条目引用时禁止删除（ON DELETE RESTRICT），由服务层给出明确提示
-- 父级条目同样采用 RESTRICT，存在子条目时不允许删除父级
CREATE TABLE IF NOT EXISTS world_entries (
    id          TEXT PRIMARY KEY,
    novel_id    TEXT NOT NULL REFERENCES novels (id) ON DELETE CASCADE,
    category_id TEXT NOT NULL REFERENCES world_categories (id) ON DELETE RESTRICT,
    name        TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '[]',
    attributes  TEXT NOT NULL DEFAULT '{}',
    parent_id   TEXT REFERENCES world_entries (id) ON DELETE RESTRICT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_world_entries_novel
    ON world_entries (novel_id, category_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_world_entries_parent
    ON world_entries (novel_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_world_entries_updated
    ON world_entries (novel_id, updated_at DESC);

-- 世界观关系：条目之间的有向关联，与 parent_id 的树形层级相互独立
-- 起点与终点必须属于同一部小说（由服务层校验），删除任一端点条目时关系级联清理
CREATE TABLE IF NOT EXISTS world_relations (
    id              TEXT PRIMARY KEY,
    novel_id        TEXT NOT NULL REFERENCES novels (id) ON DELETE CASCADE,
    source_entry_id TEXT NOT NULL REFERENCES world_entries (id) ON DELETE CASCADE,
    target_entry_id TEXT NOT NULL REFERENCES world_entries (id) ON DELETE CASCADE,
    relation_type   TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE (novel_id, source_entry_id, target_entry_id, relation_type),
    CHECK (source_entry_id <> target_entry_id)
);

CREATE INDEX IF NOT EXISTS idx_world_relations_source
    ON world_relations (novel_id, source_entry_id);
CREATE INDEX IF NOT EXISTS idx_world_relations_target
    ON world_relations (novel_id, target_entry_id);
CREATE INDEX IF NOT EXISTS idx_world_relations_type
    ON world_relations (novel_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_world_relations_created
    ON world_relations (novel_id, created_at DESC);

-- 人物档案：相对稳定的身份、外貌、性格、背景、能力
-- 同一小说允许多个同名人物，不设 UNIQUE 约束
CREATE TABLE IF NOT EXISTS characters (
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

CREATE INDEX IF NOT EXISTS idx_characters_novel
    ON characters (novel_id, sort_order, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_characters_name
    ON characters (novel_id, name);
CREATE INDEX IF NOT EXISTS idx_characters_role
    ON characters (novel_id, role);
CREATE INDEX IF NOT EXISTS idx_characters_updated
    ON characters (novel_id, updated_at DESC);

-- 复合唯一键：供人物关系的复合外键引用，从数据库层面保证
-- 关系两端人物与关系本身同属一本小说（防止未来 AI 自动写入跨小说脏数据）
CREATE UNIQUE INDEX IF NOT EXISTS idx_characters_id_novel
    ON characters (id, novel_id);

-- 人物当前状态：仅保留当前快照（剧情历史留给后续事件系统）
-- 一个人物只有一条当前状态记录，人物创建时事务内自动初始化
CREATE TABLE IF NOT EXISTS character_states (
    id                  TEXT PRIMARY KEY,
    character_id        TEXT NOT NULL UNIQUE REFERENCES characters (id) ON DELETE CASCADE,
    life_status         TEXT NOT NULL DEFAULT 'alive',
    current_location    TEXT NOT NULL DEFAULT '',
    current_faction     TEXT NOT NULL DEFAULT '',
    current_cultivation TEXT NOT NULL DEFAULT '',
    health_status       TEXT NOT NULL DEFAULT '',
    emotional_state     TEXT NOT NULL DEFAULT '',
    current_goal        TEXT NOT NULL DEFAULT '',
    current_status      TEXT NOT NULL DEFAULT '',
    attributes          TEXT NOT NULL DEFAULT '{}',
    updated_at          TEXT NOT NULL
);

-- 人物秘密：相对独立的秘密信息，可有多条
CREATE TABLE IF NOT EXISTS character_secrets (
    id              TEXT PRIMARY KEY,
    character_id    TEXT NOT NULL REFERENCES characters (id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    secrecy_level   TEXT NOT NULL DEFAULT 'restricted',
    reveal_status   TEXT NOT NULL DEFAULT 'unrevealed',
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_character_secrets_character
    ON character_secrets (character_id, updated_at DESC);

-- 人物当前关系：有向关系，允许 A→B 与 B→A 独立存在；
-- active 状态下同小说+同方向+同类型不重复（服务层预检 + 部分唯一索引兜底）；
-- 关系变化采用软终止（status='ended' + end_time 非空），历史单独保留
-- 复合外键 (source/target_character_id, novel_id) → characters(id, novel_id)
-- 在数据库层面强制关系两端人物与关系本身属于同一本小说
CREATE TABLE IF NOT EXISTS character_relations (
    id                   TEXT PRIMARY KEY,
    novel_id             TEXT NOT NULL REFERENCES novels (id) ON DELETE CASCADE,
    source_character_id  TEXT NOT NULL,
    target_character_id  TEXT NOT NULL,
    relation_type        TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'active',
    description          TEXT NOT NULL DEFAULT '',
    strength             REAL,
    attributes           TEXT NOT NULL DEFAULT '{}',
    start_time           TEXT,
    end_time             TEXT,
    sort_order           INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    CHECK (source_character_id <> target_character_id),
    CHECK (status IN ('active', 'ended')),
    FOREIGN KEY (source_character_id, novel_id)
        REFERENCES characters (id, novel_id) ON DELETE CASCADE,
    FOREIGN KEY (target_character_id, novel_id)
        REFERENCES characters (id, novel_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_char_relations_source
    ON character_relations (novel_id, source_character_id);
CREATE INDEX IF NOT EXISTS idx_char_relations_target
    ON character_relations (novel_id, target_character_id);
CREATE INDEX IF NOT EXISTS idx_char_relations_status
    ON character_relations (novel_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_char_relations_type
    ON character_relations (novel_id, relation_type);

-- 人物关系历史事件：每次关系写操作同一事务内自动写入
-- event_type ∈ created / updated / ended / restored
-- previous_data / new_data 存前后关系快照（JSON）
-- sequence 保证同一 relation 内事件按严格时间序排序（秒级时间戳相同也能稳定）
-- 此表只提供查询接口，原则上不允许普通业务写/删
CREATE TABLE IF NOT EXISTS character_relation_events (
    id             TEXT PRIMARY KEY,
    novel_id       TEXT NOT NULL REFERENCES novels (id) ON DELETE CASCADE,
    relation_id    TEXT NOT NULL REFERENCES character_relations (id) ON DELETE CASCADE,
    event_type     TEXT NOT NULL,
    title          TEXT NOT NULL DEFAULT '',
    description    TEXT NOT NULL DEFAULT '',
    previous_data  TEXT NOT NULL DEFAULT '{}',
    new_data       TEXT NOT NULL DEFAULT '{}',
    story_time     TEXT,
    chapter_id     TEXT,
    sequence       INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);

-- 注意：引用 sequence 列的事件表索引不在 SCHEMA 中创建，
-- 由 init_database 在 sequence 迁移完成后再建（见 CHAR_REL_EVENT_INDEXES_SQL）。
"""

# 事件表索引：引用 sequence 列，必须在 sequence 列迁移完成后创建，
# 否则老库（无 sequence 列）执行 SCHEMA 时会报 no such column
CHAR_REL_EVENT_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_char_rel_events_relation
    ON character_relation_events (relation_id, sequence, created_at);
CREATE INDEX IF NOT EXISTS idx_char_rel_events_novel
    ON character_relation_events (novel_id, created_at DESC);
"""

# 任务标识：四种创作任务 + 全局默认模型
TASK_KEYS = ("planner", "writer", "editor", "assistant")
DEFAULT_TASK_KEY = "default"

# 小说创作状态
NOVEL_STATUSES = ("planning", "writing", "paused", "completed")
# 默认小说在 app_settings 中的键名
DEFAULT_NOVEL_KEY = "default_novel_id"

# 新小说创建时初始化的通用世界观分类（仅作模板，用户可增删改）
DEFAULT_WORLD_CATEGORIES = (
    "地理与区域",
    "势力与组织",
    "世界规则",
    "力量体系",
    "历史与背景",
    "文化与社会",
    "其他",
)

# 关系类型的建议默认值（仅前端下拉提示，数据库不限制枚举，允许自定义）
DEFAULT_RELATION_TYPES = (
    "属于",
    "管辖",
    "位于",
    "控制",
    "联盟",
    "敌对",
    "贸易",
    "师承",
    "起源于",
    "依赖",
    "克制",
    "其他",
)

# 人物定位建议值（仅前端下拉提示，数据库不限制枚举）
DEFAULT_CHARACTER_ROLES = (
    "主角",
    "重要配角",
    "普通配角",
    "反派",
    "导师",
    "对手",
    "路人",
    "其他",
)

# 人物生死状态（life_status）建议值
DEFAULT_LIFE_STATUSES = ("alive", "dead", "unknown")

# 秘密保密等级（secrecy_level）建议值
DEFAULT_SECRECY_LEVELS = ("public", "restricted", "secret")

# 秘密公开状态（reveal_status）建议值
DEFAULT_REVEAL_STATUSES = ("unrevealed", "partially_revealed", "revealed")

# 人物关系类型建议值（仅前端下拉提示，数据库不限制枚举）
DEFAULT_CHAR_RELATION_TYPES = (
    "师徒",
    "同门",
    "亲属",
    "盟友",
    "敌对",
    "恋人",
    "朋友",
    "上司",
    "下属",
    "认识",
    "其他",
)

# 人物关系状态
DEFAULT_CHAR_RELATION_STATUSES = ("active", "ended")

# 关系历史事件类型（内部使用）
CHAR_RELATION_EVENT_TYPES = ("created", "updated", "ended", "restored")

# 重建 character_relations 表时使用的完整新表定义（与 SCHEMA 保持一致，去掉 IF NOT EXISTS）
CHAR_RELATION_REBUILD_SQL = """
BEGIN;
CREATE TABLE character_relations_new (
    id                   TEXT PRIMARY KEY,
    novel_id             TEXT NOT NULL REFERENCES novels (id) ON DELETE CASCADE,
    source_character_id  TEXT NOT NULL,
    target_character_id  TEXT NOT NULL,
    relation_type        TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'active',
    description          TEXT NOT NULL DEFAULT '',
    strength             REAL,
    attributes           TEXT NOT NULL DEFAULT '{}',
    start_time           TEXT,
    end_time             TEXT,
    sort_order           INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    CHECK (source_character_id <> target_character_id),
    CHECK (status IN ('active', 'ended')),
    FOREIGN KEY (source_character_id, novel_id)
        REFERENCES characters (id, novel_id) ON DELETE CASCADE,
    FOREIGN KEY (target_character_id, novel_id)
        REFERENCES characters (id, novel_id) ON DELETE CASCADE
);
INSERT INTO character_relations_new
    (id, novel_id, source_character_id, target_character_id, relation_type,
     status, description, strength, attributes, start_time, end_time,
     sort_order, created_at, updated_at)
SELECT id, novel_id, source_character_id, target_character_id, relation_type,
       status, description, strength, attributes, start_time, end_time,
       sort_order, created_at, updated_at
  FROM character_relations;
DROP TABLE character_relations;
ALTER TABLE character_relations_new RENAME TO character_relations;
COMMIT;
"""

# 旧表随 DROP 一并删除了索引，重建后按幂等方式补回
CHAR_RELATION_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_char_relations_source
    ON character_relations (novel_id, source_character_id);
CREATE INDEX IF NOT EXISTS idx_char_relations_target
    ON character_relations (novel_id, target_character_id);
CREATE INDEX IF NOT EXISTS idx_char_relations_status
    ON character_relations (novel_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_char_relations_type
    ON character_relations (novel_id, relation_type);
"""

# 活跃关系部分唯一索引：并发创建同方向同类型有效关系时由数据库兜底。
# 不放在 SCHEMA 中，因为老库可能存在历史重复数据，必须先去重再建索引。
CHAR_RELATION_ACTIVE_UNIQUE_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_char_relations_active
    ON character_relations (novel_id, source_character_id, target_character_id, relation_type)
    WHERE status = 'active';
"""


def db_path() -> Path:
    return Path(get_settings().database_path)


@contextmanager
def get_connection():
    """每次操作使用独立连接，避免跨线程共享。"""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _dedupe_active_relations(conn: sqlite3.Connection) -> None:
    """软终止同组中较新的重复有效关系（保留最早创建的一条），并补写 ended 事件。

    仅在建立部分唯一索引前发现历史重复数据时执行，属于一次性数据修复。
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dupes = conn.execute(
        """
        SELECT c.id, c.novel_id
          FROM character_relations c
         WHERE c.status = 'active'
           AND EXISTS (
               SELECT 1 FROM character_relations x
                WHERE x.novel_id = c.novel_id
                  AND x.source_character_id = c.source_character_id
                  AND x.target_character_id = c.target_character_id
                  AND x.relation_type = c.relation_type
                  AND x.status = 'active'
                  AND (x.created_at < c.created_at
                       OR (x.created_at = c.created_at AND x.id < c.id))
           )
        """
    ).fetchall()
    for row in dupes:
        relation_id = row["id"]
        conn.execute(
            "UPDATE character_relations"
            "   SET status = 'ended', end_time = ?, updated_at = ?"
            " WHERE id = ?",
            (now, now, relation_id),
        )
        seq_row = conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS n"
            "  FROM character_relation_events WHERE relation_id = ?",
            (relation_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO character_relation_events
                (id, novel_id, relation_id, event_type, title, description,
                 previous_data, new_data, story_time, chapter_id, sequence, created_at)
            VALUES (?, ?, ?, 'ended', '系统自动去重', ?, '{}', '{}', NULL, NULL, ?, ?)
            """,
            (
                uuid4().hex,
                row["novel_id"],
                relation_id,
                "数据库迁移发现同方向同类型的重复有效关系，"
                "此条已被软终止，仅保留最早创建的一条。",
                int(seq_row["n"]) if seq_row else 1,
                now,
            ),
        )
    if dupes:
        conn.commit()


def init_database() -> None:
    """可重复执行的数据库初始化。"""
    db_path().parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)

        # 迁移：对升级上来的老库，如果已有 character_relation_events 但缺少 sequence 列则补上。
        # 新建库的 CREATE TABLE 里已声明该列，不会重复执行。
        cols = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(character_relation_events)"
            ).fetchall()
        ]
        if "sequence" not in cols:
            conn.execute(
                "ALTER TABLE character_relation_events ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0"
            )
        # sequence 列就绪后再创建引用它的事件表索引（幂等）
        conn.executescript(CHAR_REL_EVENT_INDEXES_SQL)

        # 迁移：老库的 character_relations 使用单列外键，无法从数据库层面保证
        # 关系两端人物与关系本身属于同一本小说。检测到缺少复合外键时按 SQLite
        # 官方流程重建该表（建新表 -> 拷数据 -> 删旧表 -> 改名）。
        # 注意：必须先关闭 foreign_keys 再 DROP，否则 DROP 触发的隐式 DELETE
        # 会级联清空 character_relation_events；重建在显式事务中执行，失败自动回滚。
        fk_rows = conn.execute(
            "PRAGMA foreign_key_list(character_relations)"
        ).fetchall()
        has_composite_fk = any(
            fk["table"] == "characters" and fk["from"] == "novel_id"
            for fk in fk_rows
        )
        if fk_rows and not has_composite_fk:
            conn.commit()
            conn.execute("PRAGMA foreign_keys = OFF")
            try:
                conn.executescript(CHAR_RELATION_REBUILD_SQL)
            finally:
                conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(CHAR_RELATION_INDEXES_SQL)

        # 迁移：创建活跃关系部分唯一索引。若历史数据已存在重复有效关系，
        # 先软终止较新的重复关系（补写 ended 事件），再建索引。
        try:
            conn.execute(CHAR_RELATION_ACTIVE_UNIQUE_SQL)
        except sqlite3.IntegrityError:
            _dedupe_active_relations(conn)
            conn.execute(CHAR_RELATION_ACTIVE_UNIQUE_SQL)
