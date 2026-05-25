import hashlib
from datetime import datetime


def sha256_hex(input_string: str) -> str:
    return hashlib.sha256(input_string.encode("utf-8")).hexdigest()


def generate_server_ops_password(now: datetime | None = None) -> str:
    time_str = (now or datetime.now()).strftime("%Y%m%d")
    seed = time_str + "IandSec@2026"
    hash_value = sha256_hex(seed)
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


def generate_replace_decrypt_password(now: datetime | None = None) -> str:
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
    return str(data)
