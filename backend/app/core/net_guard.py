"""模型 Base URL 校验（SSRF 防护）。

- 只允许 http / https，且不得在 URL 中携带账号密码。
- 默认拒绝指向本机、私有网段、链路本地地址等目标，避免自定义 Base URL 被用来探测内网。
- 如需接入本地部署的模型服务，可在 .env 中设置 ALLOW_PRIVATE_ENDPOINTS=true 显式放开。
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from .config import get_settings

_PRIVATE_NAMES = {"localhost", "localhost.localdomain"}


class UrlValidationError(ValueError):
    """Base URL 不合法或不被允许。"""


def validate_base_url(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        raise UrlValidationError("Base URL 不能为空")

    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UrlValidationError("Base URL 只允许 http 或 https 协议")
    if parts.username or parts.password:
        raise UrlValidationError("Base URL 不允许携带账号或密码")
    if not parts.hostname:
        raise UrlValidationError("Base URL 缺少有效主机名")

    if not get_settings().allow_private_endpoints:
        _reject_private_target(parts.hostname)

    return url.rstrip("/")


def _reject_private_target(hostname: str) -> None:
    host = hostname.lower().strip("[]")
    if host in _PRIVATE_NAMES or host.endswith(".localhost"):
        raise UrlValidationError(
            "默认禁止访问本机地址；如确需连接本地模型，请在后端 .env 设置 ALLOW_PRIVATE_ENDPOINTS=true"
        )

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # 域名交由 DNS 解析，非 IP 字面量不做强校验

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_multicast
    ):
        raise UrlValidationError(
            "默认禁止访问内网或被保留的 IP 地址；如确需连接内网模型，请在后端 .env 设置 ALLOW_PRIVATE_ENDPOINTS=true"
        )
