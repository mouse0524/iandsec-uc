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


def test_webdav_public_base_url_is_not_exposed():
    assert "webdav_public_base_url" not in SystemSettingUpdateIn.model_fields


def test_ticket_cs_review_project_phases_must_be_subset_of_project_phases():
    payload = minimal_settings_payload(
        ticket_project_phases=["售前", "实施", "售后"],
        ticket_cs_review_project_phases=["实施", "售后"],
    )

    data = SystemSettingUpdateIn(**payload)

    assert data.ticket_cs_review_project_phases == ["实施", "售后"]


def test_ticket_cs_review_project_phases_rejects_unknown_phase():
    payload = minimal_settings_payload(
        ticket_project_phases=["售前", "实施"],
        ticket_cs_review_project_phases=["实施", "售后"],
    )

    with pytest.raises(ValidationError):
        SystemSettingUpdateIn(**payload)


def test_ticket_cs_review_project_phases_can_be_updated_without_project_phases():
    payload = minimal_settings_payload(
        ticket_cs_review_project_phases=["实施", "售后"],
    )
    payload.pop("ticket_project_phases")

    data = SystemSettingUpdateIn(**payload)

    assert data.ticket_cs_review_project_phases == ["实施", "售后"]
    assert "ticket_project_phases" not in data.model_fields_set


def test_ticket_issue_types_defaults_and_normalizes_values():
    payload = minimal_settings_payload(
        ticket_issue_types=[" 问题 ", "需求", "需求", "建议", "咨询"],
    )

    data = SystemSettingUpdateIn(**payload)

    assert data.ticket_issue_types == ["问题", "需求", "建议", "咨询"]


def test_ticket_issue_types_rejects_empty_values():
    payload = minimal_settings_payload(ticket_issue_types=["", " "])

    with pytest.raises(ValidationError):
        SystemSettingUpdateIn(**payload)


def test_ticket_impact_scopes_defaults_and_normalizes_values():
    payload = minimal_settings_payload(
        ticket_impact_scopes=[" 全部 ", "偶现", "偶现", "单台必现", "单台偶现"],
    )

    data = SystemSettingUpdateIn(**payload)

    assert data.ticket_impact_scopes == ["全部", "偶现", "单台必现", "单台偶现"]


def test_ticket_impact_scopes_rejects_empty_values():
    payload = minimal_settings_payload(ticket_impact_scopes=["", " "])

    with pytest.raises(ValidationError):
        SystemSettingUpdateIn(**payload)


def test_redmine_project_id_accepts_identifier_text():
    payload = minimal_settings_payload(redmine_project_id=" customer-portal ")

    data = SystemSettingUpdateIn(**payload)

    assert data.redmine_project_id == "customer-portal"


def test_redmine_visible_fields_accepts_project_id():
    payload = minimal_settings_payload(redmine_sync_visible_fields=["project_id", "tracker_id", "project_id"])

    data = SystemSettingUpdateIn(**payload)

    assert data.redmine_sync_visible_fields == ["project_id", "tracker_id"]


def test_redmine_sync_options_normalizes_selected_values():
    payload = minimal_settings_payload(
        redmine_sync_options={
            "project_id": [" demo ", "demo", ""],
            "tracker_id": [8, "9", None],
            "priority_id": ["2"],
            "assigned_to_id": ["7"],
            "project_phase": ["实施"],
            "os": [" Windows ", "Linux"],
            "unknown": ["x"],
        }
    )

    data = SystemSettingUpdateIn(**payload)

    assert data.redmine_sync_options == {
        "project_id": ["demo"],
        "tracker_id": ["8", "9"],
        "priority_id": ["2"],
        "assigned_to_id": ["7"],
        "project_phase": ["实施"],
        "os": ["Windows", "Linux"],
    }


def minimal_settings_payload(**overrides):
    payload = {
        "site_title": "Test",
        "ticket_attachment_extensions": ["zip"],
        "ticket_project_phases": ["售前"],
        "ticket_issue_types": ["现网问题"],
        "ticket_impact_scopes": ["全部"],
        "ticket_categories": ["登录问题"],
        "ticket_root_causes": ["配置错误"],
        "ticket_description_templates": ["问题现象："],
        "password_required_categories": ["letter"],
    }
    payload.update(overrides)
    return payload
