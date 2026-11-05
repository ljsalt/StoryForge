@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================
echo   StoryForge 前端启动脚本
echo ========================================
echo.

REM ---- 检查 Node.js ----
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Node.js。
    echo.
    echo 请先安装 Node.js 18 或更高版本：
    echo   https://nodejs.org/
    echo.
    pause
    exit /b 1
)

echo [信息] 检测到 Node.js：
node --version
echo.

REM ---- 首次运行：安装依赖 ----
if not exist "frontend\node_modules" (
    echo [信息] 首次运行，正在安装前端依赖（可能需要几分钟）...
    cd frontend
    call npm install
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络连接后重新运行本脚本。
        pause
        exit /b 1
    )
    cd ..
)

echo.
echo [信息] 前端服务即将启动：
echo   - 本机访问：http://localhost:5173
echo   - 手机访问：手机与电脑连接同一 Wi-Fi 后，
echo     浏览器打开 http://^<电脑局域网IP^>:5173
echo.
echo [提示] 查询电脑局域网IP：按 Win+R 输入 cmd 回车，再输入 ipconfig，查看 "IPv4 地址"。
echo [提示] 若手机无法访问，请在 Windows 防火墙中允许 5173 和 8000 端口（详见 README）。
echo [提示] 停止服务：按 Ctrl+C 或直接关闭本窗口。
echo.

cd frontend
call npm run dev

echo.
echo [信息] 前端服务已停止。
pause
