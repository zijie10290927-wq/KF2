@echo off
REM 解锁 PowerShell 执行策略 + 启动后端服务
REM 在 TraeCode 终端中执行：scripts\unlock_and_start.bat

echo [1/2] Setting PowerShell ExecutionPolicy to RemoteSigned (CurrentUser)...
powershell.exe -ExecutionPolicy Bypass -NoProfile -Command "Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force"
if %errorlevel% neq 0 (
    echo Failed to set ExecutionPolicy. Trying reg import...
    reg add "HKCU\SOFTWARE\Microsoft\PowerShell\1\ShellIds\Microsoft.PowerShell" /v ExecutionPolicy /t REG_SZ /d RemoteSigned /f
)

echo.
echo [2/2] Starting backend on http://localhost:8000 ...
cd /d "c:\Users\admin\Desktop\ZNKF\ZNKF\ZNKF\a1\KF2\ai-customer-backend"
call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
