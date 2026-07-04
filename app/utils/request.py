from fastapi import Request

from app.settings import settings


def get_client_ip(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        for header in ("cf-connecting-ip", "true-client-ip", "x-real-ip"):
            value = request.headers.get(header)
            if value:
                return value.strip()
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
