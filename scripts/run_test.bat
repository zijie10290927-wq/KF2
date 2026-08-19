@echo off
chcp 65001 >nul
cd /d "c:UsersadminDesktopZNKFZNKFZNKFa1KF2"
echo === Clearing __pycache__ ===
for /d /r "ai-customer-backendapp" %%d in (__pycache__) do rmdir /s /q "%%d" 2>nul
echo === Starting backend on port 8000 ===
cd ai-customer-backend
start "BACKEND_8000" /MIN python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
cd ..
echo === Wait 8s for backend ===
ping 127.0.0.1 -n 9 >nul
echo === Now running test_3_errors.py ===
python scripts	est_3_errors.py
echo === Test script exit code=%errorlevel% ===
