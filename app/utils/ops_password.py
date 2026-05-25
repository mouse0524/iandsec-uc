import hashlib
import hmac
from datetime import datetime

from app.settings import settings


def sha256_hex(input_string: str) -> str:
    return hashlib.sha256(input_string.encode("utf-8")).hexdigest()


def _resolve_secret(secret: str | None = None) -> str:
    value = secret or settings.OPS_PASSWORD_SECRET or settings.SECRET_KEY
    if not value:
        raise RuntimeError("OPS_PASSWORD_SECRET or SECRET_KEY must be set")
    return value


def _hmac_hex(secret: str, purpose: str, period: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"{purpose}:{period}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_server_ops_password(now: datetime | None = None, *, secret: str | None = None) -> str:
    time_str = (now or datetime.now()).strftime("%Y%m%d")
    hash_value = _hmac_hex(_resolve_secret(secret), "server-ops", time_str)
    charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    positions = [0, 3, 7, 11, 15, 19, 23, 27, 31, 35]

    password = []
    for idx in positions:
        if idx < len(hash_value):
            char_index = ord(hash_value[idx]) % len(charset)
            password.append(charset[char_index])
        if len(password) >= 10:
            break

    return "".join(password)


def generate_replace_decrypt_password(now: datetime | None = None, *, secret: str | None = None) -> str:
    current = now or datetime.now()
    year = current.year
    month = int(current.strftime("%m").replace("0", ""))
    year += (year - 2024) * 9
    if month < 5:
        month *= month + 1
    elif month > 5:
        month *= month - 2
    data = (year - 1968) + month
    data *= 37
    period = current.strftime("%Y%m")
    secret_offset = int(_hmac_hex(_resolve_secret(secret), "replace-decrypt", period)[:8], 16)
    return str((data + secret_offset) % 1_000_000).zfill(6)
