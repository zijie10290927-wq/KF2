@echo off
REM 启动后端服务（绕过 PowerShell 执行策略限制）
cd /d "c:\Users\admin\Desktop\ZNKF\ZNKF\ZNKF\a1\KF2\ai-customer-backend"
call .venv\Scripts\activate.bat
echo Starting backend on http://localhost:8000 ...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
