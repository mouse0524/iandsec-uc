from datetime import datetime

from app.utils.ops_password import generate_replace_decrypt_password, generate_server_ops_password


def test_generate_server_ops_password_matches_existing_tool_for_2026_05_25():
    now = datetime(2026, 5, 25, 9, 30)

    assert generate_server_ops_password(now) == "l3z0wmj0m5"


def test_generate_replace_decrypt_password_matches_existing_tool_for_2026_05():
    now = datetime(2026, 5, 25, 9, 30)

    assert generate_replace_decrypt_password(now) == "2997"


def test_generate_replace_decrypt_password_preserves_existing_october_behavior():
    now = datetime(2026, 10, 1, 9, 30)

    assert generate_replace_decrypt_password(now) == "2886"
