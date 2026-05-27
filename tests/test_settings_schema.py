import pytest
from pydantic import ValidationError

from app.schemas.settings import SystemSettingUpdateIn


def test_webdav_signature_ttl_default_is_24_hours():
    payload = minimal_settings_payload()

    data = SystemSettingUpdateIn(**payload)

    assert data.webdav_signature_ttl == 24


def test_webdav_signature_ttl_accepts_max_9999_hours():
    payload = minimal_settings_payload(webdav_signature_ttl=9999)

    data = SystemSettingUpdateIn(**payload)

    assert data.webdav_signature_ttl == 9999


def test_webdav_signature_ttl_rejects_values_above_9999_hours():
    payload = minimal_settings_payload(webdav_signature_ttl=10000)

    with pytest.raises(ValidationError):
        SystemSettingUpdateIn(**payload)


def test_webdav_public_base_url_is_optional():
    payload = minimal_settings_payload()

    data = SystemSettingUpdateIn(**payload)

    assert data.webdav_public_base_url is None


def test_webdav_public_base_url_can_be_set():
    payload = minimal_settings_payload(webdav_public_base_url="https://files.example.com/public")

    data = SystemSettingUpdateIn(**payload)

    assert data.webdav_public_base_url == "https://files.example.com/public"


def minimal_settings_payload(**overrides):
    payload = {
        "site_title": "Test",
        "ticket_attachment_extensions": ["zip"],
        "ticket_project_phases": ["售前"],
        "ticket_categories": ["登录问题"],
        "ticket_root_causes": ["配置错误"],
        "ticket_description_templates": ["问题现象："],
        "password_required_categories": ["letter"],
    }
    payload.update(overrides)
    return payload
