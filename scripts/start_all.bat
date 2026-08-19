@echo off
REM 一键启动前后端服务（同时启动两个窗口）
REM 双击本文件即可执行

setlocal
set "ROOT=c:\Users\admin\Desktop\ZNKF\ZNKF\ZNKF\a1\KF2"
set "BACKEND=%ROOT%\ai-customer-backend"
set "FRONTEND=%ROOT%\ai-customer-frontend"

REM 解锁 PowerShell 执行策略（仅当前用户，避免 .ps1 包装脚本被阻止）
powershell.exe -NoProfile -Command "Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force" 2>nul
reg add "HKCU\SOFTWARE\Microsoft\PowerShell\1\ShellIds\Microsoft.PowerShell" /v ExecutionPolicy /t REG_SZ /d RemoteSigned /f >nul 2>&1

echo [1/2] Starting backend on http://localhost:8000 ...
start "AI-Backend" cmd /k "cd /d "%BACKEND%" && call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

REM 等待后端启动
timeout /t 5 /nobreak >nul

echo [2/2] Starting frontend on http://localhost:5173 ...
start "AI-Frontend" cmd /k "cd /d "%FRONTEND%" && call npm run dev"

echo.
echo ============================================================
echo 服务启动中：
echo   后端: http://localhost:8000  (新增窗口查看日志)
echo   前端: http://localhost:5173  (新增窗口查看日志)
echo.
echo 等待 ~10 秒后浏览器访问 http://localhost:5173
echo ============================================================
echo.
echo 本窗口可以关闭。后端/前端的 cmd 窗口保留运行。
timeout /t 10 /nobreak >nul
start http://localhost:5173
endlocal
