import pytest

from app.services import human_challenge as human_challenge_module
from app.services.human_challenge import human_challenge_service


@pytest.mark.anyio
async def test_turnstile_can_fallback_to_captcha(monkeypatch):
    async def fake_verify_captcha(captcha_id, captcha_code, *, consume=True):
        return captcha_id == "cid" and captcha_code == "1234"

    monkeypatch.setattr(human_challenge_module.captcha_controller, "verify_captcha", fake_verify_captcha)

    valid, message = await human_challenge_service.verify(
        captcha_id="cid",
        captcha_code="1234",
        turnstile_token="",
        config={"login_challenge_enabled": True, "login_challenge_type": "turnstile"},
    )

    assert valid is True
    assert message == ""


@pytest.mark.anyio
async def test_turnstile_fallback_rejects_bad_captcha(monkeypatch):
    async def fake_verify_captcha(captcha_id, captcha_code, *, consume=True):
        return False

    monkeypatch.setattr(human_challenge_module.captcha_controller, "verify_captcha", fake_verify_captcha)

    valid, message = await human_challenge_service.verify(
        captcha_id="cid",
        captcha_code="bad",
        turnstile_token="",
        config={"login_challenge_enabled": True, "login_challenge_type": "turnstile"},
    )

    assert valid is False
    assert "Turnstile" in message


@pytest.mark.anyio
async def test_both_mode_requires_turnstile_token(monkeypatch):
    async def fake_verify_captcha(captcha_id, captcha_code, *, consume=True):
        return True

    monkeypatch.setattr(human_challenge_module.captcha_controller, "verify_captcha", fake_verify_captcha)

    valid, message = await human_challenge_service.verify(
        captcha_id="cid",
        captcha_code="1234",
        turnstile_token="",
        config={"login_challenge_enabled": True, "login_challenge_type": "both"},
    )

    assert valid is False
    assert "Turnstile" in message
