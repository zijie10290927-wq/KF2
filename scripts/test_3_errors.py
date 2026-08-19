"""快速验证：测试之前报错的 3 个端点（chat/stream、knowledge/upload、knowledge/docs/:id）。"""
import base64
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8000/api/v1"
TOKEN = None  # 登录后填充


def request(method, path, data=None, headers=None, timeout=30, accept_status=(200, 201)):
    url = f"{BASE}{path}"
    h = {"Content-Type": "application/json"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        elif isinstance(data, bytes):
            body = data
            h.pop("Content-Type", None)
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            raw = resp.read()
            elapsed = time.time() - t0
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                payload = raw.decode("utf-8", errors="ignore")[:500]
            return status, elapsed, payload
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        raw = e.read()
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            payload = raw.decode("utf-8", errors="ignore")[:500]
        return e.code, elapsed, payload
    except Exception as e:
        elapsed = time.time() - t0
        return 0, elapsed, {"error": str(e)}


def login():
    global TOKEN
    s, t, d = request("POST", "/auth/login", {"username": "admin", "password": "admin123"})
    ok = s == 200 and isinstance(d, dict) and d.get("code") == 0
    if ok:
        TOKEN = d.get("data", {}).get("access_token") or d.get("data", {}).get("token")
        print(f"[OK] 登录  status={s}  t={t:.2f}s  token_len={len(TOKEN or '')}")
        return True
    print(f"[FAIL] 登录  status={s}  t={t:.2f}s  resp={d}")
    return False


def test_health():
    # 健康检查不走 /api/v1
    try:
        t0 = time.time()
        with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as resp:
            s = resp.getcode()
            t = time.time() - t0
            print(f"[OK] /health  status={s}  t={t:.2f}s")
            return True
    except Exception as e:
        print(f"[FAIL] /health: {e}")
        return False


def test_knowledge_upload():
    """上传一个极小的 TXT 文档测试 upload 端点（优先 requests，退化到手工 multipart）。"""
    sample_text = "AI 出图产品功能说明文档：\n1. 支持文字转图片\n2. 支持风格迁移\n3. 支持图片高清放大\n"
    TOKEN_H = TOKEN
    BASE_URL = BASE
    try:
        import requests  # type: ignore
        files = {
            "file": ("hello.txt", sample_text.encode("utf-8"), "text/plain"),
        }
        data = {"category": "产品文档", "chunk_size": "0", "overlap": "0"}
        headers = {}
        if TOKEN_H:
            headers["Authorization"] = f"Bearer {TOKEN_H}"
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/admin/knowledge/upload", data=data, files=files, headers=headers, timeout=60)
        t = time.time() - t0
        s = r.status_code
        try:
            d = r.json()
        except Exception:
            d = r.text[:500]
    except Exception as import_err:
        # 退化到手工构造 multipart (保留 fallback)
        sample = sample_text.encode("utf-8")
        boundary = "----TestBoundary" + str(int(time.time() * 1000))
        pre = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="category"\r\n'
            "\r\n"
            "\u4ea7\u54c1\u6587\u6863\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="chunk_size"\r\n'
            "\r\n"
            "0\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="overlap"\r\n'
            "\r\n"
            "0\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="hello.txt"\r\n'
            "Content-Type: text/plain\r\n"
            "\r\n"
        ).encode("utf-8")
        post = f"\r\n--{boundary}--\r\n".encode("utf-8")
        body = pre + sample + post
        s, t, d = request(
            "POST", "/admin/knowledge/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            timeout=60,
        )
        print(f"       (fallback multipart, import_err={import_err})")
    ok = s == 200 and isinstance(d, dict) and d.get("code") == 0
    doc_id = None
    if ok:
        doc_id = d.get("data", {}).get("doc_id")
    status = "OK" if ok else "FAIL"
    print(f"[{status}] /admin/knowledge/upload  status={s}  t={t:.2f}s  doc_id={doc_id}")
    if not ok:
        print(f"       resp={d}")
    return ok, doc_id


def test_knowledge_get_doc(doc_id):
    s, t, d = request("GET", f"/admin/knowledge/docs/{doc_id}", timeout=15)
    ok = s == 200 and isinstance(d, dict) and d.get("code") == 0
    status = "OK" if ok else "FAIL"
    info = ""
    if ok and isinstance(d.get("data"), dict):
        info = f"  filename={d['data'].get('filename')} status={d['data'].get('status')}"
    print(f"[{status}] /admin/knowledge/docs/:id  status={s}  t={t:.2f}s{info}")
    if not ok:
        print(f"       resp={d}")
    return ok


def test_chat_stream():
    """测试 /chat/stream SSE：发送消息并读取至少一个 answer/done 事件。"""
    # 先确保有 session
    s, t, d = request("POST", "/chat/sessions", {"title": "测试对话"})
    ok1 = s == 200 and isinstance(d, dict) and d.get("code") == 0
    if not ok1:
        print(f"[FAIL] /chat/sessions  status={s}  t={t:.2f}s  resp={d}")
        return False
    session_id = d["data"]["session_id"]

    # 发起 SSE (POST + accept: text/event-stream)
    url = f"{BASE}/chat/stream"
    body = json.dumps(
        {"session_id": session_id, "message": "这个产品多少钱？有没有试用版？", "history": []},
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    got_answer = 0
    got_done = False
    got_error = None
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            elapsed_conn = time.time() - t0
            status_code = resp.getcode()
            if status_code != 200:
                print(f"[FAIL] /chat/stream HTTP {status_code}  t={elapsed_conn:.2f}s")
                return False
            buffer = b""
            total_tokens = 0
            # 最大 50 秒读完
            end_at = time.time() + 50
            while time.time() < end_at:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buffer += chunk
                # 按 SSE \n\n 分隔
                while b"\n\n" in buffer:
                    seg, buffer = buffer.split(b"\n\n", 1)
                    seg_text = seg.decode("utf-8", errors="ignore")
                    for line in seg_text.split("\n"):
                        if line.startswith("data:"):
                            json_str = line[5:].strip()
                            if not json_str:
                                continue
                            try:
                                evt = json.loads(json_str)
                                et = evt.get("type") or evt.get("event")
                                if et == "answer":
                                    content = evt.get("content", "")
                                    if content:
                                        total_tokens += len(content)
                                        got_answer += 1
                                elif et == "done":
                                    got_done = True
                                elif et == "error":
                                    got_error = evt.get("message")
                            except Exception:
                                pass
            total_t = time.time() - t0
            # 判定：至少拿到 1 个 answer 或 done
            ok = (got_answer > 0 or got_done) and got_error is None
            status = "OK" if ok else "FAIL"
            print(
                f"[{status}] /chat/stream  status=200  t={total_t:.2f}s"
                f"  answer_chunks={got_answer}  done={got_done}"
                f"  received_chars={total_tokens}  error={got_error}"
            )
            return ok
    except Exception as e:
        total_t = time.time() - t0
        print(f"[FAIL] /chat/stream  t={total_t:.2f}s  err={e}")
        return False


def main():
    print("=" * 60)
    print("验证修复：3 条报错日志相关端点测试")
    print("=" * 60)
    ok = test_health()
    if not ok:
        print("后端服务未启动，请先启动 uvicorn (python -m uvicorn app.main:app --port 8000)")
        sys.exit(1)

    login_ok = login()
    if not login_ok:
        sys.exit(1)

    results = []

    # 1. 知识库上传
    upload_ok, doc_id = test_knowledge_upload()
    results.append(("knowledge/upload", upload_ok))

    # 2. 知识库文档详情
    get_ok = False
    if upload_ok and doc_id:
        # 等一下后台处理（0.5s 即可，mock 模式快）
        time.sleep(1)
        get_ok = test_knowledge_get_doc(doc_id)
        results.append(("knowledge/docs/:id", get_ok))
    else:
        print("[SKIP] /admin/knowledge/docs/:id  （upload 失败，跳过）")
        results.append(("knowledge/docs/:id", False))

    # 3. /chat/stream
    stream_ok = test_chat_stream()
    results.append(("chat/stream", stream_ok))

    print()
    print("=" * 60)
    print("总结")
    print("=" * 60)
    all_ok = True
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'}  {name}")
        if not ok:
            all_ok = False
    print()
    if all_ok:
        print("🎉 3 条日志对应的 3 个端点全部通过 ✅")
    else:
        print("⚠️  仍有端点未通过，请检查后端日志。")
    sys.exit(0 if all_ok else 2)


if __name__ == "__main__":
    main()
