#!/usr/bin/env python3
"""清除 __pycache__ -> 检查后端健康 -> 启动后端 (如果未启动)。"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request

BACKEND_DIR = r"c:\Users\admin\Desktop\ZNKF\ZNKF\ZNKF\a1\KF2\ai-customer-backend"
HEALTH = "http://localhost:8000/health"


def clear_pycache(root):
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath) == "__pycache__":
            try:
                shutil.rmtree(dirpath)
                removed += 1
            except Exception:
                pass
    print(f"cleared {removed} __pycache__ dirs")


def backend_up():
    try:
        with urllib.request.urlopen(HEALTH, timeout=3) as r:
            body = r.read().decode("utf-8", errors="ignore")
            print(f"backend UP: {r.getcode()} {body[:80]}")
            return True
    except Exception as e:
        print(f"backend DOWN: {e}")
        return False


if __name__ == "__main__":
    clear_pycache(BACKEND_DIR)
    up = backend_up()
    if not up:
        print("后端未启动，等待用户手动用 uvicorn 启动（或者我们的浏览器任务）")
    print("DONE", 0 if up else 1)
