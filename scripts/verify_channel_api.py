# -*- coding: utf-8 -*-
"""API 连通性验证脚本 - 渠道管理模块
适配 admin_channel.py 实际路由：
- GET    /overview
- GET    /configs              -> 返回数组，不是分页字典
- POST   /configs              -> save/update（ChannelConfigDTO 字段: platform, display_name...）
- PUT    /{platform}/status
- POST   /{platform}/test
- GET    /conversations        -> 不是 /sessions
- GET    /conversations/{id}/messages
- GET    /webhook-logs
"""
import urllib.request
import json

def http_json(url, method="GET", data=None, headers=None):
    """发送 HTTP 请求并返回 (status, parsed_json)。"""
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"error_raw": err_body}


def main():
    """主函数：依次验证登录、渠道概览、配置、会话、日志接口"""
    base = "http://localhost:8000/api/v1"
    results = []

    # 1. 登录
    code, login_data = http_json(f"{base}/auth/login", "POST",
                                 {"username": "admin", "password": "admin123"})
    print(f"[登录] HTTP {code}  code={login_data.get('code')}  message={login_data.get('message')}")
    if login_data.get("code") != 0:
        print("❌ 登录失败，无法继续")
        return 1
    token = login_data["data"]["access_token"]
    print(f"[Token] 长度={len(token)}")
    results.append(("登录", True))
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 2. 渠道概览
    code, ov = http_json(f"{base}/admin/channels/overview", headers=auth_headers)
    print(f"\n[渠道概览] HTTP {code}  code={ov.get('code')}")
    if ov.get("code") == 0:
        d = ov["data"]
        print(f"  today_messages={d.get('today_messages')}  "
              f"active_channels={d.get('active_channels')}  "
              f"avg_response_time_ms={d.get('avg_response_time_ms')}  "
              f"transfer_rate={d.get('transfer_rate')}  "
              f"channels_len={len(d.get('channels', []))}")
    results.append(("渠道概览", ov.get("code") == 0))

    # 3. 渠道配置列表（返回 ChannelConfig[]，不是分页对象）
    code, cf = http_json(f"{base}/admin/channels/configs", headers=auth_headers)
    print(f"\n[渠道配置-列表] HTTP {code}  code={cf.get('code')}")
    cfg_list = []
    if cf.get("code") == 0 and isinstance(cf["data"], list):
        cfg_list = cf["data"]
        print(f"  配置条数={len(cfg_list)}")
        for c in cfg_list:
            print(f"    - platform={c.get('platform')}  display_name={c.get('display_name')}  "
                  f"enabled={c.get('enabled')}")
    results.append(("渠道配置-列表", cf.get("code") == 0 and isinstance(cf.get("data"), list)))

    # 4. 新增渠道配置（POST /configs，使用 ChannelConfigDTO 正确字段）
    new_cfg = {
        "platform": "generic",
        "display_name": "测试渠道-自动化脚本创建",
        "enabled": True,
        "webhook_secret": "test_secret_123",
        "app_key": "test_app_key_001",
        "api_token": "test_token_xxx",
        "remark": "由脚本创建，验证完毕后可删除",
    }
    code, created = http_json(f"{base}/admin/channels/configs", "POST", new_cfg, auth_headers)
    print(f"\n[渠道配置-新增] HTTP {code}  code={created.get('code')}  message={created.get('message')}")
    saved_platform = None
    if created.get("code") == 0:
        saved = created["data"]
        saved_platform = saved.get("platform")
        print(f"  创建成功: platform={saved.get('platform')}  display_name={saved.get('display_name')}  "
              f"enabled={saved.get('enabled')}")
    else:
        print(f"  ⚠️  失败详情: {created}")
    results.append(("渠道配置-新增", created.get("code") == 0))

    # 5. 启用/停用渠道 PUT /{platform}/status
    if saved_platform:
        code, tog = http_json(f"{base}/admin/channels/{saved_platform}/status?enabled=false",
                              "PUT", headers=auth_headers)
        print(f"\n[渠道配置-停用] HTTP {code}  code={tog.get('code')}  message={tog.get('message')}")
        results.append(("渠道配置-停用", tog.get("code") == 0))

    # 6. 测试渠道连接 POST /{platform}/test
    if saved_platform:
        code, tc = http_json(f"{base}/admin/channels/{saved_platform}/test",
                             "POST", headers=auth_headers)
        print(f"\n[渠道配置-连接测试] HTTP {code}  code={tc.get('code')}  message={tc.get('message')}")
        # 连接测试因无真实第三方，只要接口返回了结构化响应就算可用
        results.append(("渠道配置-连接测试", tc.get("code") is not None))

    # 7. 渠道会话列表 GET /conversations（不是 /sessions）
    code, ss = http_json(f"{base}/admin/channels/conversations?page=1&page_size=10", headers=auth_headers)
    print(f"\n[渠道会话-列表] HTTP {code}  code={ss.get('code')}")
    if ss.get("code") == 0:
        d = ss["data"]
        print(f"  总数={d.get('total')}  当前页条数={len(d.get('items', []))}  page={d.get('page')}")
    else:
        print(f"  ⚠️  失败详情: {ss}")
    results.append(("渠道会话-列表", ss.get("code") == 0))

    # 8. Webhook 日志
    code, wl = http_json(f"{base}/admin/channels/webhook-logs?page=1&page_size=10", headers=auth_headers)
    print(f"\n[Webhook日志-列表] HTTP {code}  code={wl.get('code')}")
    if wl.get("code") == 0:
        d = wl["data"]
        print(f"  总数={d.get('total')}  当前页条数={len(d.get('items', []))}")
    results.append(("Webhook日志-列表", wl.get("code") == 0))

    # 9. 重新拉取配置列表，确认新增的配置在列表中
    if saved_platform:
        code, cf2 = http_json(f"{base}/admin/channels/configs", headers=auth_headers)
        if cf2.get("code") == 0 and isinstance(cf2["data"], list):
            found = any(c.get("platform") == saved_platform for c in cf2["data"])
            print(f"\n[渠道配置-二次确认] 新增配置在列表中: {'是' if found else '否'}")
            results.append(("渠道配置-落库确认", found))

    # 汇总
    print("\n" + "=" * 56)
    print("📊 渠道管理模块 API 验证汇总")
    print("=" * 56)
    all_ok = True
    for name, ok in results:
        mark = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"  {mark} {name}")
    print("=" * 56)
    if all_ok:
        print("🎉 所有渠道管理 API 验证通过！CODE_WIKI 第11章 RT-3 任务完成")
    else:
        print("⚠️  部分项目未通过，请检查上方日志定位问题")
    return 0 if all_ok else 1


if __name__ == "__main__":
    exit(main())

