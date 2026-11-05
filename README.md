# StoryForge

本地优先的 AI 中文长篇小说创作工作室。

> 当前版本：0.1.0-P1（项目初始化与基础访问）

## 项目介绍

StoryForge 是一个支持多模型 API 的中文长篇小说创作系统，采用前后端分离架构，数据保存在本地。

整体规划（分阶段实施，**当前仅完成 P1**）：

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| P1 | 项目初始化：基础界面、后端服务、电脑与手机局域网访问 | ✅ 当前阶段 |
| P2 | 小说/人物/预设管理，多模型接入（DeepSeek 及 OpenAI 兼容 API），AI 剧情规划与章节生成 | 未开始 |
| P3 | 半自主创作：AI 自主推进剧情，重大节点暂停并询问 | 未开始 |

## 技术栈

- **前端**：Vue 3、TypeScript、Vite、Naive UI、Vue Router、Pinia、Axios
- **后端**：Python 3.12、FastAPI、Uvicorn
- **数据库**：SQLite（本阶段暂不建业务表）
- **其他**：Git、npm

## 目录结构

```
StoryForge/
├── frontend/                # 前端（Vue 3 + Vite）
│   ├── src/
│   │   ├── api/             # API 地址统一配置与接口封装
│   │   ├── components/      # 公共组件
│   │   ├── layouts/         # 页面布局（含响应式导航）
│   │   ├── router/          # 路由
│   │   ├── stores/          # Pinia 状态
│   │   ├── views/           # 页面（首页/小说/人物/预设/设置）
│   │   ├── App.vue
│   │   └── main.ts
│   └── package.json
├── backend/                 # 后端（FastAPI）
│   ├── app/
│   │   ├── api/             # 路由
│   │   ├── core/            # 配置
│   │   ├── models/          # 数据模型（预留）
│   │   ├── services/        # 业务服务（预留）
│   │   └── main.py          # 应用入口
│   └── requirements.txt
├── data/
│   ├── novels/              # 小说数据（本地保存，不入库）
│   └── backups/             # 备份数据（不入库）
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

前端默认自动推导后端地址（与访问前端所用 IP 相同、端口 8000）。仅当后端在另一台机器时，才需要在 `frontend/.env` 中设置 `VITE_API_BASE_URL`。

**安全约定**：API Key 等敏感信息只允许放在根目录 `.env`（已加入 .gitignore），绝不写入前端代码。

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
