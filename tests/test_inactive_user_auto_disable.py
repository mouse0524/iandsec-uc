import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.controllers.user import UserController
from app.services.inactive_user_service import InactiveUserAutoDisableService


class FakeUser:
    def __init__(
        self,
        *,
        user_id=1,
        username="user",
        last_login=None,
        created_at=None,
        is_active=True,
        is_superuser=False,
        token_version=0,
    ):
        self.id = user_id
        self.username = username
        self.last_login = last_login
        self.created_at = created_at
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.token_version = token_version
        self.saved = False

    async def save(self):
        self.saved = True


def run(awaitable):
    return asyncio.run(awaitable)


def test_login_inactivity_disables_never_logged_in_user_after_configured_days():
    now = datetime(2026, 5, 25, 12, 0, 0)
    user = FakeUser(created_at=now - timedelta(days=31))
    config = {
        "inactive_user_auto_disable_enabled": True,
        "inactive_user_auto_disable_days": 30,
    }

    with patch.object(UserController, "clear_auth_cache", new=AsyncMock()) as clear_auth_cache:
        disabled = run(UserController().disable_if_login_inactive(user, config=config, now=now))

    assert disabled is True
    assert user.is_active is False
    assert user.token_version == 1
    assert user.saved is True
    clear_auth_cache.assert_awaited_once_with(user.id)


def test_login_inactivity_uses_last_login_when_available():
    now = datetime(2026, 5, 25, 12, 0, 0)
    user = FakeUser(
        last_login=now - timedelta(days=10),
        created_at=now - timedelta(days=90),
        token_version=3,
    )
    config = {
        "inactive_user_auto_disable_enabled": True,
        "inactive_user_auto_disable_days": 30,
    }

    disabled = run(UserController().disable_if_login_inactive(user, config=config, now=now))

    assert disabled is False
    assert user.is_active is True
    assert user.token_version == 3
    assert user.saved is False


def test_login_inactivity_does_not_disable_superuser():
    now = datetime(2026, 5, 25, 12, 0, 0)
    user = FakeUser(created_at=now - timedelta(days=365), is_superuser=True)
    config = {
        "inactive_user_auto_disable_enabled": True,
        "inactive_user_auto_disable_days": 30,
    }

    disabled = run(UserController().disable_if_login_inactive(user, config=config, now=now))

    assert disabled is False
    assert user.is_active is True
    assert user.saved is False


def test_login_inactivity_can_be_disabled_by_config():
    now = datetime(2026, 5, 25, 12, 0, 0)
    user = FakeUser(created_at=now - timedelta(days=365))
    config = {
        "inactive_user_auto_disable_enabled": False,
        "inactive_user_auto_disable_days": 30,
    }

    disabled = run(UserController().disable_if_login_inactive(user, config=config, now=now))

    assert disabled is False
    assert user.is_active is True
    assert user.saved is False


def test_scheduler_batch_disables_inactive_regular_users():
    now = datetime(2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc)
    active_old = FakeUser(user_id=1, username="old", last_login=now - timedelta(days=31))
    active_recent = FakeUser(user_id=2, username="recent", last_login=now - timedelta(days=2))
    active_never = FakeUser(user_id=3, username="never", created_at=now - timedelta(days=40))

    class FakeQuery:
        def __init__(self, users):
            self.users = users

        def filter(self, *args, **kwargs):
            return self

        async def all(self):
            return self.users

    class FakeUserModel:
        @staticmethod
        def filter(**kwargs):
            assert kwargs == {"is_active": True, "is_superuser": False}
            return FakeQuery([active_old, active_recent, active_never])

    service = InactiveUserAutoDisableService(user_model=FakeUserModel, now_factory=lambda: now)

    with patch.object(UserController, "clear_auth_cache", new=AsyncMock()) as clear_auth_cache:
        result = run(
            service.run_once(
                config={
                    "inactive_user_auto_disable_enabled": True,
                    "inactive_user_auto_disable_days": 30,
                }
            )
        )

    assert result == {"checked": 3, "disabled": 2, "days": 30}
    assert active_old.is_active is False
    assert active_recent.is_active is True
    assert active_never.is_active is False
    assert clear_auth_cache.await_count == 2
