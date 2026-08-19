"""入口脚本：清缓存 → 杀旧后端 → 起新后端（新 py 会用新 minio degrade）→ 健康检查 → 运行 test_3_errors.py。

不依赖 PowerShell 执行策略（只是 Python 本身用 sys/os）。
"""
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACK = ROOT / "ai-customer-backend"


def netstat_listeners(port=8000):
    out = subprocess.check_output(["netstat", "-ano"], text=True)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if f":{port}" in parts[1] and parts[3] == "LISTENING":
            return int(parts[4])
    return None


def kill_pid(pid):
    try:
        subprocess.check_call(["taskkill", "/F", "/PID", str(pid)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def clear_pycache(root: pathlib.Path):
    for p in root.rglob("__pycache__"):
        try:
            shutil.rmtree(p)
        except Exception:
            pass


def start_backend_detached(log_path: pathlib.Path) -> int:
    os.chdir(BACK)
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_NO_WINDOW = 0x08000000
    python_exe = sys.executable
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "ab")
    popen = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=log_file, stderr=log_file, cwd=str(BACK),
        creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
    )
    return popen.pid


def health_ok(timeout_s=30):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as r:
                if r.getcode() == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    print("[1/5] 清理 __pycache__...")
    clear_pycache(BACK)

    print("[2/5] 杀掉 8000 端口上的旧后端...")
    pid = netstat_listeners(8000)
    if pid:
        print(f"   - 监听进程 PID={pid}，终止中...")
        kill_pid(pid)
        time.sleep(1.5)

    print("[3/5] 启动新后端...")
    log_path = ROOT / "scripts" / "backend_8000_restart.log"
    if log_path.exists():
        try:
            log_path.unlink()
        except Exception:
            pass
    new_pid = start_backend_detached(log_path)
    print(f"   - 启动完成, PID={new_pid}，日志在 {log_path}")

    print("[4/5] 等待后端健康 (最多 40s)...")
    ok = health_ok(timeout_s=40)
    if not ok:
        print("   ⚠️  健康检查超时，仍会尝试跑测试")
    else:
        print("   ✅ 健康检查通过")

    print("[5/5] 运行 test_3_errors.py...")
    print()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    p = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "test_3_errors.py")],
        cwd=str(ROOT),
        env=env,
    )
    p.wait()
    sys.exit(p.returncode)


if __name__ == "__main__":
    main()
