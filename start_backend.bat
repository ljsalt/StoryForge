@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================
echo   StoryForge 后端启动脚本
echo ========================================
echo.

REM ---- 检查 Python：优先 3.12，其次默认 python ----
set "PY_CMD="
py -3.12 --version >nul 2>&1 && set "PY_CMD=py -3.12"
if not defined PY_CMD (
    python --version >nul 2>&1 && set "PY_CMD=python"
)

if not defined PY_CMD (
    echo [错误] 未检测到 Python。
    echo.
    echo 请先安装 Python 3.12 或更高版本：
    echo   https://www.python.org/downloads/
    echo 安装时请勾选 "Add python.exe to PATH"。
    echo.
    pause
    exit /b 1
)

echo [信息] 检测到 Python：
%PY_CMD% --version
if "%PY_CMD%"=="python" (
    echo [提示] 未找到 Python 3.12，正在使用默认 python。建议使用 Python 3.12+。
)
echo.

REM ---- 首次运行：创建虚拟环境并安装依赖 ----
if not exist "backend\.venv\Scripts\python.exe" (
    echo [信息] 首次运行，正在创建虚拟环境...
    %PY_CMD% -m venv backend\.venv
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败，请检查 Python 安装。
        pause
        exit /b 1
    )
    echo [信息] 正在安装后端依赖...
    backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络连接后重新运行本脚本。
        pause
        exit /b 1
    )
)

echo.
echo [信息] 后端服务即将启动：
echo   - 本机访问：  http://localhost:8000
echo   - 局域网访问：http://^<电脑局域网IP^>:8000
echo   - 接口文档：  http://localhost:8000/docs
echo.
echo [提示] 查询电脑局域网IP：按 Win+R 输入 cmd 回车，再输入 ipconfig，查看 "IPv4 地址"。
echo [提示] 停止服务：按 Ctrl+C 或直接关闭本窗口。
echo.

cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo [信息] 后端服务已停止。
pause
