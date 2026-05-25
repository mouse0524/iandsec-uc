from datetime import datetime

from app.utils.ops_password import generate_replace_decrypt_password, generate_server_ops_password


def test_generate_server_ops_password_is_stable_for_same_secret():
    now = datetime(2026, 5, 25, 9, 30)

    assert generate_server_ops_password(now, secret="ops-secret-a") == generate_server_ops_password(
        now,
        secret="ops-secret-a",
    )


def test_generate_server_ops_password_depends_on_secret():
    now = datetime(2026, 5, 25, 9, 30)

    assert generate_server_ops_password(now, secret="ops-secret-a") != generate_server_ops_password(
        now,
        secret="ops-secret-b",
    )


def test_generate_replace_decrypt_password_is_stable_for_same_secret():
    now = datetime(2026, 5, 25, 9, 30)

    assert generate_replace_decrypt_password(now, secret="ops-secret-a") == generate_replace_decrypt_password(
        now,
        secret="ops-secret-a",
    )


def test_generate_replace_decrypt_password_depends_on_secret():
    now = datetime(2026, 5, 25, 9, 30)

    assert generate_replace_decrypt_password(now, secret="ops-secret-a") != generate_replace_decrypt_password(
        now,
        secret="ops-secret-b",
    )
