import sys
import json
import time
import requests

BASE_URL = "http://localhost:8000"

def test_rag():
    # 1. Login
    print("1. Login...")
    login_resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    login_data = login_resp.json()
    if login_data.get("code") != 0:
        print(f"   FAIL: Login failed: {login_data}")
        return
    token = login_data["data"]["access_token"]
    print(f"   OK: Token acquired (len={len(token)})")

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Check knowledge docs
    print("\n2. Check knowledge docs...")
    resp = requests.get(f"{BASE_URL}/api/v1/admin/knowledge/docs?page=1&page_size=50", headers=headers)
    data = resp.json()
    docs = data.get("data", {}).get("list", [])
    print(f"   Total docs: {data.get('data', {}).get('total', 0)}")
    for doc in docs[:5]:
        print(f"   - [{doc['file_type']}] {doc['filename']} chunks={doc['chunk_count']} status={doc['status']}")

    # 3. Create chat session
    print("\n3. Create chat session...")
    resp = requests.post(f"{BASE_URL}/api/v1/chat/sessions", json={"title": "RAG测试"}, headers=headers)
    session_data = resp.json()
    if session_data.get("code") != 0:
        print(f"   FAIL: {session_data}")
        return
    session_id = session_data["data"]["id"]
    print(f"   OK: Session created (id={session_id})")

    # 4. Send chat message (RAG test)
    print("\n4. Send chat message (RAG query)...")
    question = "产品退款政策是什么？"
    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/{session_id}/messages",
        headers=headers,
        json={"content": question, "stream": False}
    )
    duration = time.time() - start
    chat_data = resp.json()
    print(f"   Response time: {duration:.2f}s")
    print(f"   Status: code={chat_data.get('code')}, message={chat_data.get('message')}")

    if chat_data.get("code") == 0:
        reply_data = chat_data.get("data", {})
        reply_content = reply_data.get("content", "")
        references = reply_data.get("references", [])
        print(f"   Reply content (truncated): {reply_content[:200]}...")
        print(f"   Knowledge references: {len(references)} items")
        for ref in references[:3]:
            print(f"     - {ref.get('doc_id', 'N/A')}: score={ref.get('score', 'N/A')}, content={str(ref.get('content', ''))[:60]}...")
    else:
        print(f"   FAIL: {chat_data}")

    # 5. Test with streaming
    print("\n5. Test streaming response...")
    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/{session_id}/messages",
        headers=headers,
        json={"content": "介绍一下你的功能", "stream": True},
        stream=True
    )
    chunks = []
    for line in resp.iter_lines():
        if line:
            chunks.append(line.decode('utf-8'))
    duration = time.time() - start
    print(f"   Stream chunks: {len(chunks)}, duration: {duration:.2f}s")
    if chunks:
        print(f"   First chunk: {chunks[0][:100]}...")

    print("\n=== RAG Test Complete ===")

if __name__ == "__main__":
    test_rag()
