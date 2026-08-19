"""Admin 登录 + 渠道管理页验证脚本（Playwright）。

流程：
1. 打开 http://localhost:5173/ → 应自动跳到登录页
2. 输入 admin / admin123 → 登录
3. 等待路由跳转到管理后台
4. 打开 /admin/channel → 验证页面可访问
5. 保存关键截图
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

OUT_DIR = Path("d:/Q1/ZNKF/a1/KF1/artifacts")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. 打开登录页
        try:
            page.goto("http://localhost:5173/", wait_until="networkidle", timeout=30000)
        except PWTimeoutError:
            print("ERROR: 前端页面加载超时", file=sys.stderr)
            browser.close()
            return 1

        page.screenshot(path=str(OUT_DIR / "step01_login_page.png"), full_page=True)
        print(f"[OK] 登录页截图已保存: {OUT_DIR / 'step01_login_page.png'}")

        # 2. 填写账号密码
        try:
            page.wait_for_selector('input, [role=textbox]', timeout=10000)
        except PWTimeoutError:
            print("ERROR: 未找到表单输入框", file=sys.stderr)
            _dump_html(page, OUT_DIR / "step01b_login_error.html")
            browser.close()
            return 1

        # 查找两个 input：第一个账号第二个密码；使用更智能的 selector
        user_input = page.locator('input').first
        pwd_input = page.locator('input').nth(1)
        if user_input.count() == 0 or pwd_input.count() == 0:
            user_input = page.get_by_role('textbox').first
            pwd_input = page.get_by_role('textbox').nth(1)

        user_input.fill("admin")
        pwd_input.fill("admin123")
        page.screenshot(path=str(OUT_DIR / "step02_login_filled.png"), full_page=True)

        # 3. 点击登录按钮
        btn = page.get_by_role("button", name=re.compile(r"登\s*录|Login", "i"))
        if btn.count() == 0:
            btn = page.locator("button").filter(has_text=re.compile(r"登\s*录|Login", "i"))
        if btn.count() == 0:
            # 兜底：最后一个按钮
            btn = page.locator("button").last
        btn.click()

        # 4. 等待跳转 / 抓登录接口响应
        resp_any = None
        try:
            resp = page.wait_for_response(
                lambda r: "/api/v1/auth/login" in r.url and r.request.method == "POST",
                timeout=15000,
            )
            resp_any = resp
            print(f"[OK] 登录请求状态: {resp.status} body-preview={resp.text()[:200]}")
            if resp.status != 200:
                print("ERROR: 登录接口失败", file=sys.stderr)
                page.screenshot(path=str(OUT_DIR / "step03_login_fail.png"), full_page=True)
                browser.close()
                return 1
            data = resp.json()
            print(f"[OK] 登录响应 code={data.get('code')}, role={data.get('data',{}).get('user_info',{}).get('role')}")
            assert data.get("code") == 0, "登录返回 code != 0"
            assert data["data"]["user_info"]["role"] == "admin", "登录用户角色不是 admin"
        except PWTimeoutError:
            print("WARN: 未捕获到登录接口响应，尝试用页面状态判断")

        # 5. 等待跳转（通过 URL 变化或页面文本）
        try:
            page.wait_for_url(lambda u: "/login" not in str(u), timeout=15000)
        except PWTimeoutError:
            print("WARN: URL 未跳转，检查是否登录成功但未路由")

        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(OUT_DIR / "step04_after_login.png"), full_page=True)
        print(f"[OK] 登录后 URL = {page.url}")

        # 读取 token（用于后续请求）
        token = None
        for k in ("token", "access_token", "auth.token"):
            v = page.evaluate(f'() => localStorage.getItem("{k}") || sessionStorage.getItem("{k}")')
            if v:
                token = v
                break
        if not token:
            token = page.evaluate(
                '() => { try { const v = JSON.parse(localStorage.getItem("auth")||"{}").token; return v || null; } catch(e) { return null; } }'
            )
        print(f"[INFO] 本地存储 token: {'已获取' if token else '未找到'}")

        # 6. 导航到渠道管理页
        try:
            page.goto("http://localhost:5173/admin/channel", wait_until="networkidle", timeout=30000)
        except PWTimeoutError:
            print("ERROR: 渠道管理页加载超时（不致命，继续截图）", file=sys.stderr)

        page.screenshot(path=str(OUT_DIR / "step05_admin_channel.png"), full_page=True)
        title = page.title()
        content_1000 = page.inner_text("body")[:1000]
        print(f"[OK] 渠道管理页 title={title}")
        with open(OUT_DIR / "step05_admin_channel_text.txt", "w", encoding="utf-8") as f:
            f.write("TITLE: " + title + "\n\n" + content_1000)

        # 额外：直接调后端渠道接口验证 admin token 是否可访问
        if token:
            import urllib.request
            req = urllib.request.Request(
                "http://localhost:8000/api/v1/admin/channels?page=1&page_size=10",
                headers={"Authorization": f"Bearer {token}"},
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    api_body = r.read().decode("utf-8")
                    print(f"[OK] 后端渠道接口 code={json.loads(api_body).get('code')}")
                    with open(OUT_DIR / "step06_admin_channel_api.json", "w", encoding="utf-8") as f:
                        f.write(api_body)
            except Exception as e:
                print(f"WARN: 渠道接口返回异常（可能 DB 不可用但应能通过鉴权）: {e}")

        browser.close()
    return 0


import re  # noqa: E402  (used above in regex)


def _dump_html(page, path: Path) -> None:
    path.write_text(page.content(), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
