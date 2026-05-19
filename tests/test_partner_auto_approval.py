from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.partner import partner as partner_module
from app.models.enums import RegisterType


class FakeRegistration:
    id = 101
    email = "new@example.com"

    async def to_dict(self, exclude_fields=None):
        return {"id": self.id, "email": self.email, "status": "pending"}


class FakeApprovedRegistration(FakeRegistration):
    async def to_dict(self, exclude_fields=None):
        return {"id": self.id, "email": self.email, "status": "approved"}


def _client():
    app = FastAPI()
    app.include_router(partner_module.router, prefix="/api/v1/partner")
    return TestClient(app)


def _payload():
    return {
        "register_type": RegisterType.CHANNEL.value,
        "company_name": "Demo Co",
        "contact_name": "Alice",
        "email": "new@example.com",
        "phone": "13800138000",
        "password": "Passw0rd!",
        "email_code": "123456",
    }


def test_partner_register_auto_approves_when_enabled():
    with (
        patch.object(
            partner_module.system_setting_controller,
            "get_public_config",
            AsyncMock(return_value={"allow_partner_register": True, "customer_service_auto_approve_register": True}),
        ),
        patch.object(partner_module.mail_controller, "verify_email_code", AsyncMock(return_value=True)),
        patch.object(partner_module.partner_controller, "register", AsyncMock(return_value=FakeRegistration())),
        patch.object(partner_module.partner_controller, "review", AsyncMock(return_value=FakeApprovedRegistration())) as mock_review,
    ):
        response = _client().post("/api/v1/partner/register", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["msg"] == "注册成功，已自动审核通过"
    assert body["data"]["status"] == "approved"
    mock_review.assert_awaited_once_with(register_id=101, reviewer_id=0, approved=True, comment="客服自动审批")


def test_partner_register_waits_for_review_when_auto_approve_disabled():
    with (
        patch.object(
            partner_module.system_setting_controller,
            "get_public_config",
            AsyncMock(return_value={"allow_partner_register": True, "customer_service_auto_approve_register": False}),
        ),
        patch.object(partner_module.mail_controller, "verify_email_code", AsyncMock(return_value=True)),
        patch.object(partner_module.partner_controller, "register", AsyncMock(return_value=FakeRegistration())),
        patch.object(partner_module.partner_controller, "review", AsyncMock()) as mock_review,
    ):
        response = _client().post("/api/v1/partner/register", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["msg"] == "注册成功，请等待审核"
    assert body["data"]["status"] == "pending"
    mock_review.assert_not_awaited()
