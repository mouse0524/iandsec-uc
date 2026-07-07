import json
from types import SimpleNamespace

import pytest

from app.api.v1.base import base as base_api
from app.schemas.mail import ResetPasswordByEmailIn, SendResetPasswordCodeIn, SendVerifyCodeIn


class FakeRequest:
    headers = {}
    client = SimpleNamespace(host="127.0.0.1")


class FakeQuery:
    def __init__(self, *, exists=False, first=None):
        self._exists = exists
        self._first = first

    async def exists(self):
        return self._exists

    async def first(self):
        return self._first


def response_json(response):
    return json.loads(response.body.decode())


@pytest.mark.anyio
async def test_send_email_code_does_not_query_email_when_challenge_fails(monkeypatch):
    async def fake_config():
        return {}

    async def fake_verify(**kwargs):
        return False, "captcha failed"

    def fail_filter(**kwargs):
        raise AssertionError("email lookup should wait until challenge passes")

    monkeypatch.setattr(base_api.system_setting_controller, "get_full_dict", fake_config)
    monkeypatch.setattr(base_api.human_challenge_service, "verify", fake_verify)
    monkeypatch.setattr(base_api.User, "filter", fail_filter)
    monkeypatch.setattr(base_api.PartnerRegistration, "filter", fail_filter)

    response = await base_api.send_email_code(
        SendVerifyCodeIn(email="known@example.com", captcha_code="bad"),
        FakeRequest(),
    )

    assert response.status_code == 400


@pytest.mark.anyio
async def test_send_email_code_requires_unused_invite_before_sending(monkeypatch):
    sent = []

    async def fake_config():
        return {}

    async def fake_verify(**kwargs):
        return True, ""

    async def fake_send(email):
        sent.append(email)

    monkeypatch.setattr(base_api.system_setting_controller, "get_full_dict", fake_config)
    monkeypatch.setattr(base_api.human_challenge_service, "verify", fake_verify)
    monkeypatch.setattr(base_api, "PartnerInvite", SimpleNamespace(filter=lambda **kwargs: FakeQuery(exists=False)), raising=False)
    monkeypatch.setattr(base_api.User, "filter", lambda **kwargs: FakeQuery(exists=False))
    monkeypatch.setattr(base_api.PartnerRegistration, "filter", lambda **kwargs: FakeQuery(exists=False))
    monkeypatch.setattr(base_api.mail_controller, "send_partner_verify_code", fake_send)

    response = await base_api.send_email_code(
        SendVerifyCodeIn(email="new@example.com", captcha_code="ok", invite_code="USED"),
        FakeRequest(),
    )

    assert response.status_code == 400
    assert sent == []


@pytest.mark.anyio
async def test_send_reset_password_code_masks_unknown_email(monkeypatch):
    sent = []

    async def fake_verify(**kwargs):
        return True, ""

    async def fake_send(email):
        sent.append(email)

    monkeypatch.setattr(base_api.human_challenge_service, "verify", fake_verify)
    monkeypatch.setattr(base_api.User, "filter", lambda **kwargs: FakeQuery(first=None))
    monkeypatch.setattr(base_api.mail_controller, "send_reset_password_code", fake_send)

    response = await base_api.send_reset_password_code(
        SendResetPasswordCodeIn(email="missing@example.com"),
        FakeRequest(),
    )

    assert response.status_code == 200
    assert response_json(response)["msg"] == base_api.RESET_PASSWORD_CODE_SENT_MSG
    assert sent == []


@pytest.mark.anyio
async def test_reset_password_by_email_masks_missing_user_like_bad_code(monkeypatch):
    async def fake_verify(email, code):
        return False

    monkeypatch.setattr(base_api.mail_controller, "verify_email_code", fake_verify)

    monkeypatch.setattr(base_api.User, "filter", lambda **kwargs: FakeQuery(first=None))
    missing_response = await base_api.reset_password_by_email(
        ResetPasswordByEmailIn(
            email="missing@example.com",
            email_code="123456",
            new_password="Password123",
        )
    )

    monkeypatch.setattr(base_api.User, "filter", lambda **kwargs: FakeQuery(first=object()))
    bad_code_response = await base_api.reset_password_by_email(
        ResetPasswordByEmailIn(
            email="known@example.com",
            email_code="123456",
            new_password="Password123",
        )
    )

    assert missing_response.status_code == bad_code_response.status_code == 400
    assert response_json(missing_response)["msg"] == response_json(bad_code_response)["msg"]
    assert response_json(missing_response)["msg"] == base_api.RESET_PASSWORD_CODE_INVALID_MSG
