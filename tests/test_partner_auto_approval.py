import json
import asyncio
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


def test_database_backup_test_keeps_saved_password_when_payload_is_masked():
    with (
        patch.object(
            settings_module.system_setting_controller,
            "get_full_dict",
            AsyncMock(
                return_value={
                    "db_backup_directory": "/db",
                    "db_backup_webdav_base_url": "https://nas.example.com/dav",
                    "db_backup_webdav_username": "backup",
                    "db_backup_webdav_password": "real-secret",
                }
            ),
        ),
        patch.object(
            settings_module.database_backup_service,
            "test_directory",
            AsyncMock(return_value={"ok": True, "remote_path": "/db/.write-test.txt"}),
        ) as mock_test,
    ):
        response = _settings_client().post(
            "/api/v1/settings/database-backup/test",
            json={
                "db_backup_directory": "/db",
                "db_backup_webdav_base_url": "https://nas.example.com/dav",
                "db_backup_webdav_username": "backup",
                "db_backup_webdav_password": "******",
            },
        )

    assert response.status_code == 200
    config = mock_test.await_args.args[0]
    assert config["db_backup_webdav_password"] == "real-secret"


def test_redmine_metadata_uses_saved_api_key_when_payload_is_masked():
    class FakeRedmineClient:
        def __init__(self, config):
            self.config = config

        async def list_projects(self):
            assert self.config["redmine_api_key"] == "real-key"
            return [SimpleNamespace(id=1, identifier="demo", name="<Demo>")]

        async def list_trackers(self):
            return [SimpleNamespace(id=8, name="现网问题")]

        async def list_issue_priorities(self):
            return [SimpleNamespace(id=2, name="一般")]

        async def list_users(self):
            return [SimpleNamespace(id=7, login="tech", firstname="Tech", lastname="User")]

        async def list_custom_fields(self):
            return [SimpleNamespace(id=11, name="项目阶段")]

    with (
        patch.object(
            settings_module.system_setting_controller,
            "get_full_dict",
            AsyncMock(
                return_value={
                    "redmine_base_url": "https://redmine.example.com",
                    "redmine_api_key": "real-key",
                    "redmine_project_id": "demo",
                    "redmine_tracker_id": 8,
                    "redmine_priority_id": 2,
                    "redmine_assigned_to_id": 7,
                    "redmine_project_phase_field_id": 11,
                    "redmine_os_field_id": 12,
                    "redmine_sync_visible_fields": ["project_id", "tracker_id"],
                    "redmine_sync_options": {"project_id": ["demo"]},
                }
            ),
        ),
        patch.object(settings_module, "RedmineClient", FakeRedmineClient),
    ):
        response = _settings_client().post(
            "/api/v1/settings/redmine/metadata",
            json={
                "redmine_base_url": "https://redmine.example.com",
                "redmine_api_key": "******",
            },
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["projects"][0]["value"] == "demo"
    assert data["projects"][0]["label"] == "&lt;Demo&gt;"
    assert data["trackers"][0]["id"] == 8
    assert data["priorities"][0]["label"] == "一般"
    assert data["users"][0]["id"] == 7
    assert [item["id"] for item in data["custom_fields"]] == [11]
    assert data["redmine_project_id"] == "demo"
    assert data["redmine_tracker_id"] == 8
    assert data["redmine_priority_id"] == 2
    assert data["redmine_assigned_to_id"] == 7
    assert data["redmine_project_phase_field_id"] == 11
    assert data["redmine_os_field_id"] == 12
    assert data["redmine_sync_visible_fields"] == ["project_id", "tracker_id"]
    assert data["redmine_sync_options"] == {"project_id": ["demo"]}


def test_public_config_does_not_expose_redmine_internal_settings():
    sections = {
        "site": {"site_title": "Test", "allow_partner_register": True},
        "ticket": {},
        "login_security": {},
        "redmine": {
            "redmine_project_id": "demo",
            "redmine_tracker_id": 8,
            "redmine_sync_options": {"project_id": ["demo"]},
        },
    }

    async def fake_redis(*args, **kwargs):
        return None

    with (
        patch.object(settings_module.system_setting_controller, "_ensure_all_sections", AsyncMock(return_value=sections)),
        patch("app.controllers.system_setting.execute_redis", fake_redis),
    ):
        data = asyncio.run(settings_module.system_setting_controller.get_public_config())

    assert "site_title" in data
    assert not any(key.startswith("redmine_") for key in data)


def test_redmine_metadata_uses_redis_cache_for_empty_payload():
    async def fail_get_full_dict():
        raise AssertionError("empty metadata request should use redis cache")

    cache_data = {
        "projects": [{"label": "Demo", "value": "demo"}],
        "trackers": [{"label": "现网问题", "value": "8", "id": 8}],
        "priorities": [],
        "users": [],
        "custom_fields": [],
        "redmine_sync_options": {"project_id": ["demo"]},
    }

    async def fake_redis(command, *args, **kwargs):
        assert command == "get"
        assert args[0] == settings_module.REDMINE_METADATA_CACHE_KEY
        return json.dumps(cache_data, ensure_ascii=False)

    with (
        patch.object(settings_module.system_setting_controller, "get_full_dict", fail_get_full_dict),
        patch.object(settings_module, "execute_redis", fake_redis),
    ):
        response = _settings_client().post("/api/v1/settings/redmine/metadata", json={})

    assert response.status_code == 200
    assert response.json()["data"] == cache_data
