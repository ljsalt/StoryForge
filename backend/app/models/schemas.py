"""API 请求/响应数据模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ProviderType = Literal["deepseek", "openai_compatible", "custom"]
TaskKey = Literal["planner", "writer", "editor", "assistant"]


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64, description="服务商名称")
    provider_type: ProviderType = "deepseek"
    base_url: str = Field(min_length=1, max_length=500, description="接口地址，仅允许 http/https")
    api_key: str | None = Field(default=None, max_length=4000, description="API Key，可为空")
    enabled: bool = True

    @field_validator("name", "base_url")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    provider_type: ProviderType | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    # 传 null 或省略表示不修改；传空字符串表示清除密钥
    api_key: str | None = Field(default=None, max_length=4000)
    enabled: bool | None = None

    @field_validator("name", "base_url")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class ProviderOut(BaseModel):
    id: str
    name: str
    provider_type: ProviderType
    base_url: str
    enabled: bool
    has_api_key: bool
    api_key_masked: str
    created_at: str
    updated_at: str


class ModelCreate(BaseModel):
    provider_id: str
    name: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=200, description="API 模型标识符")
    remark: str = Field(default="", max_length=500)
    enabled: bool = True

    @field_validator("name", "model_id")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class ModelUpdate(BaseModel):
    provider_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=64)
    model_id: str | None = Field(default=None, min_length=1, max_length=200)
    remark: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None

    @field_validator("name", "model_id")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class ModelOut(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    provider_type: ProviderType
    name: str
    model_id: str
    remark: str
    enabled: bool
    created_at: str
    updated_at: str


class ModelTestRequest(BaseModel):
    model_id: str


class ModelTestResult(BaseModel):
    success: bool
    latency_ms: int
    method: str
    error_code: str | None = None
    message: str
    model_identifier: str


class TaskSettingOut(BaseModel):
    task: TaskKey
    model_id: str | None = None


class ModelSettingsOut(BaseModel):
    tasks: list[TaskSettingOut]
    default_model_id: str | None = None


class ModelSettingsUpdate(BaseModel):
    tasks: dict[TaskKey, str | None] = Field(default_factory=dict)
    default_model_id: str | None = None


# ----------------------------- 小说项目 -----------------------------
NovelStatus = Literal["planning", "writing", "paused", "completed"]

_TAG_MAX = 20


def _clean_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        value = tag.strip()
        if not value:
            continue
        if len(value) > _TAG_MAX:
            raise ValueError(f"单个标签不能超过 {_TAG_MAX} 个字符")
        if value not in cleaned:
            cleaned.append(value)
    if len(cleaned) > 10:
        raise ValueError("标签最多 10 个")
    return cleaned


class NovelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100, description="小说名称")
    subtitle: str = Field(default="", max_length=100, description="副标题")
    description: str = Field(default="", max_length=2000, description="小说简介")
    genre: str = Field(default="", max_length=50, description="题材")
    tags: list[str] = Field(default_factory=list, description="标签")
    status: NovelStatus = "planning"
    cover_color: str = Field(default="", max_length=20)
    target_word_count: int = Field(default=100000, ge=1, le=10_000_000, description="目标字数")

    @field_validator("title", "subtitle", "description", "genre", "cover_color")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("小说名称不能为空")
        return value

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, value: list[str]) -> list[str]:
        return _clean_tags(value)

    @field_validator("cover_color")
    @classmethod
    def _validate_color(cls, value: str) -> str:
        if value and (len(value) != 7 or not value.startswith("#")):
            raise ValueError("封面颜色需使用 #RRGGBB 格式")
        return value


class NovelUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    subtitle: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    genre: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = None
    status: NovelStatus | None = None
    cover_color: str | None = Field(default=None, max_length=20)
    target_word_count: int | None = Field(default=None, ge=1, le=10_000_000)

    @field_validator("title", "subtitle", "description", "genre", "cover_color")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("小说名称不能为空")
        return value

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, value: list[str] | None) -> list[str] | None:
        return _clean_tags(value) if value is not None else None

    @field_validator("cover_color")
    @classmethod
    def _validate_color(cls, value: str | None) -> str | None:
        if value and (len(value) != 7 or not value.startswith("#")):
            raise ValueError("封面颜色需使用 #RRGGBB 格式")
        return value


class NovelStats(BaseModel):
    chapter_count: int = 0
    completed_chapter_count: int = 0
    character_count: int = 0
    character_relation_count: int = 0
    word_count: int = 0
    world_entry_count: int = 0


class NovelOut(BaseModel):
    id: str
    title: str
    subtitle: str
    description: str
    genre: str
    tags: list[str]
    status: NovelStatus
    cover_color: str
    target_word_count: int
    current_word_count: int = 0
    is_default: bool = False
    created_at: str
    updated_at: str


class NovelDetail(NovelOut):
    stats: NovelStats = Field(default_factory=NovelStats)


class NovelDeleteResult(BaseModel):
    deleted: bool
    default_cleared: bool


# ----------------------------- 世界观设定 -----------------------------
_WORLD_TAG_MAX = 20
_WORLD_TAG_COUNT = 10
_WORLD_ATTR_MAX = 30
_WORLD_ATTR_KEY_MAX = 50
_WORLD_ATTR_VALUE_MAX = 500


def _clean_world_tags(tags: list[str] | None) -> list[str] | None:
    if tags is None:
        return None
    cleaned: list[str] = []
    for tag in tags:
        value = tag.strip()
        if not value:
            continue
        if len(value) > _WORLD_TAG_MAX:
            raise ValueError(f"单个标签不能超过 {_WORLD_TAG_MAX} 个字符")
        if value not in cleaned:
            cleaned.append(value)
    if len(cleaned) > _WORLD_TAG_COUNT:
        raise ValueError(f"标签最多 {_WORLD_TAG_COUNT} 个")
    return cleaned


def _clean_world_attributes(attrs: dict[str, Any] | None) -> dict[str, Any] | None:
    if attrs is None:
        return None
    if len(attrs) > _WORLD_ATTR_MAX:
        raise ValueError(f"自定义属性最多 {_WORLD_ATTR_MAX} 项")
    cleaned: dict[str, Any] = {}
    for raw_key, value in attrs.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError("属性名不能为空")
        if len(key) > _WORLD_ATTR_KEY_MAX:
            raise ValueError(f"属性名不能超过 {_WORLD_ATTR_KEY_MAX} 个字符")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"属性“{key}”的值必须是文本、数字、布尔或空值")
        if isinstance(value, str) and len(value) > _WORLD_ATTR_VALUE_MAX:
            raise ValueError(f"属性“{key}”的值不能超过 {_WORLD_ATTR_VALUE_MAX} 个字符")
        cleaned[key] = value
    return cleaned


class WorldCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="分类名称")
    description: str = Field(default="", max_length=500, description="分类说明")
    sort_order: int = Field(default=0, ge=0, le=100000)

    @field_validator("name", "description")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("分类名称不能为空")
        return value


class WorldCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None, ge=0, le=100000)

    @field_validator("name", "description")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("分类名称不能为空")
        return value


class WorldCategoryOut(BaseModel):
    id: str
    novel_id: str
    name: str
    description: str
    sort_order: int
    entry_count: int = 0
    created_at: str
    updated_at: str


class WorldEntryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="设定名称")
    category_id: str = Field(min_length=1, max_length=64, description="所属分类")
    summary: str = Field(default="", max_length=500, description="简短介绍")
    content: str = Field(default="", max_length=20000, description="详细描述")
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict, description="结构化属性键值对")
    parent_id: str | None = Field(default=None, max_length=64)
    sort_order: int = Field(default=0, ge=0, le=100000)

    @field_validator("name", "category_id", "summary", "content")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("设定名称不能为空")
        return value

    @field_validator("parent_id")
    @classmethod
    def _parent_empty_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, value: list[str]) -> list[str]:
        cleaned = _clean_world_tags(value)
        return cleaned or []

    @field_validator("attributes")
    @classmethod
    def _validate_attributes(cls, value: dict[str, Any]) -> dict[str, Any]:
        cleaned = _clean_world_attributes(value)
        return cleaned or {}


class WorldEntryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category_id: str | None = Field(default=None, min_length=1, max_length=64)
    summary: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=20000)
    tags: list[str] | None = None
    attributes: dict[str, Any] | None = None
    parent_id: str | None = Field(default=None, max_length=64)
    sort_order: int | None = Field(default=None, ge=0, le=100000)

    @field_validator("name", "category_id", "summary", "content")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("设定名称不能为空")
        return value

    @field_validator("parent_id")
    @classmethod
    def _parent_empty_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, value: list[str] | None) -> list[str] | None:
        return _clean_world_tags(value)

    @field_validator("attributes")
    @classmethod
    def _validate_attributes(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _clean_world_attributes(value)


class WorldEntryOut(BaseModel):
    id: str
    novel_id: str
    category_id: str
    category_name: str
    name: str
    summary: str
    content: str
    tags: list[str]
    attributes: dict[str, Any]
    parent_id: str | None
    parent_name: str | None
    sort_order: int
    created_at: str
    updated_at: str


class WorldCategoryCount(BaseModel):
    category_id: str
    name: str
    count: int


class WorldRelationTypeCount(BaseModel):
    relation_type: str
    count: int


class WorldStats(BaseModel):
    total_entries: int
    category_count: int
    by_category: list[WorldCategoryCount]
    total_relations: int = 0
    relation_type_count: int = 0
    relation_by_type: list[WorldRelationTypeCount] = Field(default_factory=list)
    related_entry_count: int = 0
    latest_updated_at: str | None = None


class WorldDeleteResult(BaseModel):
    deleted: bool


# ----------------------------- 世界观关系 -----------------------------
_RELATION_TYPE_MAX = 50
_RELATION_DESCRIPTION_MAX = 2000


class WorldRelationCreate(BaseModel):
    source_entry_id: str = Field(min_length=1, max_length=64, description="起点条目")
    target_entry_id: str = Field(min_length=1, max_length=64, description="终点条目")
    relation_type: str = Field(
        min_length=1, max_length=_RELATION_TYPE_MAX, description="关系类型，支持自定义"
    )
    description: str = Field(
        default="", max_length=_RELATION_DESCRIPTION_MAX, description="关系描述"
    )

    @field_validator(
        "source_entry_id", "target_entry_id", "relation_type", "description"
    )
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("source_entry_id", "target_entry_id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("条目 ID 不能为空")
        return value

    @field_validator("relation_type")
    @classmethod
    def _type_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("关系类型不能为空")
        return value


class WorldRelationUpdate(BaseModel):
    source_entry_id: str | None = Field(default=None, min_length=1, max_length=64)
    target_entry_id: str | None = Field(default=None, min_length=1, max_length=64)
    relation_type: str | None = Field(
        default=None, min_length=1, max_length=_RELATION_TYPE_MAX
    )
    description: str | None = Field(default=None, max_length=_RELATION_DESCRIPTION_MAX)

    @field_validator(
        "source_entry_id", "target_entry_id", "relation_type", "description"
    )
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("source_entry_id", "target_entry_id")
    @classmethod
    def _id_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("条目 ID 不能为空")
        return value

    @field_validator("relation_type")
    @classmethod
    def _type_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("关系类型不能为空")
        return value


class WorldRelationEntryOut(BaseModel):
    id: str
    name: str
    category_id: str
    category_name: str


class WorldRelationOut(BaseModel):
    id: str
    novel_id: str
    source_entry_id: str
    target_entry_id: str
    relation_type: str
    description: str
    source: WorldRelationEntryOut
    target: WorldRelationEntryOut
    created_at: str
    updated_at: str


class WorldEntryRelationOut(WorldRelationOut):
    direction: Literal["outgoing", "incoming"]


class WorldEntryRelationsOut(BaseModel):
    entry_id: str
    outgoing: list[WorldEntryRelationOut]
    incoming: list[WorldEntryRelationOut]


# ----------------------------- 人物档案 -----------------------------
_CHAR_NAME_MAX = 100
_CHAR_TEXT_MAX = 500
_CHAR_LONG_TEXT_MAX = 5000
_CHAR_TAG_MAX = 20
_CHAR_TAG_COUNT = 10
_CHAR_ATTR_MAX = 30
_CHAR_ATTR_KEY_MAX = 50
_CHAR_ATTR_VALUE_MAX = 500


def _clean_character_tags(tags: list[str] | None) -> list[str] | None:
    if tags is None:
        return None
    cleaned: list[str] = []
    for tag in tags:
        value = tag.strip()
        if not value:
            continue
        if len(value) > _CHAR_TAG_MAX:
            raise ValueError(f"单个标签不能超过 {_CHAR_TAG_MAX} 个字符")
        if value not in cleaned:
            cleaned.append(value)
    if len(cleaned) > _CHAR_TAG_COUNT:
        raise ValueError(f"标签最多 {_CHAR_TAG_COUNT} 个")
    return cleaned


def _clean_character_attributes(attrs: dict[str, Any] | None) -> dict[str, Any] | None:
    if attrs is None:
        return None
    if len(attrs) > _CHAR_ATTR_MAX:
        raise ValueError(f"自定义属性最多 {_CHAR_ATTR_MAX} 项")
    cleaned: dict[str, Any] = {}
    for raw_key, value in attrs.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError("属性名不能为空")
        if len(key) > _CHAR_ATTR_KEY_MAX:
            raise ValueError(f"属性名不能超过 {_CHAR_ATTR_KEY_MAX} 个字符")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"属性“{key}”的值必须是文本、数字、布尔或空值")
        if isinstance(value, str) and len(value) > _CHAR_ATTR_VALUE_MAX:
            raise ValueError(f"属性“{key}”的值不能超过 {_CHAR_ATTR_VALUE_MAX} 个字符")
        cleaned[key] = value
    return cleaned


def _clean_aliases(aliases: list[str] | None) -> list[str] | None:
    if aliases is None:
        return None
    cleaned: list[str] = []
    for alias in aliases:
        value = alias.strip()
        if not value:
            continue
        if len(value) > _CHAR_NAME_MAX:
            raise ValueError(f"别名不能超过 {_CHAR_NAME_MAX} 个字符")
        if value not in cleaned:
            cleaned.append(value)
    if len(cleaned) > 20:
        raise ValueError("别名最多 20 个")
    return cleaned


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=_CHAR_NAME_MAX, description="姓名")
    aliases: list[str] = Field(default_factory=list)
    gender: str = Field(default="", max_length=30)
    age: str = Field(default="", max_length=40)
    race: str = Field(default="", max_length=50)
    identity: str = Field(default="", max_length=_CHAR_TEXT_MAX)
    role: str = Field(default="", max_length=50)
    appearance: str = Field(default="", max_length=_CHAR_LONG_TEXT_MAX)
    personality: str = Field(default="", max_length=_CHAR_LONG_TEXT_MAX)
    background: str = Field(default="", max_length=_CHAR_LONG_TEXT_MAX)
    abilities: str = Field(default="", max_length=_CHAR_LONG_TEXT_MAX)
    cultivation: str = Field(default="", max_length=200)
    affiliation: str = Field(default="", max_length=_CHAR_TEXT_MAX)
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    avatar_color: str = Field(default="", max_length=20)
    sort_order: int = Field(default=0, ge=0, le=100000)

    @field_validator(
        "name", "gender", "age", "race", "identity", "role", "appearance",
        "personality", "background", "abilities", "cultivation", "affiliation",
    )
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("人物姓名不能为空")
        return value

    @field_validator("aliases")
    @classmethod
    def _validate_aliases(cls, value: list[str]) -> list[str]:
        return _clean_aliases(value) or []

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, value: list[str]) -> list[str]:
        return _clean_character_tags(value) or []

    @field_validator("attributes")
    @classmethod
    def _validate_attrs(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _clean_character_attributes(value) or {}

    @field_validator("avatar_color")
    @classmethod
    def _validate_color(cls, value: str) -> str:
        if value and (len(value) != 7 or not value.startswith("#")):
            raise ValueError("头像颜色需使用 #RRGGBB 格式")
        return value


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=_CHAR_NAME_MAX)
    aliases: list[str] | None = None
    gender: str | None = Field(default=None, max_length=30)
    age: str | None = Field(default=None, max_length=40)
    race: str | None = Field(default=None, max_length=50)
    identity: str | None = Field(default=None, max_length=_CHAR_TEXT_MAX)
    role: str | None = Field(default=None, max_length=50)
    appearance: str | None = Field(default=None, max_length=_CHAR_LONG_TEXT_MAX)
    personality: str | None = Field(default=None, max_length=_CHAR_LONG_TEXT_MAX)
    background: str | None = Field(default=None, max_length=_CHAR_LONG_TEXT_MAX)
    abilities: str | None = Field(default=None, max_length=_CHAR_LONG_TEXT_MAX)
    cultivation: str | None = Field(default=None, max_length=200)
    affiliation: str | None = Field(default=None, max_length=_CHAR_TEXT_MAX)
    tags: list[str] | None = None
    attributes: dict[str, Any] | None = None
    avatar_color: str | None = Field(default=None, max_length=20)
    sort_order: int | None = Field(default=None, ge=0, le=100000)

    @field_validator(
        "name", "gender", "age", "race", "identity", "role", "appearance",
        "personality", "background", "abilities", "cultivation", "affiliation",
    )
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("人物姓名不能为空")
        return value

    @field_validator("aliases")
    @classmethod
    def _validate_aliases(cls, value: list[str] | None) -> list[str] | None:
        return _clean_aliases(value)

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, value: list[str] | None) -> list[str] | None:
        return _clean_character_tags(value)

    @field_validator("attributes")
    @classmethod
    def _validate_attrs(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _clean_character_attributes(value)

    @field_validator("avatar_color")
    @classmethod
    def _validate_color(cls, value: str | None) -> str | None:
        if value and (len(value) != 7 or not value.startswith("#")):
            raise ValueError("头像颜色需使用 #RRGGBB 格式")
        return value


class CharacterStateOut(BaseModel):
    id: str
    character_id: str
    life_status: str
    current_location: str
    current_faction: str
    current_cultivation: str
    health_status: str
    emotional_state: str
    current_goal: str
    current_status: str
    attributes: dict[str, Any]
    updated_at: str


class CharacterSecretOut(BaseModel):
    id: str
    character_id: str
    title: str
    content: str
    secrecy_level: str
    reveal_status: str
    notes: str
    created_at: str
    updated_at: str


class CharacterOut(BaseModel):
    id: str
    novel_id: str
    name: str
    aliases: list[str]
    gender: str
    age: str
    race: str
    identity: str
    role: str
    appearance: str
    personality: str
    background: str
    abilities: str
    cultivation: str
    affiliation: str
    tags: list[str]
    attributes: dict[str, Any]
    avatar_color: str
    sort_order: int
    state: CharacterStateOut | None = None
    created_at: str
    updated_at: str


class CharacterListOut(BaseModel):
    """列表接口中的摘要，包含人物档案、生死状态与当前位置等简要信息。"""
    id: str
    novel_id: str
    name: str
    aliases: list[str]
    identity: str
    role: str
    tags: list[str]
    avatar_color: str
    life_status: str = "alive"
    current_location: str = ""
    current_cultivation: str = ""
    sort_order: int
    created_at: str
    updated_at: str


# ----------------------------- 人物当前状态 -----------------------------
_CHAR_STATE_TEXT_MAX = 500
_CHAR_STATE_LONG_MAX = 2000


class CharacterStateUpdate(BaseModel):
    life_status: str | None = Field(default=None, max_length=30)
    current_location: str | None = Field(default=None, max_length=_CHAR_STATE_TEXT_MAX)
    current_faction: str | None = Field(default=None, max_length=_CHAR_STATE_TEXT_MAX)
    current_cultivation: str | None = Field(default=None, max_length=200)
    health_status: str | None = Field(default=None, max_length=_CHAR_STATE_LONG_MAX)
    emotional_state: str | None = Field(default=None, max_length=_CHAR_STATE_LONG_MAX)
    current_goal: str | None = Field(default=None, max_length=_CHAR_STATE_LONG_MAX)
    current_status: str | None = Field(default=None, max_length=_CHAR_STATE_LONG_MAX)
    attributes: dict[str, Any] | None = None

    @field_validator(
        "life_status", "current_location", "current_faction",
        "current_cultivation", "health_status", "emotional_state",
        "current_goal", "current_status",
    )
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("attributes")
    @classmethod
    def _validate_attrs(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _clean_character_attributes(value)


# ----------------------------- 人物秘密 -----------------------------
_CHAR_SECRET_TITLE_MAX = 200
_CHAR_SECRET_CONTENT_MAX = 5000
_CHAR_SECRET_NOTES_MAX = 2000


class CharacterSecretCreate(BaseModel):
    title: str = Field(min_length=1, max_length=_CHAR_SECRET_TITLE_MAX)
    content: str = Field(default="", max_length=_CHAR_SECRET_CONTENT_MAX)
    secrecy_level: str = Field(default="restricted", max_length=30)
    reveal_status: str = Field(default="unrevealed", max_length=30)
    notes: str = Field(default="", max_length=_CHAR_SECRET_NOTES_MAX)

    @field_validator(
        "title", "content", "secrecy_level", "reveal_status", "notes"
    )
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("秘密标题不能为空")
        return value


class CharacterSecretUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=_CHAR_SECRET_TITLE_MAX)
    content: str | None = Field(default=None, max_length=_CHAR_SECRET_CONTENT_MAX)
    secrecy_level: str | None = Field(default=None, max_length=30)
    reveal_status: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=_CHAR_SECRET_NOTES_MAX)

    @field_validator(
        "title", "content", "secrecy_level", "reveal_status", "notes"
    )
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("秘密标题不能为空")
        return value


# ----------------------------- 人物关系 -----------------------------
_CHAR_REL_TYPE_MAX = 80
_CHAR_REL_DESC_MAX = 2000
_CHAR_REL_EVENT_TITLE_MAX = 200
_CHAR_REL_EVENT_DESC_MAX = 2000


class CharacterRelationCreate(BaseModel):
    source_character_id: str = Field(min_length=1, max_length=64)
    target_character_id: str = Field(min_length=1, max_length=64)
    relation_type: str = Field(min_length=1, max_length=_CHAR_REL_TYPE_MAX)
    description: str = Field(default="", max_length=_CHAR_REL_DESC_MAX)
    strength: float | None = Field(default=None, ge=0, le=100)
    attributes: dict[str, Any] = Field(default_factory=dict)
    start_time: str | None = Field(default=None, max_length=64)
    story_time: str | None = Field(default=None, max_length=64)
    chapter_id: str | None = Field(default=None, max_length=64, description="关联章节")

    @field_validator(
        "relation_type", "description", "start_time", "story_time", "chapter_id"
    )
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("chapter_id")
    @classmethod
    def _chapter_empty_to_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("relation_type")
    @classmethod
    def _type_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("关系类型不能为空")
        return value


class CharacterRelationUpdate(BaseModel):
    relation_type: str | None = Field(default=None, min_length=1, max_length=_CHAR_REL_TYPE_MAX)
    description: str | None = Field(default=None, max_length=_CHAR_REL_DESC_MAX)
    strength: float | None = Field(default=None, ge=0, le=100)
    attributes: dict[str, Any] | None = None
    start_time: str | None = Field(default=None, max_length=64)
    story_time: str | None = Field(default=None, max_length=64)
    chapter_id: str | None = Field(default=None, max_length=64, description="事件关联章节")

    @field_validator("relation_type", "description", "start_time", "story_time", "chapter_id")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("relation_type")
    @classmethod
    def _type_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("关系类型不能为空")
        return value


class CharacterRelationEventInfo(BaseModel):
    title: str | None = Field(default=None, max_length=_CHAR_REL_EVENT_TITLE_MAX)
    description: str | None = Field(default=None, max_length=_CHAR_REL_EVENT_DESC_MAX)
    story_time: str | None = Field(default=None, max_length=64)
    chapter_id: str | None = Field(default=None, max_length=64)

    @field_validator("title", "description", "story_time", "chapter_id")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CharacterRelationOut(BaseModel):
    id: str
    novel_id: str
    source_character_id: str
    target_character_id: str
    source_name: str
    target_name: str
    relation_type: str
    status: str
    description: str
    strength: float | None
    attributes: dict[str, Any]
    start_time: str | None
    end_time: str | None
    sort_order: int
    created_at: str
    updated_at: str


class CharacterRelationEventOut(BaseModel):
    id: str
    relation_id: str
    event_type: str
    title: str
    description: str
    previous_data: dict[str, Any]
    new_data: dict[str, Any]
    story_time: str | None
    chapter_id: str | None
    chapter_title: str | None = None
    chapter_number: int | None = None
    sequence: int = 0
    created_at: str


class ChapterRelationEventOut(CharacterRelationEventOut):
    """章节详情里展示的关系变化事件，附带关系两端人物姓名。"""
    source_name: str
    target_name: str


class CharacterCharacterRelationOut(BaseModel):
    relation: CharacterRelationOut
    direction: Literal["outgoing", "incoming"]


class CharacterCharacterRelationsOut(BaseModel):
    character_id: str
    outgoing: list[CharacterCharacterRelationOut]
    incoming: list[CharacterCharacterRelationOut]


# ----------------------------- 章节 -----------------------------
ChapterStatus = Literal["planned", "drafting", "completed"]
_CHAR_TITLE_MAX = 200
_CHAR_SUMMARY_MAX = 5000
_CHAPTER_CONTENT_MAX = 5_000_000


class ChapterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=_CHAR_TITLE_MAX, description="章节标题")
    chapter_number: int | None = Field(default=None, ge=1, le=1_000_000)
    volume_number: int | None = Field(default=None, ge=1, le=100_000)
    content: str = Field(default="", max_length=_CHAPTER_CONTENT_MAX, description="章节正文")
    summary: str = Field(default="", max_length=_CHAR_SUMMARY_MAX, description="章节摘要")
    status: ChapterStatus = "planned"

    @field_validator("title", "content", "summary")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("章节标题不能为空")
        return value


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=_CHAR_TITLE_MAX)
    chapter_number: int | None = Field(default=None, ge=1, le=1_000_000)
    volume_number: int | None = Field(default=None, ge=1, le=100_000)
    content: str | None = Field(default=None, max_length=_CHAPTER_CONTENT_MAX)
    summary: str | None = Field(default=None, max_length=_CHAR_SUMMARY_MAX)
    status: ChapterStatus | None = None

    @field_validator("title", "content", "summary")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("章节标题不能为空")
        return value


class ChapterReorder(BaseModel):
    ordered_ids: list[str] = Field(min_length=1, max_length=5000, description="按新顺序排列的章节 ID")


class ChapterOut(BaseModel):
    id: str
    novel_id: str
    chapter_number: int
    volume_number: int | None
    title: str
    content: str
    summary: str
    status: ChapterStatus
    word_count: int
    sort_order: int
    created_at: str
    updated_at: str


class ChapterSummaryOut(BaseModel):
    """目录列表用的摘要，不返回正文，避免长正文拖慢列表加载。"""
    id: str
    novel_id: str
    chapter_number: int
    volume_number: int | None
    title: str
    summary: str
    status: ChapterStatus
    word_count: int
    sort_order: int
    created_at: str
    updated_at: str


class ChapterStats(BaseModel):
    chapter_count: int = 0
    completed_chapter_count: int = 0
    drafting_chapter_count: int = 0
    planned_chapter_count: int = 0
    total_word_count: int = 0


# ----------------------------- 剧情事件 -----------------------------
PlotImportance = Literal["low", "normal", "high", "critical"]
_PLOT_TITLE_MAX = 200
_PLOT_DESCRIPTION_MAX = 20000
_PLOT_TYPE_MAX = 80
_PLOT_TIME_MAX = 100
_PLOT_LOCATION_NAME_MAX = 200
_PLOT_ROLE_MAX = 100
_PLOT_PARTICIPANT_DESC_MAX = 1000
_PLOT_PARTICIPANTS_MAX = 50


class PlotEventParticipantInput(BaseModel):
    character_id: str = Field(min_length=1, max_length=64)
    participant_role: str = Field(default="", max_length=_PLOT_ROLE_MAX)
    description: str = Field(default="", max_length=_PLOT_PARTICIPANT_DESC_MAX)

    @field_validator("character_id", "participant_role", "description")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()


class PlotEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=_PLOT_TITLE_MAX)
    description: str = Field(default="", max_length=_PLOT_DESCRIPTION_MAX)
    event_type: str = Field(default="", max_length=_PLOT_TYPE_MAX, description="事件类型，支持自定义")
    story_time: str | None = Field(default=None, max_length=_PLOT_TIME_MAX, description="故事世界内时间")
    chapter_id: str | None = Field(default=None, max_length=64)
    location_id: str | None = Field(default=None, max_length=64)
    location_name: str = Field(default="", max_length=_PLOT_LOCATION_NAME_MAX)
    importance: PlotImportance = "normal"
    sequence: int = Field(default=0, ge=0, le=1_000_000)
    participants: list[PlotEventParticipantInput] = Field(default_factory=list)

    @field_validator("title", "description", "event_type", "story_time", "location_name")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("事件标题不能为空")
        return value

    @field_validator("chapter_id", "location_id")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("participants")
    @classmethod
    def _validate_participants(
        cls, value: list[PlotEventParticipantInput]
    ) -> list[PlotEventParticipantInput]:
        if len(value) > _PLOT_PARTICIPANTS_MAX:
            raise ValueError(f"参与人物最多 {_PLOT_PARTICIPANTS_MAX} 位")
        return value


class PlotEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=_PLOT_TITLE_MAX)
    description: str | None = Field(default=None, max_length=_PLOT_DESCRIPTION_MAX)
    event_type: str | None = Field(default=None, max_length=_PLOT_TYPE_MAX)
    story_time: str | None = Field(default=None, max_length=_PLOT_TIME_MAX)
    chapter_id: str | None = Field(default=None, max_length=64)
    location_id: str | None = Field(default=None, max_length=64)
    location_name: str | None = Field(default=None, max_length=_PLOT_LOCATION_NAME_MAX)
    importance: PlotImportance | None = None
    sequence: int | None = Field(default=None, ge=0, le=1_000_000)
    participants: list[PlotEventParticipantInput] | None = None

    @field_validator("title", "description", "event_type", "story_time", "location_name")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("事件标题不能为空")
        return value

    @field_validator("chapter_id", "location_id")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("participants")
    @classmethod
    def _validate_participants(
        cls, value: list[PlotEventParticipantInput] | None
    ) -> list[PlotEventParticipantInput] | None:
        if value is not None and len(value) > _PLOT_PARTICIPANTS_MAX:
            raise ValueError(f"参与人物最多 {_PLOT_PARTICIPANTS_MAX} 位")
        return value


class PlotEventParticipantOut(BaseModel):
    id: str
    character_id: str
    character_name: str
    participant_role: str
    description: str


class PlotEventOut(BaseModel):
    id: str
    novel_id: str
    chapter_id: str | None
    chapter_title: str | None = None
    chapter_number: int | None = None
    title: str
    description: str
    event_type: str
    story_time: str | None
    location_id: str | None
    location_name: str
    importance: PlotImportance
    sequence: int
    participants: list[PlotEventParticipantOut] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PlotTimelineOut(BaseModel):
    """timed 为有故事时间的事件（按故事时间排序），untimed 为未填写故事时间的事件。"""
    timed: list[PlotEventOut] = Field(default_factory=list)
    untimed: list[PlotEventOut] = Field(default_factory=list)

# ----------------------------- AI 基础设施 -----------------------------
AiTaskType = Literal["planner", "writer", "editor", "assistant", "default"]
AiTaskStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
ContextPov = Literal["author", "narrative", "character"]


class AiGenerateRequest(BaseModel):
    """AI 调用测试请求。本阶段仅用于基础设施测试，不代表正式章节生成。"""
    novel_id: str = Field(min_length=1, max_length=64)
    task_type: AiTaskType = "default"
    model_id: str | None = Field(default=None, max_length=64, description="显式指定模型行 ID")
    system_prompt: str = Field(default="", max_length=20000)
    user_prompt: str = Field(min_length=1, max_length=50000)
    context: str = Field(default="", max_length=200000)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=128000)
    timeout: float | None = Field(default=None, ge=1, le=600)
    include_reasoning: bool = False
    extra_params: dict[str, Any] | None = None

    @field_validator("novel_id", "model_id")
    @classmethod
    def _strip_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("user_prompt")
    @classmethod
    def _prompt_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("用户提示词不能为空")
        return value

    @field_validator("extra_params")
    @classmethod
    def _check_extra(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and len(value) > 20:
            raise ValueError("额外模型参数最多 20 个")
        return value


class AiGenerateResult(BaseModel):
    """统一 AI 调用响应结构；不包含任何密钥信息。"""
    success: bool
    content: str = ""
    reasoning: str = ""
    model: str = ""
    provider: str = ""
    task_type: str = ""
    finish_reason: str | None = None
    truncated: bool = False
    usage: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int = 0
    resolved_from: str = ""
    task_id: str | None = None
    test_only: bool = True


class AiRoutePreviewOut(BaseModel):
    task_type: str
    resolved: bool
    model_id: str | None = None
    model_identifier: str | None = None
    provider_id: str | None = None
    provider_type: str | None = None
    resolved_from: str | None = None
    message: str = ""


class ContextPreviewRequest(BaseModel):
    novel_id: str = Field(min_length=1, max_length=64)
    task_type: AiTaskType = "writer"
    chapter_id: str | None = Field(default=None, max_length=64)
    character_ids: list[str] | None = Field(default=None, max_length=50)
    token_budget: int | None = Field(default=None, ge=200, le=200000)
    pov: ContextPov = "author"
    user_requirement: str = Field(default="", max_length=20000)

    @field_validator("novel_id", "chapter_id")
    @classmethod
    def _strip_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ContextSectionOut(BaseModel):
    key: str
    title: str
    content: str
    tokens: int
    estimated: bool = True
    included: bool = True
    item_count: int = 0
    priority: int = 0


class ContextPreviewOut(BaseModel):
    context_text: str
    sections: list[ContextSectionOut] = Field(default_factory=list)
    estimated_tokens: int
    token_budget: int
    omitted_sections: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PromptTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    task_type: AiTaskType
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(default="", max_length=20000)
    user_prompt_template: str = Field(default="", max_length=50000)
    is_active: bool = True

    @field_validator("name", "description")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("模板名称不能为空")
        return value


class PromptTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    task_type: AiTaskType | None = None
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, max_length=20000)
    user_prompt_template: str | None = Field(default=None, max_length=50000)
    is_active: bool | None = None

    @field_validator("name", "description")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class PromptTemplateOut(BaseModel):
    id: str
    name: str
    task_type: str
    description: str
    system_prompt: str
    user_prompt_template: str
    version: int
    is_active: bool
    variables: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PromptTemplateVersionOut(BaseModel):
    id: str
    template_id: str
    version: int
    name: str
    task_type: str
    description: str
    system_prompt: str
    user_prompt_template: str
    created_at: str


class PromptTemplateRenderRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=64)
    variables: dict[str, str] = Field(default_factory=dict)

    @field_validator("variables")
    @classmethod
    def _check_variables(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 50:
            raise ValueError("模板变量最多 50 个")
        return value


class PromptTemplateRenderOut(BaseModel):
    system_prompt: str
    user_prompt: str
    template_id: str
    version: int
    task_type: str


class AiTaskOut(BaseModel):
    id: str
    novel_id: str
    task_type: str
    model_id: str | None
    model_identifier: str = ""
    provider_id: str | None
    status: AiTaskStatus
    input_summary: str = ""
    output_summary: str = ""
    error_code: str | None = None
    error_message: str | None = None
    prompt_template_id: str | None = None
    template_version: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_tokens: int | None = None
    truncated: bool = False
    latency_ms: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str


# ----------------------------- P4.1.2 单章节创作工作流 -----------------------------

WritingSessionStatus = Literal[
    "planning",
    "awaiting_plan_approval",
    "writing",
    "paused_for_user",
    "draft_ready",
    "completed",
    "cancelled",
    "failed",
]


class WritingSessionCreate(BaseModel):
    """从已有章节或新章节草稿启动一次创作会话。"""

    title: str = Field(default="", max_length=200)
    chapter_id: str | None = Field(default=None, max_length=64)
    user_instruction: str = Field(default="", max_length=5000)
    pov_character_id: str | None = Field(default=None, max_length=64)
    target_word_count: int = Field(default=3000, ge=500, le=10000)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("chapter_id", "pov_character_id")
    @classmethod
    def _strip_optional_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class WritingSessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    user_instruction: str | None = Field(default=None, max_length=5000)
    pov_character_id: str | None = Field(default=None, max_length=64)
    target_word_count: int | None = Field(default=None, ge=500, le=10000)


class WritingSceneInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str = Field(default="", max_length=200)
    characters: list[str] = Field(default_factory=list, max_length=30)
    purpose: str = Field(min_length=1, max_length=2000)
    actions: str = Field(min_length=1, max_length=4000)
    conflict: str = Field(min_length=1, max_length=2000)
    result: str = Field(min_length=1, max_length=2000)
    transition: str = Field(min_length=1, max_length=2000)


class WritingPlotEventInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)


class WritingDecisionInput(BaseModel):
    decision_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    context: str = Field(default="", max_length=2000)
    options: list[str] = Field(min_length=1, max_length=10)
    recommended_option: str | None = Field(default=None, max_length=200)
    consequences: str = Field(default="", max_length=2000)
    is_required: bool = False


class WritingPlanUpdate(BaseModel):
    """用户手工修改计划时提交的完整结构（必须通过同一套结构校验）。"""

    chapter_goal: str = Field(min_length=1, max_length=2000)
    opening: str = Field(min_length=1, max_length=4000)
    scenes: list[WritingSceneInput] = Field(min_length=1, max_length=30)
    character_actions: list[str] = Field(default_factory=list, max_length=30)
    conflicts: list[str] = Field(default_factory=list, max_length=30)
    plot_events: list[WritingPlotEventInput] = Field(default_factory=list, max_length=30)
    foreshadowing: list[str] = Field(default_factory=list, max_length=30)
    ending: str = Field(min_length=1, max_length=4000)
    estimated_word_count: int = Field(ge=1, le=50000)
    major_decisions: list[WritingDecisionInput] = Field(default_factory=list, max_length=20)


class WritingPlanGenerateRequest(BaseModel):
    extra_instruction: str = Field(default="", max_length=5000)
    temperature: float = Field(default=0.6, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=256, le=32768)


class WritingDecisionResolveRequest(BaseModel):
    selected_option: str = Field(default="", max_length=200)
    custom_answer: str = Field(default="", max_length=2000)


class WritingPlanApproveRequest(BaseModel):
    draft_title: str = Field(default="", max_length=200)


class WritingSegmentGenerateRequest(BaseModel):
    sequence: int | None = Field(default=None, ge=1, le=100)
    extra_instruction: str = Field(default="", max_length=5000)
    temperature: float = Field(default=0.8, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=256, le=32768)


class WritingDraftUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=200000)


class WritingConfirmRequest(BaseModel):
    """确认写入正式章节：默认另存为新章节，覆盖原章节必须显式指定。"""

    mode: Literal["new_chapter", "replace_existing"] = "new_chapter"
    chapter_title: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=500)


class WritingSessionOut(BaseModel):
    id: str
    novel_id: str
    chapter_id: str | None = None
    title: str
    status: WritingSessionStatus
    task_type: str = "writer"
    user_instruction: str = ""
    pov_character_id: str | None = None
    target_word_count: int = 3000
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None
    plan_version: int | None = None
    draft_status: str | None = None
    draft_word_count: int = 0


class WritingSegmentOut(BaseModel):
    id: str
    draft_id: str
    scene_index: int
    sequence: int
    content: str = ""
    status: Literal["pending", "generating", "completed", "failed"]
    word_count: int = 0
    attempt: int = 1
    truncated: bool = False
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class WritingDraftOut(BaseModel):
    id: str
    novel_id: str
    session_id: str
    plan_id: str | None = None
    chapter_id: str | None = None
    title: str
    content: str = ""
    word_count: int = 0
    status: Literal["drafting", "ready", "confirmed", "discarded"]
    edited: bool = False
    created_at: str
    updated_at: str
    confirmed_at: str | None = None
    segments: list[WritingSegmentOut] = Field(default_factory=list)
    progress: dict[str, Any] = Field(default_factory=dict)
