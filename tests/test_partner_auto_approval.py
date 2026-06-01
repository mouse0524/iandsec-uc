from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.partner import partner as partner_module
from app.api.v1.base import base as base_module
from app.api.v1.settings import settings as settings_module
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


def _base_client():
    app = FastAPI()
    app.include_router(base_module.router, prefix="/api/v1/base")
    return TestClient(app)


def _settings_client():
    app = FastAPI()
    app.include_router(settings_module.router, prefix="/api/v1/settings")
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


def _user_payload():
    data = _payload()
    data["register_type"] = RegisterType.USER.value
    data["hardware_id"] = "HW-001"
    return data


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


def test_partner_register_rejects_when_channel_register_disabled():
    with (
        patch.object(
            partner_module.system_setting_controller,
            "get_public_config",
            AsyncMock(
                return_value={
                    "allow_partner_register": True,
                    "allow_channel_register": False,
                    "allow_user_register": True,
                    "customer_service_auto_approve_register": False,
                }
            ),
        ),
        patch.object(partner_module.mail_controller, "verify_email_code", AsyncMock()) as mock_verify,
        patch.object(partner_module.partner_controller, "register", AsyncMock()) as mock_register,
    ):
        response = _client().post("/api/v1/partner/register", json=_payload())

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == 403
    assert "渠道商注册" in body["msg"]
    mock_verify.assert_not_awaited()
    mock_register.assert_not_awaited()


def test_partner_register_rejects_when_user_register_disabled():
    with (
        patch.object(
            partner_module.system_setting_controller,
            "get_public_config",
            AsyncMock(
                return_value={
                    "allow_partner_register": True,
                    "allow_channel_register": True,
                    "allow_user_register": False,
                    "customer_service_auto_approve_register": False,
                }
            ),
        ),
        patch.object(partner_module.mail_controller, "verify_email_code", AsyncMock()) as mock_verify,
        patch.object(partner_module.partner_controller, "register", AsyncMock()) as mock_register,
    ):
        response = _client().post("/api/v1/partner/register", json=_user_payload())

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == 403
    assert "用户注册" in body["msg"]
    mock_verify.assert_not_awaited()
    mock_register.assert_not_awaited()


def test_send_email_code_rejects_disabled_register_type():
    payload = {
        "email": "new@example.com",
        "captcha_id": "captcha-1",
        "captcha_code": "1234",
        "register_type": RegisterType.USER.value,
    }
    with (
        patch.object(
            base_module.system_setting_controller,
            "get_public_config",
            AsyncMock(
                return_value={
                    "allow_partner_register": True,
                    "allow_channel_register": True,
                    "allow_user_register": False,
                }
            ),
        ),
        patch.object(base_module.User, "filter") as mock_user_filter,
        patch.object(base_module.PartnerRegistration, "filter") as mock_registration_filter,
        patch.object(base_module.captcha_controller, "verify_captcha", AsyncMock()) as mock_captcha,
        patch.object(base_module.mail_controller, "send_partner_verify_code", AsyncMock()) as mock_send,
    ):
        response = _base_client().post("/api/v1/base/send_email_code", json=payload)

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == 403
    assert "用户注册" in body["msg"]
    mock_user_filter.assert_not_called()
    mock_registration_filter.assert_not_called()
    mock_captcha.assert_not_awaited()
    mock_send.assert_not_awaited()


def test_settings_update_preserves_legacy_register_toggle_when_new_fields_missing():
    legacy_payload = {
        "site_title": "Demo",
        "allow_partner_register": False,
        "customer_service_auto_approve_register": False,
        "ticket_attachment_extensions": ["zip"],
        "ticket_project_phases": ["售后"],
        "ticket_issue_types": ["现网问题"],
        "ticket_impact_scopes": ["全部"],
        "ticket_categories": ["其他"],
        "customer_service_auto_approve_ticket": False,
        "ticket_root_causes": ["配置错误"],
        "ticket_description_templates": ["问题现象："],
    }
    with (
        patch.object(settings_module.system_setting_controller, "update", AsyncMock()) as mock_update,
        patch.object(settings_module.system_setting_controller, "get_safe_dict", AsyncMock(return_value={})),
    ):
        response = _settings_client().post("/api/v1/settings/update", json=legacy_payload)

    assert response.status_code == 200
    payload = mock_update.await_args.args[0]
    assert payload["allow_partner_register"] is False
    assert "allow_channel_register" not in payload
    assert "allow_user_register" not in payload


def test_settings_update_preserves_database_backup_fields_when_missing():
    legacy_payload = {
        "site_title": "Demo",
        "allow_partner_register": True,
        "customer_service_auto_approve_register": False,
        "ticket_attachment_extensions": ["zip"],
        "ticket_project_phases": ["after-sales"],
        "ticket_categories": ["other"],
        "customer_service_auto_approve_ticket": False,
        "ticket_root_causes": ["config"],
        "ticket_description_templates": ["desc"],
    }
    with (
        patch.object(settings_module.system_setting_controller, "update", AsyncMock()) as mock_update,
        patch.object(settings_module.system_setting_controller, "get_safe_dict", AsyncMock(return_value={})),
    ):
        response = _settings_client().post("/api/v1/settings/update", json=legacy_payload)

    assert response.status_code == 200
    payload = mock_update.await_args.args[0]
    assert "db_backup_enabled" not in payload
    assert "db_backup_directory" not in payload
    assert "db_backup_mysql_container" not in payload
    assert "db_backup_webdav_base_url" not in payload
    assert "db_backup_webdav_username" not in payload
    assert "db_backup_webdav_password" not in payload
    assert "db_backup_run_at" not in payload
    assert "db_backup_retention_days" not in payload
    assert "ticket_issue_types" not in payload
    assert "ticket_impact_scopes" not in payload
    assert "webdav_public_base_url" not in payload


def test_database_backup_run_uses_scheduler_lock():
    with (
        patch.object(
            settings_module.system_setting_controller,
            "get_full_dict",
            AsyncMock(return_value={"db_backup_directory": "D:/nas/backups"}),
        ),
        patch.object(
            settings_module.database_backup_scheduler,
            "run_once",
            AsyncMock(return_value=None),
        ) as mock_run_once,
        patch.object(
            settings_module.database_backup_service,
            "run_once",
            AsyncMock(side_effect=AssertionError("manual backup must use scheduler lock")),
        ),
    ):
        response = _settings_client().post(
            "/api/v1/settings/database-backup/run",
            json={"db_backup_directory": "D:/nas/backups"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"ok": True, "skipped": True, "reason": "locked"}
    mock_run_once.assert_awaited_once()
    assert mock_run_once.await_args.kwargs["force"] is True
