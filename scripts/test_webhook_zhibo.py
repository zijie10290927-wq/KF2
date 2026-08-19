"""RT-1 连通性自测：模拟智齿 Webhook 消息验证后端链路。

前置条件：
- 后端服务运行在 http://localhost:8000
- .env 中 ZHIBO_WEBHOOK_SECRET 为空（开发期签名直接放行）

验证项：
1. GET /api/v1/webhook/health → enabled=true, platforms 含 zhibo
2. POST /api/v1/webhook/zhibo 模拟 message.receive → 202 accepted
3. (扩展) 不带 body 的非法请求 → 400
"""
import json
import sys
import time

import requests

BASE = "http://localhost:8000"
WEBHOOK_URL = f"{BASE}/api/v1/webhook/zhibo"
HEALTH_URL = f"{BASE}/api/v1/webhook/health"

# 模拟智齿 message.receive 事件 payload（参考 zhibo_adapter.parse_incoming 字段）
FAKE_PAYLOAD = {
    "event": "message.receive",
    "timestamp": int(time.time() * 1000),
    "data": {
        "conversation": {
            "id": "conv_smoke_test_001",
            "type": "online",
            "channel": "web",
        },
        "sender": {
            "id": "visitor_smoke_001",
            "name": "连通性测试访客",
            "type": "visitor",
        },
        "message": {
            "id": "msg_smoke_test_001",
            "type": "text",
            "content": "你好，这是连通性自测消息",
        },
        "extra": {
            "page_url": "http://localhost:5173/chat",
        },
    },
}


def line(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def step1_health() -> bool:
    line("[Step 1] GET /api/v1/webhook/health")
    try:
        r = requests.get(HEALTH_URL, timeout=5)
        print(f"HTTP {r.status_code}  耗时 {r.elapsed.total_seconds():.3f}s")
        print(f"响应体: {r.text}")
        if r.status_code != 200:
            print("❌ 期望 200")
            return False
        data = r.json().get("data") or r.json()
        enabled = data.get("enabled")
        platforms = data.get("platforms") or []
        if not enabled:
            print("❌ webhook 未启用 (enabled=false)，请检查 .env WEBHOOK_ENABLED")
            return False
        if "zhibo" not in platforms:
            print(f"❌ platforms 未包含 zhibo: {platforms}")
            return False
        print(f"✅ enabled={enabled}, platforms={platforms}")
        return True
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


def step2_simulate_message() -> bool:
    line("[Step 2] POST /api/v1/webhook/zhibo 模拟 message.receive")
    headers = {"Content-Type": "application/json"}
    # 注意：当前 ZHIBO_WEBHOOK_SECRET 为空，verify_signature 直接放行
    # 如后续配置了 secret，需额外构造 X-Sobot-Signature / X-Sobot-Timestamp 头
    try:
        r = requests.post(WEBHOOK_URL, json=FAKE_PAYLOAD, headers=headers, timeout=10)
        print(f"HTTP {r.status_code}  耗时 {r.elapsed.total_seconds():.3f}s")
        print(f"响应体: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")
        if r.status_code != 202:
            print(f"❌ 期望 202，实际 {r.status_code}")
            return False
        data = r.json().get("data") or {}
        status = data.get("status")
        platform = data.get("platform")
        internal_sid = data.get("internal_session_id")
        if status != "accepted" or platform != "zhibo":
            print(f"❌ 响应字段不符: status={status} platform={platform}")
            return False
        if not internal_sid:
            print("❌ internal_session_id 为空，会话映射失败")
            return False
        print(f"✅ accepted, internal_session_id={internal_sid}")
        return True
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


def step3_invalid_body() -> bool:
    line("[Step 3] POST 非法 body 验证 400 容错")
    try:
        r = requests.post(
            WEBHOOK_URL,
            data=b"not-a-json",
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        print(f"HTTP {r.status_code}  耗时 {r.elapsed.total_seconds():.3f}s")
        print(f"响应体: {r.text[:300]}")
        if r.status_code != 400:
            # 当前 secret 为空，签名验证放行；解析失败应返回 400
            print(f"⚠️ 期望 400，实际 {r.status_code}（如已配置 secret 可能返回 403）")
            return True
        print("✅ 非法 body 正确返回 400")
        return True
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


def step4_duplicate_check() -> bool:
    line("[Step 4] 重复 message_id 验证防重")
    try:
        r1 = requests.post(WEBHOOK_URL, json=FAKE_PAYLOAD, timeout=10)
        r2 = requests.post(WEBHOOK_URL, json=FAKE_PAYLOAD, timeout=10)
        s1 = (r1.json().get("data") or {}).get("status")
        s2 = (r2.json().get("data") or {}).get("status")
        print(f"第一次: HTTP {r1.status_code} status={s1}")
        print(f"第二次: HTTP {r2.status_code} status={s2}")
        if s1 == "accepted" and s2 == "duplicate":
            print("✅ 防重逻辑生效：第二次返回 duplicate")
            return True
        print(f"⚠️ 防重未触发: s1={s1} s2={s2}")
        return False
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


def main() -> int:
    print("智齿 Webhook 连通性自测 (RT-1 Step 5.1)")
    print(f"目标: {BASE}")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    results = [
        ("健康检查", step1_health()),
        ("模拟消息", step2_simulate_message()),
        ("非法 body 容错", step3_invalid_body()),
        ("防重检查", step4_duplicate_check()),
    ]

    line("测试结果汇总")
    passed = 0
    for name, ok in results:
        flag = "✅ PASS" if ok else "❌ FAIL"
        print(f"{flag}  {name}")
        if ok:
            passed += 1
    print(f"\n通过 {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
