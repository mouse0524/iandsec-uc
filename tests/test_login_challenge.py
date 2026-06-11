import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from app.api.v1.base import base as base_module
from app.controllers.login_security import LoginSecurityDecision
from app.schemas.login import CredentialsSchema
from app.services import human_challenge as challenge_module

REAL_ASYNC_CLIENT = httpx.AsyncClient


def _credentials(**overrides):
    data = {
        "username": "user@example.com",
        "password": "Secret123!",
        "remember_me": False,
    }
    data.update(overrides)
    return CredentialsSchema(**data)


def _request():
    return SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))


def _payload(response):
    return json.loads(response.body.decode())


def _config(**overrides):
    data = {
        "login_security_enabled": True,
        "login_challenge_enabled": True,
        "login_challenge_type": "captcha",
        "login_generic_error_enabled": False,
        "user_token_expire_minutes": 60,
    }
    data.update(overrides)
    return data


def test_login_skips_captcha_when_login_challenge_disabled():
    async def run():
        user = SimpleNamespace(id=7, username="user@example.com", is_superuser=False, token_version=0)
        with (
            patch.object(base_module.system_setting_controller, "get_full_dict", AsyncMock(return_value=_config(login_challenge_enabled=False))),
            patch.object(base_module.login_security_controller, "check_lock", AsyncMock(return_value=LoginSecurityDecision(False))),
            patch.object(base_module.login_security_controller, "clear_success", AsyncMock()),
            patch.object(base_module.user_controller, "authenticate", AsyncMock(return_value=user)),
            patch.object(base_module.user_controller, "update_last_login", AsyncMock()),
            patch.object(base_module.captcha_controller, "verify_captcha", AsyncMock()) as verify_captcha,
        ):
            result = await base_module.login_access_token(_credentials(), _request())

        assert result.status_code == 200
        assert _payload(result)["code"] == 200
        verify_captcha.assert_not_awaited()

    asyncio.run(run())


def test_login_turnstile_success_uses_siteverify():
    async def run():
        user = SimpleNamespace(id=7, username="user@example.com", is_superuser=False, token_version=0)
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"success": True}))
        with (
            patch.object(
                base_module.system_setting_controller,
                "get_full_dict",
                AsyncMock(return_value=_config(login_challenge_type="turnstile", turnstile_secret_key="secret")),
            ),
            patch.object(base_module.login_security_controller, "check_lock", AsyncMock(return_value=LoginSecurityDecision(False))),
            patch.object(base_module.login_security_controller, "clear_success", AsyncMock()),
            patch.object(base_module.user_controller, "authenticate", AsyncMock(return_value=user)),
            patch.object(base_module.user_controller, "update_last_login", AsyncMock()),
            patch.object(challenge_module.httpx, "AsyncClient", lambda **kwargs: REAL_ASYNC_CLIENT(transport=transport, **kwargs)),
        ):
            result = await base_module.login_access_token(_credentials(turnstile_token="token-1"), _request())

        assert result.status_code == 200
        assert _payload(result)["code"] == 200

    asyncio.run(run())


def test_login_turnstile_failure_records_login_failure():
    async def run():
        record_failure = AsyncMock(return_value=LoginSecurityDecision(False))
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"success": False, "error-codes": ["invalid-input-response"]}))
        with (
            patch.object(
                base_module.system_setting_controller,
                "get_full_dict",
                AsyncMock(return_value=_config(login_challenge_type="turnstile", turnstile_secret_key="secret")),
            ),
            patch.object(base_module.login_security_controller, "check_lock", AsyncMock(return_value=LoginSecurityDecision(False))),
            patch.object(base_module.login_security_controller, "record_failure", record_failure),
            patch.object(base_module.user_controller, "authenticate", AsyncMock()) as authenticate,
            patch.object(challenge_module.httpx, "AsyncClient", lambda **kwargs: REAL_ASYNC_CLIENT(transport=transport, **kwargs)),
        ):
            result = await base_module.login_access_token(_credentials(turnstile_token="bad-token"), _request())

        assert result.status_code == 400
        assert _payload(result)["code"] == 400
        record_failure.assert_awaited_once()
        authenticate.assert_not_awaited()

    asyncio.run(run())


def test_human_challenge_both_requires_captcha_and_turnstile():
    async def run():
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"success": True}))
        with (
            patch.object(challenge_module.captcha_controller, "verify_captcha", AsyncMock(return_value=True)) as verify_captcha,
            patch.object(challenge_module.httpx, "AsyncClient", lambda **kwargs: REAL_ASYNC_CLIENT(transport=transport, **kwargs)),
        ):
            valid, error = await challenge_module.human_challenge_service.verify(
                captcha_id="captcha-1",
                captcha_code="1234",
                turnstile_token="turnstile-token",
                client_ip="127.0.0.1",
                config={
                    "login_challenge_enabled": True,
                    "login_challenge_type": "both",
                    "turnstile_secret_key": "secret",
                },
            )

        assert valid is True
        assert error == ""
        verify_captcha.assert_awaited_once_with("captcha-1", "1234", consume=True)

    asyncio.run(run())


def test_human_challenge_both_fails_without_turnstile_token_after_captcha_passes():
    async def run():
        with patch.object(challenge_module.captcha_controller, "verify_captcha", AsyncMock(return_value=True)) as verify_captcha:
            valid, error = await challenge_module.human_challenge_service.verify(
                captcha_id="captcha-1",
                captcha_code="1234",
                turnstile_token="",
                config={
                    "login_challenge_enabled": True,
                    "login_challenge_type": "both",
                    "turnstile_secret_key": "secret",
                },
            )

        assert valid is False
        assert "Turnstile" in error
        verify_captcha.assert_awaited_once_with("captcha-1", "1234", consume=True)

    asyncio.run(run())
