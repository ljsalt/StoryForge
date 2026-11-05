# StoryForge

本地优先的 AI 中文长篇小说创作工作室。

> 当前版本：0.3.2-P3.2.2（世界观关系管理）

## 项目介绍

StoryForge 是一个支持多模型 API 的中文长篇小说创作系统，采用前后端分离架构，数据保存在本地。

整体规划（分阶段实施，**当前已完成 P1、P2、P3.1、P3.2.1、P3.2.2**）：

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| P1 | 项目初始化：基础界面、后端服务、电脑与手机局域网访问 | ✅ 已完成 |
| P2 | 统一模型接口：多服务商/多模型管理、API Key 加密、连接测试、任务模型分配 | ✅ 已完成 |
| P3.1 | 小说项目管理：小说 CRUD、搜索筛选、详情页、默认项目、Dashboard 联动 | ✅ 已完成 |
| P3.2.1 | 世界观基础管理：分类与条目 CRUD、搜索筛选、标签、结构化属性 | ✅ 已完成 |
| P3.2.2 | 世界观关系管理：有向关系 CRUD、正/反向关系、关系管理与网络视图 | ✅ 当前阶段 |
| P3.3 | 人物档案管理 | 未开始 |
| P3.4 | 剧情记忆管理 | 未开始 |
| P3.5 | 长篇章节生成 | 未开始 |
| P4 | 半自主创作：AI 自主推进剧情，重大节点暂停并询问 | 未开始 |

## 技术栈

- **前端**：Vue 3、TypeScript、Vite、Naive UI、Vue Router、Pinia、Axios
- **后端**：Python 3.12、FastAPI、Uvicorn、httpx、cryptography
- **数据库**：SQLite（小说项目、服务商、模型与任务分配配置）
- **其他**：Git、npm

## 目录结构

```
StoryForge/
├── frontend/                # 前端（Vue 3 + Vite）
│   ├── src/
│   │   ├── api/             # API 封装（小说、世界观、模型等）
│   │   ├── components/      # 公共组件（小说卡片、世界观条目/表单/详情/关系/图谱/分类管理）
│   │   ├── layouts/         # 页面布局（含响应式导航）
│   │   ├── router/          # 路由
│   │   ├── stores/          # Pinia 状态（系统、模型、小说、世界观）
│   │   ├── utils/           # 时间格式化等工具
│   │   ├── views/           # 页面（首页/小说列表/小说详情/世界观/世界观关系/人物/预设/设置）
│   │   ├── App.vue
│   │   └── main.ts
│   └── package.json
├── backend/                 # 后端（FastAPI）
│   ├── app/
│   │   ├── api/             # 路由（基础接口 + 模型接口 + 小说接口 + 世界观接口）
│   │   ├── core/            # 配置、API Key 加密、Base URL 校验
│   │   ├── database/        # SQLite 初始化与连接
│   │   ├── adapters/        # 统一模型适配器（DeepSeek / OpenAI 兼容）
│   │   ├── models/          # 请求与响应数据结构
│   │   ├── services/        # 服务商、模型、ModelRouter、小说服务、世界观/关系服务
│   │   └── main.py          # 应用入口
│   ├── tests/               # pytest 自动化测试
│   └── requirements.txt
├── data/
│   ├── novels/              # 小说数据（本地保存，不入库）
│   ├── backups/             # 备份数据（不入库）
│   ├── secrets/             # API Key 加密主密钥（自动生成，禁止提交）
│   └── storyforge.db        # SQLite 数据库（自动创建，禁止提交）
├── .env.example             # 环境变量示例
├── start_backend.bat        # Windows 后端启动脚本
├── start_frontend.bat       # Windows 前端启动脚本
└── README.md
```

## 环境要求

- Windows 10 / 11
- Python **3.12** 或更高版本（https://www.python.org/downloads/ ，安装时勾选 "Add python.exe to PATH"）
- Node.js **18** 或更高版本（https://nodejs.org/ ）

检查是否已安装：按 `Win+R` 输入 `cmd` 回车，执行：

```
python --version
node --version
```

## 安装与启动（Windows）

两种方式任选其一。

### 方式一：双击启动脚本（推荐，适合没有编程经验的用户）

1. 双击 `start_backend.bat`
   - 首次运行会自动创建虚拟环境并安装后端依赖，需要几分钟，请耐心等待。
   - 看到 `Uvicorn running on http://0.0.0.0:8000` 即表示后端启动成功，**不要关闭该窗口**。
2. 双击 `start_frontend.bat`
   - 首次运行会自动安装前端依赖，需要几分钟。
   - 看到 `Local: http://localhost:5173/` 即表示前端启动成功，**不要关闭该窗口**。
3. 打开电脑浏览器，访问 http://localhost:5173

### 方式二：命令行手动启动

后端（在 `backend` 目录下）：

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端（在 `frontend` 目录下）：

```bash
npm install
npm run dev
```

接口验证：

- 健康检查：http://localhost:8000/api/health
- 系统信息：http://localhost:8000/api/system/info
- 接口文档：http://localhost:8000/docs

## 模型与 API 管理（P2）

打开左侧导航「系统设置」，页面包含四个标签：

1. **API 服务商**：添加/编辑/删除服务商，启停开关，查看 API Key 脱敏状态。
2. **模型管理**：为服务商添加多个模型，填写模型标识符，测试连接。
3. **任务模型分配**：为剧情导演、正文作者、连续性编辑、普通辅助分别指定模型，并设置全局默认模型；未指定时自动回退到默认模型。
4. **默认设置**：查看后端连接状态、数据库与密钥存放位置、安全说明。

### 添加 DeepSeek 官方 API

1. 进入「系统设置 → API 服务商」，点击「添加服务商」。
2. 服务商名称填 `DeepSeek Official`，类型选「DeepSeek 官方」。
3. Base URL 默认 `https://api.deepseek.com`，可按需修改。
4. 粘贴 API Key 后保存（留空表示暂不配置，可稍后编辑补充）。
5. 切到「模型管理」点击「新增模型」，填写模型标识符（例如 `deepseek-chat`），保存。
6. 点击该模型的「测试连接」查看结果。

OpenAI 兼容服务同理：类型选「OpenAI 兼容」，Base URL 一般需要带 `/v1`（例如 `https://api.openai.com/v1`）。

### 连接测试说明

- 优先调用服务商的模型列表接口校验，此方式通常不产生费用。
- 服务商不支持模型列表时，才使用 `max_tokens=1` 的最小对话请求，**可能产生极少量 API 费用**。
- 返回结果包含响应时间、验证方式、错误分类：网络失败 / API Key 无效 / 模型不存在 / 余额或配额不足 / 格式不兼容 / 服务商错误。
- 本功能只做连通性验证，不会生成任何小说内容。

### API Key 如何加密与保存

- 使用 **Fernet（AES-128-CBC + HMAC）** 加密后写入 SQLite，数据库中不存在明文。
- 主密钥首次启动时自动生成到 `data/secrets/fernet.key`，仅保存在后端本地。
- 主密钥不通过任何接口返回，不写入日志，也不提交 Git（已在 `.gitignore` 中忽略）。
- 前端只能看到「是否已配置」与脱敏值（如 `sk-****abcd`）；API Key 不进入 localStorage。
- 修改密钥时才会要求重新输入；编辑时留空表示保持不变，也可显式「清除已保存的密钥」。

**备份与恢复**：

1. 备份：复制 `data/storyforge.db` 与 `data/secrets/fernet.key` 两个文件。
2. 恢复：把两个文件放回原路径（保持文件名不变），重启后端即可。
3. 若只恢复数据库而丢失主密钥，已保存的 API Key 无法解密，需要在界面中重新填写。

### P2 API 接口清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/providers` | 服务商列表（不含完整密钥） |
| POST | `/api/providers` | 新增服务商 |
| PUT | `/api/providers/{id}` | 修改服务商 |
| DELETE | `/api/providers/{id}` | 删除服务商（级联删除其模型） |
| GET | `/api/models` | 模型列表（可按 provider_id 过滤） |
| POST | `/api/models` | 新增模型 |
| PUT | `/api/models/{id}` | 修改模型 |
| DELETE | `/api/models/{id}` | 删除模型（相关任务分配自动置空） |
| POST | `/api/models/test` | 测试模型连接 |
| GET | `/api/model-settings` | 获取任务模型分配 |
| PUT | `/api/model-settings` | 保存任务模型分配 |

### 运行后端测试

在 `backend` 目录执行：

```bash
.venv\Scripts\python.exe -m pytest tests -q
```

测试使用临时数据库与临时密钥文件，不会影响真实配置。当前覆盖 P1、P2、P3.1、P3.2.1、P3.2.2，共 56 项用例。

## 小说项目管理（P3.1）

本阶段提供完整的小说项目管理，作为后续世界观、人物档案、剧情记忆与章节生成的数据基础。后续世界观能力已在 P3.2.1 中接入。

### 功能

- 小说列表：卡片网格（桌面端多列、手机端单列），支持按标题搜索、按创作状态筛选，按更新时间倒序。
- 新建 / 编辑：小说名称（必填）、副标题、简介、题材、多个标签、创作状态、目标字数（默认 100000）。
- 小说详情：标题、简介、题材/标签/状态、创建与更新时间、目标字数、当前字数（本阶段固定为 0）、世界观条目统计与入口；其余后续模块入口标记“尚未开放”。
- 删除：前端二次确认；删除默认小说时自动清空默认项目设置。
- 默认项目：一键设为默认，列表与详情均有明确标识，重启或刷新后由数据库恢复。
- Dashboard 联动：小说数量与累计字数为真实数据；最近创作展示最近更新的 5 部小说；无数据时显示空状态与创建入口。

### 数据结构

`novels` 表（启动时幂等创建，不会删除或重建已有数据库）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT | 主键，32 位 UUID |
| title | TEXT | 小说名称，必填，最长 100 |
| subtitle | TEXT | 副标题 |
| description | TEXT | 简介，最长 2000 |
| genre | TEXT | 题材 |
| tags | TEXT | 标签，JSON 数组，最多 10 个、单个最长 20 |
| status | TEXT | planning / writing / paused / completed |
| cover_color | TEXT | 封面颜色（#RRGGBB，可选） |
| target_word_count | INTEGER | 目标字数，1 ~ 10000000 |
| created_at | DATETIME | 创建时间（UTC） |
| updated_at | DATETIME | 更新时间（UTC） |

`app_settings` 表（键值配置）保存 `default_novel_id`。默认小说必须指向真实存在的小说；删除小说时同一事务内清理该设置；读取到失效引用时自动清除。

后续章节、人物、剧情记忆等表均以 `novel_id` 外键关联 `novels.id`，采用 `ON DELETE CASCADE` 随小说一并清理（这些表将在后续阶段创建）。世界观表已在 P3.2.1 中创建。

### P3.1 API 接口清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/novels` | 小说列表，支持 `search` 标题搜索、`status` 状态筛选 |
| POST | `/api/novels` | 创建小说 |
| GET | `/api/novels/{id}` | 小说详情（含统计数据） |
| PUT | `/api/novels/{id}` | 修改小说基本信息 |
| DELETE | `/api/novels/{id}` | 删除小说并清理默认设置 |
| PUT | `/api/novels/{id}/default` | 设为默认项目 |
| GET | `/api/novels/default` | 获取默认小说；未设置时返回 `null` |

### 手动创建第一部小说

1. 打开左侧导航「小说管理」，点击右上角「新建小说」。
2. 填写小说名称（必填），按需补充副标题、简介、题材、标签、创作状态和目标字数，点击「创建项目」。
3. 在小说卡片上点击「设为默认」，卡片出现「默认项目」徽标。
4. 点击卡片或「打开项目」进入详情页；刷新页面后默认项目仍然保留。

## 世界观管理（P3.2.1）

为每部小说建立独立、通用的世界观资料库。数据结构与分类完全由用户自定义，不限定小说题材（玄幻、仙侠、科幻、都市、历史、武侠、悬疑等均适用）。

本阶段暂不包含 AI 自动生成设定、AI 检索、关系图谱可视化与人物档案。

### 功能

- 每部小说拥有独立的世界观条目与分类，通过 `novel_id` 严格隔离，切换小说自动重新加载，不复用上一部小说的缓存。
- 分类管理：新建、重命名、修改说明与排序、删除空分类；分类名称在同一部小说内唯一。
- 设定条目：新建 / 编辑 / 删除 / 查看详情，支持名称、分类、简介、详细描述、多个标签、自定义键值属性、父级条目与排序。
- 检索：关键词搜索（匹配名称、简介、详细描述）+ 分类筛选 + 标签筛选 + 父级筛选；按排序值与更新时间排列。
- 统计：条目总数、分类数量、各分类条目数、最近更新时间；小说详情页同步显示世界观条目数。
- 页面布局：桌面端左侧分类导航 + 右侧条目网格；手机端（≤767px）纵向布局、分类导航横向滚动。

### 数据结构

两张表在启动时幂等创建（`CREATE TABLE IF NOT EXISTS`），不会删除或重建已有数据库，并启用 SQLite 外键约束。

`world_categories` 表：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT | 主键，32 位 UUID |
| novel_id | TEXT | 所属小说，外键 → `novels.id`，`ON DELETE CASCADE` |
| name | TEXT | 分类名称，必填，最长 50 |
| description | TEXT | 分类说明，最长 500 |
| sort_order | INTEGER | 排序值 |
| created_at / updated_at | DATETIME | 创建 / 更新时间（UTC） |

唯一约束：`UNIQUE(novel_id, name)`。

`world_entries` 表：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT | 主键，32 位 UUID |
| novel_id | TEXT | 所属小说，外键 → `novels.id`，`ON DELETE CASCADE` |
| category_id | TEXT | 分类，外键 → `world_categories.id`，`ON DELETE RESTRICT` |
| name | TEXT | 名称，必填，最长 100 |
| summary | TEXT | 简短介绍，最长 300 |
| content | TEXT | 详细描述（自然语言长文本，最长 20000 字） |
| tags | TEXT | 标签，JSON 数组（最多 10 个，单个最长 20） |
| attributes | TEXT | 自定义属性，JSON 对象（最多 30 项，键最长 50，值最长 500） |
| parent_id | TEXT | 父级条目，外键 → `world_entries.id`，`ON DELETE RESTRICT` |
| sort_order | INTEGER | 排序值 |
| created_at / updated_at | DATETIME | 创建 / 更新时间（UTC） |

**默认分类**：新建小说时自动初始化 7 个通用分类模板——地理与区域、势力与组织、世界规则、力量体系、历史与背景、文化与社会、其他，排序间隔 10。它们只是模板，可以自由改名、改说明、调排序或删除（需先迁移条目）。

**删除限制**：

- 分类下仍有条目时禁止删除，返回明确错误提示“请先将条目迁移到其他分类”。
- 父级条目仍有子条目时禁止删除，需先移动或删除子条目，不会静默级联删除整棵设定树。
- 删除小说时，同一事务内先解除父子引用、再删除条目与分类，最后删除小说，确保世界观数据随小说清理干净。

### P3.2.1 API 接口清单

所有接口均以小说 ID 为范围，访问其他小说的分类、条目或父级一律返回 404。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/novels/{novel_id}/world/entries` | 条目列表，支持 `search`、`category_id`、`tag`、`parent_id` |
| POST | `/api/novels/{novel_id}/world/entries` | 创建条目 |
| GET | `/api/novels/{novel_id}/world/entries/{entry_id}` | 条目详情 |
| PUT | `/api/novels/{novel_id}/world/entries/{entry_id}` | 修改条目（传 `parent_id: null` 可清空父级） |
| DELETE | `/api/novels/{novel_id}/world/entries/{entry_id}` | 删除条目（有子条目时返回 400） |
| GET | `/api/novels/{novel_id}/world/categories` | 分类列表（含各分类条目数） |
| POST | `/api/novels/{novel_id}/world/categories` | 新建分类 |
| PUT | `/api/novels/{novel_id}/world/categories/{category_id}` | 修改分类 |
| DELETE | `/api/novels/{novel_id}/world/categories/{category_id}` | 删除分类（有条目时返回 400） |
| GET | `/api/novels/{novel_id}/world/stats` | 世界观统计（条目数、分类数、各分类条目数、最近更新时间） |

### 使用说明

1. 进入「小说管理」，打开任意小说详情页。
2. 点击「世界观设定」卡片中的「进入世界观」（或直接访问 `/novels/{id}/world`）。
3. 点击「分类管理」确认或调整分类（新小说已自动带 7 个默认分类）。
4. 点击「新建设定」，填写名称、分类，按需补充简介、详细描述、标签、自定义属性、父级条目与排序。
5. 在左侧分类导航筛选，或用搜索框检索；点击卡片查看详情，可编辑或删除。

`world_entries.parent_id` 用于表达树形层级（例如“青木府城”的父级是“东部区域”）。它在 P3.2.2 中继续保持独立，不与关系表互相替代；条目之间的任意关联统一放入 `world_relations`，不写入 `attributes`。

## 世界观关系管理（P3.2.2）

为世界观条目建立**有向**关系网络。关系与 `parent_id` 的树形层级相互独立，例如“青木府城”既可以有父级“东部区域”，也可以通过关系被“远东皇朝”管辖，并与“北明府城”建立贸易关系。

本阶段不包含 AI 自动建立关系、AI 自动补充世界观与 AI 检索。

### 功能

- 关系方向：`A → 管辖 → B` 与 `B → 管辖 → A` 是两条独立关系，不会被视为同一条；联盟、敌对、贸易等双向语义可由用户分别创建，或勾选“同时创建反向关系”一次性建立两条。
- 关系类型：内置建议值“属于 / 管辖 / 位于 / 控制 / 联盟 / 敌对 / 贸易 / 师承 / 起源于 / 依赖 / 克制 / 其他”，数据库不做枚举限制，用户可输入任意自定义类型。
- 条目详情联动：详情弹窗展示该条目的正向（→）与反向（←）关系，包含关系类型、关联对象名称与分类、关系描述；点击关联对象可切换到对应条目详情；支持新建、编辑、删除（删除前二次确认）。
- 关系管理页：`/novels/{id}/world/relations`，展示起点、关系类型、终点、描述、修改时间与操作，支持按关系类型筛选和按描述关键词搜索。
- 关系网络视图：节点代表条目、连线代表关系，带方向箭头与关系类型标签；支持按分类筛选节点、按关系类型筛选连线；点击节点查看条目、点击连线查看关系详情；不同分类使用不同颜色并在图例中标注。图谱使用原生 SVG 自绘（圆形布局），未引入新的图形库。
- 手机端：关系列表是图谱的等价替代视图；390px 下列表与图谱均无横向溢出，图谱宽度自适应。
- 世界观总览：世界观页显示条目数、分类数、关系数；没有关系时展示空状态与“去创建关系”引导。
- 数据隔离：所有关系属于同一本小说，起点与终点必须是当前小说内的条目；切换小说时清空旧关系数据并从后端重新加载。

### 数据结构

`world_relations` 表（启动时幂等创建，不删除或重建已有数据库）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT | 主键，32 位 UUID |
| novel_id | TEXT | 所属小说，外键 → `novels.id`，`ON DELETE CASCADE` |
| source_entry_id | TEXT | 起点条目，外键 → `world_entries.id`，`ON DELETE CASCADE` |
| target_entry_id | TEXT | 终点条目，外键 → `world_entries.id`，`ON DELETE CASCADE` |
| relation_type | TEXT | 关系类型，必填，最长 50，允许自定义 |
| description | TEXT | 关系描述，最长 2000 |
| created_at / updated_at | DATETIME | 创建 / 更新时间（UTC） |

约束与索引：

- `UNIQUE(novel_id, source_entry_id, target_entry_id, relation_type)`：同一小说中相同起点、终点与类型的重复关系被拒绝。
- `CHECK(source_entry_id <> target_entry_id)`：起点与终点不能相同。
- 起点与终点必须属于同一本小说，由服务层校验（跨小说按“不存在”返回 404）。
- 索引：`(novel_id, source_entry_id)`、`(novel_id, target_entry_id)`、`(novel_id, relation_type)`、`(novel_id, created_at DESC)`。
- 删除任一端点条目时关系自动级联清理；删除小说时先清理关系，再清理条目与分类。

### P3.2.2 API 接口清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/novels/{novel_id}/world/relations` | 关系列表，支持 `relation_type`、`source_entry_id`、`target_entry_id`、`search`（描述关键词） |
| POST | `/api/novels/{novel_id}/world/relations` | 创建关系（校验两端存在、同小说、起点≠终点、类型非空、不可重复） |
| GET | `/api/novels/{novel_id}/world/relations/{relation_id}` | 关系详情（含两端条目摘要） |
| PUT | `/api/novels/{novel_id}/world/relations/{relation_id}` | 修改起点、终点、类型或描述，并重新校验 |
| DELETE | `/api/novels/{novel_id}/world/relations/{relation_id}` | 删除关系，不删除两端条目 |
| GET | `/api/novels/{novel_id}/world/entries/{entry_id}/relations` | 条目的正向 `outgoing` 与反向 `incoming` 关系，每条带 `direction` |
| GET | `/api/novels/{novel_id}/world/stats` | 在原统计基础上新增关系总数、关系类型数量、各类型关系数量、关联条目数量 |

### 使用说明

1. 进入某部小说的世界观管理页，在条目详情中选择「关联关系」区域的「新建关系」。
2. 选择起点与终点（下拉可搜索），选择或输入关系类型，填写关系描述；需要双向关系时勾选“同时创建反向关系”。
3. 需要集中管理时点击页面右上角「关系管理」，在列表页筛选、编辑或删除关系；切换到「关系网络」可查看图谱。
4. 图谱中节点颜色代表分类，箭头方向代表关系方向，连线上的文字为关系类型；点击节点或连线查看详情。

## 手机局域网访问（安卓）

> 前提：手机与电脑连接**同一个 Wi-Fi**。本功能仅限可信家庭/办公局域网，请勿暴露到公网。

### 第 1 步：查询电脑局域网 IP

电脑上按 `Win+R` 输入 `cmd` 回车，输入：

```
ipconfig
```

找到当前网络（一般是"无线局域网适配器 WLAN"）下的 **IPv4 地址**，例如 `192.168.1.19`。

### 第 2 步：放行 Windows 防火墙端口

首次启动服务时，Windows 可能弹出"网络访问"提示，请勾选**专用网络**并允许。

如果没有弹窗或手机仍无法访问，手动放行 **5173（前端）** 和 **8000（后端）** 端口：

1. 开始菜单搜索并打开"**高级安全 Windows Defender 防火墙**"。
2. 左侧点击"**入站规则**"，右侧点击"**新建规则**"。
3. 选择"**端口**" → 下一步 → 选择"TCP"，特定本地端口填 `5173, 8000` → 下一步。
4. 选择"**允许连接**" → 下一步 → 勾选"**专用**"（不要勾"公用"）→ 下一步。
5. 名称填 `StoryForge` → 完成。

### 第 3 步：手机浏览器访问

安卓手机浏览器（Chrome / Edge / Via 等）地址栏输入：

```
http://<电脑局域网IP>:5173
```

例如：`http://192.168.1.19:5173`

前端会自动把 API 请求指向同一台电脑的 8000 端口，无需额外配置。手机端会自动切换为抽屉式导航布局。

## 配置说明

复制根目录 `.env.example` 为 `.env` 可按需修改配置；不配置也有合理默认值：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | 后端监听地址，`0.0.0.0` 允许局域网访问 |
| `PORT` | `8000` | 后端端口 |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 允许跨域的前端来源；局域网私有网段已自动放行 |
| `DATABASE_PATH` | `data/storyforge.db` | SQLite 数据库文件位置 |
| `SECRET_KEY_FILE` | `data/secrets/fernet.key` | API Key 加密主密钥文件位置 |
| `MODEL_REQUEST_TIMEOUT` | `20` | 调用第三方模型接口的超时（秒） |
| `ALLOW_PRIVATE_ENDPOINTS` | `false` | 是否允许模型 Base URL 指向本机/内网地址（接入本地部署模型时才需要开启） |

前端默认自动推导后端地址（与访问前端所用 IP 相同、端口 8000）。仅当后端在另一台机器时，才需要在 `frontend/.env` 中设置 `VITE_API_BASE_URL`。

**安全约定**：API Key 只在后端加密存储，前端不保存任何密钥；`.env`、数据库与加密主密钥均已加入 `.gitignore`。

**SSRF 防护**：Base URL 仅允许 http/https，默认禁止指向 `localhost`、私有网段、链路本地等地址；确需连接本地模型时，可在 `.env` 中设置 `ALLOW_PRIVATE_ENDPOINTS=true` 显式放开。请勿将服务暴露到公网。

## 常见问题排查

**1. 双击脚本提示"未检测到 Python"**
未安装 Python 或未加入 PATH。重新安装并勾选 "Add python.exe to PATH"，装好后重开脚本。

**2. 双击脚本提示"未检测到 Node.js"**
安装 Node.js 18+（https://nodejs.org/ ），装好后重开脚本。

**3. 依赖安装失败**
多为网络问题，重试即可。npm 可换镜像：在 `frontend` 目录执行 `npm install --registry=https://registry.npmmirror.com`。

**4. 电脑能打开，手机打不开**
- 确认手机与电脑在**同一 Wi-Fi**（不要一个用 5G 一个用 2.4G 访客网络）。
- 确认 IP 没输错，且是 `http://` 开头、端口 5173。
- 按上文第 2 步检查防火墙入站规则。
- 部分路由器开启了"AP 隔离"，需在路由器设置中关闭。

**5. 手机能打开页面，但提示"无法连接后端服务"**
后端（8000 端口）没启动或被防火墙拦截。确认 `start_backend.bat` 窗口还在运行，并检查防火墙是否放行了 8000 端口。

**6. 端口被占用**
8000 或 5173 被其他程序占用时，关闭对应程序；或修改 `.env` 中的 `PORT` 与 `frontend/package.json` 中 `dev` 脚本的 `--port`。

**7. 杀毒软件拦截**
部分杀毒软件会拦截本地服务，将项目目录加入信任列表后重试。

**8. 添加服务商时提示"默认禁止访问本机地址"或"内网 IP"**
这是 SSRF 防护的默认行为。若要接入本机部署的模型服务（如本地推理服务），在根目录 `.env` 中设置 `ALLOW_PRIVATE_ENDPOINTS=true` 并重启后端。

**9. 测试连接提示"API Key 无法解密"**
加密主密钥（`data/secrets/fernet.key`）被删除或替换。请重新在界面填写 API Key；如需恢复旧数据，请使用之前备份的主密钥文件。

**10. 修改了模型配置但页面没更新**
确认后端仍在运行（设置页「默认设置」中显示"已连接"），可刷新页面或点击"重试"。
