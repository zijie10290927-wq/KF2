# -*- coding: utf-8 -*-
"""AI 智能客服后端 API 审查测试脚本"""
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = "http://localhost:8000/api/v1"
OUT = {}


def req(method, path, body=None, token=None):
    url = (BASE if path.startswith("/") else BASE + "/") + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            try:
                j = json.loads(raw)
            except Exception:
                j = {"_raw": raw}
            return resp.status, j
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            j = json.loads(raw)
        except Exception:
            j = {"_raw": raw}
        return e.code, j


def sec(n, label, resp):
    code, body = resp
    print(f"\n=== {n}. {label} ===")
    print(f"HTTP {code}")
    print(json.dumps(body, ensure_ascii=False, indent=2)[:3000])
    OUT[n] = {"label": label, "code": code, "body": body}
    return code, body


def main():
    # 1. health
    sec(1, "GET /health", (200, json.loads(urllib.request.urlopen(
        "http://localhost:8000/health", timeout=10).read().decode("utf-8"))))

    # 2. login
    c2, b2 = sec(2, "POST /auth/login (admin/admin123)",
                 req("POST", "/auth/login", {"username": "admin", "password": "admin123"}))
    token = None
    if b2.get("code") == 0 and isinstance(b2.get("data"), dict):
        token = b2["data"].get("access_token")
        user_info = b2["data"].get("user_info")
        user_field = b2["data"].get("user")
        print(f"  -> token length: {len(token) if token else 0}")
        print(f"  -> has user_info (backend key): {user_info is not None}")
        print(f"  -> has user (frontend expects): {user_field is not None}")
    if not token:
        print("LOGIN FAILED, ABORT")
        return 1

    # 3. /auth/me
    c3, b3 = sec(3, "GET /auth/me", req("GET", "/auth/me", token=token))
    if b3.get("code") == 0 and isinstance(b3.get("data"), dict):
        print(f"  -> keys in me data: {list(b3['data'].keys())}")

    # 4. create session
    c4, b4 = sec(4, "POST /chat/sessions {title}",
                 req("POST", "/chat/sessions", {"title": "审查测试会话"}, token=token))
    sid = None
    if b4.get("code") == 0 and isinstance(b4.get("data"), dict):
        sid = b4["data"].get("session_id")
        print(f"  -> session_id: {sid}")

    # 5. session list
    sec(5, "GET /chat/sessions", req("GET", "/chat/sessions", token=token))

    # 6. messages
    if sid:
        sec(6, f"GET /chat/sessions/{sid}/messages",
            req("GET", f"/chat/sessions/{sid}/messages", token=token))

    # 7. transfer-human
    sec(7, "POST /chat/transfer-human",
        req("POST", "/chat/transfer-human",
            {"reason": "审查测试转人工", "session_id": sid or ""}, token=token))

    # 8. admin config
    sec(8, "GET /admin/config/fallback",
        req("GET", "/admin/config/fallback", token=token))

    # 9. knowledge docs
    sec(9, "GET /knowledge/docs",
        req("GET", "/knowledge/docs", token=token))

    # 10. admin models
    sec(10, "GET /admin/models",
        req("GET", "/admin/models", token=token))

    # 11. admin users
    sec(11, "GET /admin/users",
        req("GET", "/admin/users", token=token))

    # 12. openapi size
    with urllib.request.urlopen("http://localhost:8000/openapi.json", timeout=10) as r:
        oa_size = len(r.read())
    print(f"\n=== 12. /openapi.json size: {oa_size} bytes ===")
    OUT[12] = {"label": "openapi.json", "size": oa_size}

    # 13. /auth/me 无 token (expect 401)
    sec(13, "GET /auth/me (no token, expect 401/unauth)",
        req("GET", "/auth/me"))

    # 14. login wrong password
    sec(14, "POST /auth/login wrong password",
        req("POST", "/auth/login", {"username": "admin", "password": "wrongpass"}))

    # 15. sessions 无 token (expect 401)
    sec(15, "GET /chat/sessions (no token, expect 401/unauth)",
        req("GET", "/chat/sessions"))

    # 16. /auth/register
    sec(16, "POST /auth/register (test_user_xx / 123456)",
        req("POST", "/auth/register",
            {"username": "test_user_review", "password": "123456", "role": "user"}))

    # 17. 登录刚刚注册的用户
    sec(17, "POST /auth/login as test_user_review",
        req("POST", "/auth/login", {"username": "test_user_review", "password": "123456"}))

    # save state
    Path("test-state.json").write_text(
        json.dumps({"token": token, "sid": sid, "results": OUT}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print("\nDONE -> test-state.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
