from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException

from app.settings import settings


def _is_private_hostname(hostname: str) -> bool:
    lowered = hostname.strip().lower().rstrip(".")
    if lowered in {"localhost", "0", "0.0.0.0"}:
        return True
    try:
        ip = ipaddress.ip_address(lowered)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified
    except ValueError:
        pass

    try:
        resolved = socket.getaddrinfo(lowered, None)
    except OSError:
        return False
    for item in resolved:
        address = item[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            return True
    return False


def validate_external_service_url(url: str | None, *, label: str = "外部服务") -> str:
    raw = str(url or "").strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=400, detail=f"{label}地址必须使用 HTTPS")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail=f"{label}地址不能包含认证信息")
    if _is_private_hostname(parsed.hostname):
        raise HTTPException(status_code=400, detail=f"{label}地址不能指向内网或本机")
    allowed_hosts = {item.lower() for item in settings.EXTERNAL_URL_ALLOWED_HOSTS}
    if allowed_hosts and parsed.hostname.lower() not in allowed_hosts:
        raise HTTPException(status_code=400, detail=f"{label}地址不在允许的域名列表中")
    return raw
