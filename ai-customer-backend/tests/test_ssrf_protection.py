"""B4 SSRF 防护回归测试。

验证 GenericAdapter.send_reply 不会对内网/环回/链路本地地址发起请求。

攻击面：
  GenericAdapter 接收 webhook 请求体中的 callback_url，
  回复时 httpx.post(callback_url) 回调。
  无防护时攻击者可探测内网服务或窃取云元数据。

防护链：
  validate_callback_url → 校验协议 + IP 范围检查 + DNS 解析检查
  GenericAdapter.send_reply → 调用 validate_callback_url，失败抛 AdapterSendError
"""

import socket
from unittest.mock import patch

import pytest

from app.adapters.platforms.generic_adapter import GenericAdapter
from app.exceptions import AdapterSendError
from app.security.url_guard import _is_ip_blocked, validate_callback_url


# --------------------------------------------------------------------------- #
# validate_callback_url — 协议检查
# --------------------------------------------------------------------------- #
class TestSchemeValidation:
    """非 http/https 协议一律拒绝。"""

    def test_file_scheme_rejected(self):
        with pytest.raises(ValueError, match="仅允许 http/https"):
            validate_callback_url("file:///etc/passwd")

    def test_ftp_scheme_rejected(self):
        with pytest.raises(ValueError, match="仅允许 http/https"):
            validate_callback_url("ftp://example.com/file")

    def test_gopher_scheme_rejected(self):
        with pytest.raises(ValueError, match="仅允许 http/https"):
            validate_callback_url("gopher://127.0.0.1:6379/_INFO")

    def test_dict_scheme_rejected(self):
        with pytest.raises(ValueError, match="仅允许 http/https"):
            validate_callback_url("dict://127.0.0.1:11211/stats")

    def test_empty_scheme_rejected(self):
        with pytest.raises(ValueError, match="仅允许 http/https"):
            validate_callback_url("//example.com/path")

    def test_empty_url_rejected(self):
        with pytest.raises(ValueError, match="不能为空"):
            validate_callback_url("")

    def test_none_url_rejected(self):
        with pytest.raises(ValueError, match="不能为空"):
            validate_callback_url(None)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# validate_callback_url — IP 字面量检查
# --------------------------------------------------------------------------- #
class TestIPLiteralBlocked:
    """直接在 URL 中使用内网 IP 字面量应被拒绝（无需 DNS 解析）。"""

    @pytest.mark.parametrize(
        "url, reason_keyword",
        [
            ("http://127.0.0.1/callback", "loopback"),
            ("http://127.0.0.1:8080/admin", "loopback"),
            ("http://127.1.2.3/test", "loopback"),
            ("http://10.0.0.1/callback", "private"),
            ("http://10.255.255.255/test", "private"),
            ("http://192.168.1.1/callback", "private"),
            ("http://192.168.0.0/test", "private"),
            ("http://172.16.0.1/callback", "private"),
            ("http://172.31.255.255/test", "private"),
            ("http://169.254.169.254/latest/meta-data/", "link-local"),
            ("http://169.254.170.2/test", "link-local"),
            ("http://0.0.0.0/test", "unspecified"),
            ("http://0.0.0.0:8000/test", "unspecified"),
            ("http://100.64.0.1/test", "CGNAT"),
            ("http://224.0.0.1/test", "multicast"),
            ("http://240.0.0.1/test", "reserved"),
        ],
    )
    def test_blocked_ipv4(self, url, reason_keyword):
        with pytest.raises(ValueError, match=reason_keyword):
            validate_callback_url(url)

    def test_ipv6_loopback_blocked(self):
        with pytest.raises(ValueError, match="loopback"):
            validate_callback_url("http://[::1]/callback")

    def test_ipv6_link_local_blocked(self):
        with pytest.raises(ValueError, match="link-local"):
            validate_callback_url("http://[fe80::1]/callback")

    def test_ipv6_unique_local_blocked(self):
        with pytest.raises(ValueError, match="unique local"):
            validate_callback_url("http://[fc00::1]/callback")

    def test_ipv6_unspecified_blocked(self):
        with pytest.raises(ValueError, match="unspecified"):
            validate_callback_url("http://[::]/test")


# --------------------------------------------------------------------------- #
# validate_callback_url — 合法公网 URL 放行
# --------------------------------------------------------------------------- #
class TestValidUrlAllowed:
    """公网 IP 与合法域名应放行。"""

    def test_public_ipv4_allowed(self):
        # 8.8.8.8 是 Google DNS，公网地址
        assert validate_callback_url("http://8.8.8.8/callback") == "http://8.8.8.8/callback"

    def test_public_ipv4_with_port_allowed(self):
        assert validate_callback_url("https://1.1.1.1:443/hook") == "https://1.1.1.1:443/hook"

    def test_https_scheme_allowed(self):
        url = "https://203.0.113.1/api/callback"
        assert validate_callback_url(url) == url

    def test_public_ipv6_allowed(self):
        # 2606:4700::1 是 Cloudflare 公网地址
        url = "http://[2606:4700::1]/callback"
        assert validate_callback_url(url) == url


# --------------------------------------------------------------------------- #
# validate_callback_url — DNS 解析检查
# --------------------------------------------------------------------------- #
class TestDNSResolutionCheck:
    """域名解析到内网 IP 应被拒绝。"""

    def test_domain_resolves_to_private_rejected(self):
        """域名解析到 10.x 内网地址 → 拒绝。"""
        fake_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0)),
        ]
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            with pytest.raises(ValueError, match="解析到封锁地址"):
                validate_callback_url("https://internal.evil.com/callback")

    def test_domain_resolves_to_loopback_rejected(self):
        """域名解析到 127.0.0.1 → 拒绝。"""
        fake_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0)),
        ]
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            with pytest.raises(ValueError, match="loopback"):
                validate_callback_url("https://localhost.evil.com/hook")

    def test_domain_resolves_to_metadata_rejected(self):
        """域名解析到 169.254.169.254 → 拒绝（云元数据窃取）。"""
        fake_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0)),
        ]
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            with pytest.raises(ValueError, match="link-local"):
                validate_callback_url("https://metadata.attacker.com/latest")

    def test_domain_resolves_to_mixed_ips_all_checked(self):
        """多 A 记录中只要有一个内网 IP → 拒绝。"""
        fake_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 0)),  # 公网
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0)),  # 内网
        ]
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            with pytest.raises(ValueError, match="10.0.0.5"):
                validate_callback_url("https://mixed.attacker.com/hook")

    def test_domain_resolves_to_public_allowed(self):
        """域名解析到公网 IP → 放行。"""
        fake_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),  # example.com
        ]
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            result = validate_callback_url("https://example.com/callback")
            assert result == "https://example.com/callback"

    def test_dns_resolution_failure_rejected(self):
        """DNS 解析失败 → 拒绝（fail-closed）。"""
        with patch(
            "app.security.url_guard.socket.getaddrinfo",
            side_effect=socket.gaierror("Name or service not known"),
        ):
            with pytest.raises(ValueError, match="解析失败"):
                validate_callback_url("https://nonexistent.invalid/callback")

    def test_ipv6_with_zone_id_stripped(self):
        """IPv6 zone id (fe80::1%eth0) 应正确剥离后检查。"""
        fake_addr = [
            (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("fe80::1%eth0", 0, 0, 0)),
        ]
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            with pytest.raises(ValueError, match="link-local"):
                validate_callback_url("https://zone6.attacker.com/hook")


# --------------------------------------------------------------------------- #
# _is_ip_blocked — 单元测试
# --------------------------------------------------------------------------- #
class TestIsIPBlocked:
    """直接测试 IP 检查函数。"""

    @pytest.mark.parametrize(
        "ip, expected_blocked",
        [
            ("127.0.0.1", True),
            ("127.255.255.255", True),
            ("10.0.0.1", True),
            ("192.168.0.1", True),
            ("172.16.0.1", True),
            ("172.31.255.255", True),
            ("169.254.169.254", True),
            ("0.0.0.0", True),
            ("100.64.0.1", True),
            ("224.0.0.1", True),
            ("240.0.0.1", True),
            ("::1", True),
            ("fe80::1", True),
            ("fc00::1", True),
            ("ff00::1", True),
            ("::", True),
        ],
    )
    def test_blocked_ips(self, ip, expected_blocked):
        blocked, _reason = _is_ip_blocked(ip)
        assert blocked is expected_blocked

    @pytest.mark.parametrize(
        "ip",
        [
            "8.8.8.8",       # Google DNS
            "1.1.1.1",       # Cloudflare DNS
            "203.0.113.1",   # TEST-NET-3 (documentation range, but not in our blocklist)
            "172.32.0.1",    # Just outside 172.16/12 private range
            "2606:4700::1",  # Cloudflare IPv6
            "2001:4860:4860::8888",  # Google IPv6 DNS
        ],
    )
    def test_allowed_ips(self, ip):
        blocked, _reason = _is_ip_blocked(ip)
        assert not blocked


# --------------------------------------------------------------------------- #
# GenericAdapter.send_reply 集成测试
# --------------------------------------------------------------------------- #
class TestGenericAdapterSSRFIntegration:
    """验证 GenericAdapter.send_reply 拒绝不安全的 callback_url。"""

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1:8000/admin",
            "http://10.0.0.5:3306",
            "http://169.254.169.254/latest/meta-data/",
            "http://192.168.1.1/router",
            "file:///etc/passwd",
            "gopher://127.0.0.1:6379/_INFO",
            "http://[::1]/callback",
            "http://[fe80::1]/callback",
        ],
    )
    async def test_send_reply_rejects_unsafe_url(self, url):
        """不安全的 callback_url → AdapterSendError（不发起 HTTP 请求）。"""
        adapter = GenericAdapter()
        with pytest.raises(AdapterSendError, match="安全校验失败"):
            await adapter.send_reply(
                external_session_id="test_session",
                content="测试回复",
                callback_url=url,
            )

    async def test_send_reply_rejects_dns_rebind_to_internal(self):
        """域名解析到内网 IP → AdapterSendError。"""
        fake_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.99", 0)),
        ]
        adapter = GenericAdapter()
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            with pytest.raises(AdapterSendError, match="安全校验失败"):
                await adapter.send_reply(
                    external_session_id="test_session",
                    content="测试回复",
                    callback_url="https://rebind.attacker.com/callback",
                )

    async def test_send_reply_no_callback_url_raises(self):
        """缺少 callback_url → AdapterSendError。"""
        adapter = GenericAdapter()
        with pytest.raises(AdapterSendError, match="需要 callback_url"):
            await adapter.send_reply(
                external_session_id="test_session",
                content="测试回复",
            )


# --------------------------------------------------------------------------- #
# Allowlist 测试
# --------------------------------------------------------------------------- #
class TestAllowlist:
    """CALLBACK_URL_ALLOWLIST 配置的域名应绕过内网检查。"""

    def test_exact_domain_allowlisted(self, monkeypatch):
        monkeypatch.setattr(settings_ref(), "CALLBACK_URL_ALLOWLIST", "api.trusted.com")
        # 即使解析到内网也应放行
        fake_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0)),
        ]
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            result = validate_callback_url("https://api.trusted.com/callback")
            assert result == "https://api.trusted.com/callback"

    def test_wildcard_domain_allowlisted(self, monkeypatch):
        monkeypatch.setattr(settings_ref(), "CALLBACK_URL_ALLOWLIST", "*.trusted.com")
        fake_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0)),
        ]
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            result = validate_callback_url("https://sub.api.trusted.com/callback")
            assert result == "https://sub.api.trusted.com/callback"

    def test_non_allowlisted_domain_still_checked(self, monkeypatch):
        """Allowlist 外的域名仍需通过内网检查。"""
        monkeypatch.setattr(settings_ref(), "CALLBACK_URL_ALLOWLIST", "api.trusted.com")
        fake_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0)),
        ]
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            with pytest.raises(ValueError, match="解析到封锁地址"):
                validate_callback_url("https://api.untrusted.com/callback")

    def test_empty_allowlist_no_effect(self, monkeypatch):
        """空 allowlist → 所有域名都走正常检查。"""
        monkeypatch.setattr(settings_ref(), "CALLBACK_URL_ALLOWLIST", "")
        fake_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0)),
        ]
        with patch("app.security.url_guard.socket.getaddrinfo", return_value=fake_addr):
            with pytest.raises(ValueError, match="解析到封锁地址"):
                validate_callback_url("https://api.trusted.com/callback")


# --------------------------------------------------------------------------- #
# 辅助函数
# --------------------------------------------------------------------------- #
def settings_ref():
    """返回全局 settings 单例，供 monkeypatch 使用。"""
    from app.config.settings import settings as s
    return s
