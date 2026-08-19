"""SSRF 防护：出站 URL 安全校验。

拦截对内网 / 环回 / 链路本地地址的出站 HTTP 请求，防止 SSRF 攻击。

攻击场景：
  GenericAdapter 接收用户 webhook 请求体中的 callback_url，
  回复时直接 httpx.post(callback_url) 回调。
  攻击者可设置 callback_url 指向内网服务或云元数据接口：

    - http://127.0.0.1:8000/admin        （本机服务探测）
    - http://10.0.0.5:3306                （内网 DB 探测）
    - http://169.254.169.254/latest/meta-data/  （AWS / 云厂商元数据窃取）
    - http://192.168.1.1                  （内网网关）

  本模块在请求发出前校验 URL，拒绝所有非公网地址。

设计要点：
  1. 仅允许 http/https 协议（拒绝 file://, gopher://, ftp://, dict:// 等）
  2. hostname 为 IP 字面量时直接检查
  3. hostname 为域名时 DNS 解析后检查所有 A/AAAA 记录
  4. 封锁范围：loopback / private / link-local / unspecified / multicast / reserved
  5. 可选 allowlist：settings.CALLBACK_URL_ALLOWLIST 配置的域名/前缀直接放行
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

from app.config.settings import settings

logger = logging.getLogger(__name__)

# 仅允许的协议
_ALLOWED_SCHEMES = frozenset({"http", "https"})

# 封锁的 IP 范围（network, 描述）
_BLOCKED_RANGES: list[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, str]] = [
    # IPv4
    (ipaddress.ip_network("127.0.0.0/8"), "IPv4 loopback"),
    (ipaddress.ip_network("10.0.0.0/8"), "IPv4 private 10/8"),
    (ipaddress.ip_network("172.16.0.0/12"), "IPv4 private 172.16/12"),
    (ipaddress.ip_network("192.168.0.0/16"), "IPv4 private 192.168/16"),
    (ipaddress.ip_network("169.254.0.0/16"), "IPv4 link-local (含云元数据接口)"),
    (ipaddress.ip_network("0.0.0.0/8"), "IPv4 unspecified/current network"),
    (ipaddress.ip_network("100.64.0.0/10"), "IPv4 CGNAT"),
    (ipaddress.ip_network("224.0.0.0/4"), "IPv4 multicast"),
    (ipaddress.ip_network("240.0.0.0/4"), "IPv4 reserved"),
    # IPv6
    (ipaddress.ip_network("::1/128"), "IPv6 loopback"),
    (ipaddress.ip_network("fc00::/7"), "IPv6 unique local"),
    (ipaddress.ip_network("fe80::/10"), "IPv6 link-local"),
    (ipaddress.ip_network("::/128"), "IPv6 unspecified"),
    (ipaddress.ip_network("ff00::/8"), "IPv6 multicast"),
]


def _is_ip_blocked(ip_str: str) -> tuple[bool, str]:
    """检查 IP 地址是否在封锁范围内。

    Args:
        ip_str: IP 地址字符串（IPv4 或 IPv6）。

    Returns:
        (is_blocked, reason): 被封锁时 reason 含原因描述，未封锁时 reason 为空。
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True, f"无法解析的 IP 地址: {ip_str}"

    for network, desc in _BLOCKED_RANGES:
        # IPv4 地址不会在 IPv6 network 中，反之亦然
        if ip.version != network.version:
            continue
        if ip in network:
            return True, desc

    return False, ""


def _is_allowlisted(hostname: str) -> bool:
    """检查 hostname 是否在 allowlist 中。

    Allowlist 条目可以是：
    - 精确域名：api.example.com
    - 通配前缀：*.example.com（匹配 example.com 及其任意子域）

    Args:
        hostname: 待检查的主机名（已小写化）。

    Returns:
        bool: 是否在 allowlist 中。
    """
    allowlist = getattr(settings, "CALLBACK_URL_ALLOWLIST", "") or ""
    if not allowlist.strip():
        return False

    entries = [e.strip().lower() for e in allowlist.split(",") if e.strip()]
    for entry in entries:
        if entry == hostname:
            return True
        if entry.startswith("*."):
            suffix = entry[1:]  # ".example.com"
            if hostname.endswith(suffix):
                return True
    return False


def validate_callback_url(url: str) -> str:
    """校验出站 URL 是否安全（非内网 / 非环回 / 非链路本地）。

    本函数为同步方法，在异步上下文中调用时建议使用
    ``await asyncio.to_thread(validate_callback_url, url)`` 避免阻塞事件循环。

    Args:
        url: 待校验的 URL 字符串。

    Returns:
        str: 校验通过后的 URL（原样返回）。

    Raises:
        ValueError: URL 不安全时抛出，message 中包含封锁原因。
    """
    if not url or not isinstance(url, str):
        raise ValueError("callback_url 不能为空")

    parsed = urlparse(url)

    # 1. 协议检查——仅 http/https
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"callback_url 仅允许 http/https 协议，"
            f"收到: {parsed.scheme or '(空)'}"
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("callback_url 缺少主机名")

    hostname_lower = hostname.lower()

    # 2. Allowlist 快速放行
    if _is_allowlisted(hostname_lower):
        logger.debug("callback_url allowlisted: %s", hostname_lower)
        return url

    # 3. hostname 为 IP 字面量时直接检查
    try:
        ip = ipaddress.ip_address(hostname)
        blocked, reason = _is_ip_blocked(str(ip))
        if blocked:
            raise ValueError(
                f"callback_url 指向封锁地址 ({reason}): {hostname}"
            )
        return url
    except ValueError:
        pass  # 不是 IP 字面量 → 继续做 DNS 解析

    # 4. DNS 解析并检查所有 A/AAAA 记录
    try:
        addr_infos = socket.getaddrinfo(hostname_lower, None)
    except socket.gaierror as e:
        raise ValueError(
            f"callback_url 主机名解析失败: {hostname} ({e})"
        ) from e

    resolved_ips: set[str] = set()
    for _family, _type, _proto, _canon, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        # IPv6 sockaddr 中 IP 可能带 zone id: fe80::1%eth0
        ip_str = ip_str.split("%")[0]
        resolved_ips.add(ip_str)

    for ip_str in resolved_ips:
        blocked, reason = _is_ip_blocked(ip_str)
        if blocked:
            raise ValueError(
                f"callback_url 主机 {hostname} 解析到封锁地址 "
                f"{ip_str} ({reason})"
            )

    logger.debug(
        "callback_url validated: %s -> %s",
        hostname,
        ", ".join(sorted(resolved_ips)) or "(no IP)",
    )
    return url
