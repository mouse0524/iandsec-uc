from __future__ import annotations

import base64
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.redmine_sync_service import RedmineSyncService


class FakeTicket:
    def __init__(self, **kwargs):
        self.id = 1
        self.ticket_no = "TK-001"
        self.title = "Login error"
        self.company_name = "Customer Co"
        self.contact_name = "Alice"
        self.email = "alice@example.com"
        self.phone = "13800000000"
        self.project_phase = "实施"
        self.issue_type = "现网问题"
        self.impact_scope = "全部"
        self.category = "登录问题"
        self.root_cause = None
        self.description = "Cannot login"
        self.attachments = []
        self.status = "tech_processing"
        self.redmine_issue_id = None
        self.redmine_issue_url = None
        self.redmine_sync_status = "never"
        self.redmine_sync_error = None
        self.redmine_synced_at = None
        self.redmine_last_updated_on = None
        self.redmine_status_id = None
        self.redmine_status_name = None
        self.save_calls = 0
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def save(self):
        self.save_calls += 1

    async def to_dict(self):
        return dict(self.__dict__)


class FakeClient:
    instances = []

    def __init__(self, config):
        self.config = config
        self.calls = []
        self.uploads = []
        FakeClient.instances.append(self)

    async def create_issue(self, payload):
        self.calls.append(("create_issue", payload))
        return SimpleNamespace(id=321)

    async def update_issue(self, issue_id, payload):
        self.calls.append(("update_issue", issue_id, payload))
        return True

    async def get_issue(self, issue_id, **params):
        self.calls.append(("get_issue", issue_id, params))
        return SimpleNamespace(
            id=issue_id,
            updated_on="2026-06-01T12:00:00+08:00",
            status=SimpleNamespace(id=5, name="Resolved"),
        )

    async def upload(self, filename, content, *, content_type="application/octet-stream"):
        self.uploads.append((filename, content, content_type))
        return f"token-{len(self.uploads)}"


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch):
    FakeClient.instances = []
    monkeypatch.setattr("app.services.redmine_sync_service.RedmineClient", FakeClient)


@pytest.fixture
def config(monkeypatch):
    data = {
        "redmine_enabled": True,
        "redmine_base_url": "https://redmine.example.com/",
        "redmine_api_key": "key",
        "redmine_project_id": "demo-project",
        "redmine_tracker_id": "2",
        "redmine_priority_id": "3",
        "redmine_assigned_to_id": "7",
        "redmine_project_phase_field_id": "11",
        "redmine_os_field_id": "12",
        "redmine_sync_visible_fields": ["tracker_id", "priority_id"],
    }

    async def get_full_dict():
        return data

    monkeypatch.setattr("app.services.redmine_sync_service.system_setting_controller.get_full_dict", get_full_dict)
    return data


@pytest.mark.anyio
async def test_push_ticket_creates_redmine_issue_and_saves_reference(config):
    ticket = FakeTicket()
    service = RedmineSyncService()

    result = await service.push_ticket(ticket, operator_id=7)

    assert ticket.redmine_issue_id == 321
    assert ticket.redmine_issue_url == "https://redmine.example.com/issues/321"
    assert ticket.redmine_sync_status == "success"
    assert ticket.redmine_sync_error is None
    assert ticket.save_calls == 1
    assert result["redmine_issue_id"] == 321
    call = FakeClient.instances[0].calls[0]
    assert call[0] == "create_issue"
    assert call[1]["project_id"] == "demo-project"
    assert call[1]["tracker_id"] == 2
    assert call[1]["priority_id"] == 3
    assert call[1]["assigned_to_id"] == 7
    assert call[1]["custom_fields"] == [
        {"id": 11, "value": ticket.project_phase},
    ]
    assert call[1]["subject"] == "【Customer Co】Login error"
    assert call[1]["description"] == "\n".join(
        [
            "工单编号：TK-001",
            "项目名称：Customer Co",
            "影响范围：全部",
            "问题分类：登录问题",
            "联系人：Alice",
            "邮箱：alice@example.com",
            "电话：13800000000",
            "",
            "问题描述：",
            "Cannot login",
            "",
            "附件：",
            "-",
        ]
    )


@pytest.mark.anyio
async def test_push_ticket_can_override_redmine_tracker_priority_assignee_and_fields(config):
    ticket = FakeTicket(issue_type="现网需求")
    service = RedmineSyncService()

    await service.push_ticket(
        ticket,
        operator_id=7,
        project_id="customer-portal",
        tracker_id=9,
        priority_id=5,
        assigned_to_id=11,
        project_phase="售后",
        os_value="Linux",
    )

    payload = FakeClient.instances[0].calls[0][1]
    assert payload["project_id"] == "customer-portal"
    assert payload["tracker_id"] == 9
    assert payload["priority_id"] == 5
    assert payload["assigned_to_id"] == 11
    assert payload["custom_fields"] == [
        {"id": 11, "value": "售后"},
        {"id": 12, "value": "Linux"},
    ]


@pytest.mark.anyio
async def test_push_ticket_description_strips_html_keeps_images_and_lists_attachments(config):
    ticket = FakeTicket(
        description='<p><strong>Cannot</strong> login<br><img src="/uploads/a.png"></p>',
        attachments=[
            SimpleNamespace(origin_name="error.log"),
            {"origin_name": "screenshot.png"},
        ],
    )
    service = RedmineSyncService()

    await service.push_ticket(ticket, operator_id=7)

    description = FakeClient.instances[0].calls[0][1]["description"]
    assert "<strong>" not in description
    assert "Cannot login" in description
    assert "![](/uploads/a.png)" in description
    assert "附件：\nerror.log\nscreenshot.png" in description


@pytest.mark.anyio
async def test_push_ticket_uploads_ticket_attachments_to_redmine(config, tmp_path):
    attachment_file = tmp_path / "error.log"
    attachment_file.write_bytes(b"boom")
    ticket = FakeTicket(
        attachments=[
            SimpleNamespace(
                origin_name="error.log",
                file_path=str(attachment_file),
                mime_type="text/plain",
            )
        ]
    )
    service = RedmineSyncService()

    await service.push_ticket(ticket, operator_id=7)

    client = FakeClient.instances[0]
    payload = client.calls[0][1]
    assert client.uploads == [("error.log", b"boom", "text/plain")]
    assert payload["uploads"] == [
        {"token": "token-1", "filename": "error.log", "content_type": "text/plain"}
    ]
    assert "附件：\nerror.log" in payload["description"]


@pytest.mark.anyio
async def test_push_ticket_uploads_inline_base64_images_and_references_uploaded_name(config):
    image_bytes = b"\x89PNG\r\n\x1a\nimage"
    data_uri = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
    ticket = FakeTicket(description=f'<p>Screenshot<br><img src="{data_uri}"></p>')
    service = RedmineSyncService()

    await service.push_ticket(ticket, operator_id=7)

    client = FakeClient.instances[0]
    payload = client.calls[0][1]
    assert client.uploads == [("TK-001-image-1.png", image_bytes, "image/png")]
    assert payload["uploads"] == [
        {"token": "token-1", "filename": "TK-001-image-1.png", "content_type": "image/png"}
    ]
    assert "![](TK-001-image-1.png)" in payload["description"]
    assert data_uri not in payload["description"]


@pytest.mark.anyio
async def test_push_ticket_updates_existing_issue(config):
    ticket = FakeTicket(redmine_issue_id=88)
    service = RedmineSyncService()

    await service.push_ticket(ticket, operator_id=7, note="please sync")

    assert FakeClient.instances[0].calls[0] == (
        "update_issue",
        88,
        {
            "subject": "【Customer Co】Login error",
            "description": await service._description(ticket),
            "notes": "please sync",
        },
    )
    assert ticket.redmine_issue_id == 88
    assert ticket.redmine_sync_status == "success"


@pytest.mark.anyio
async def test_pull_ticket_saves_redmine_status_without_local_status_mutation(config):
    ticket = FakeTicket(redmine_issue_id=88, status="done")
    service = RedmineSyncService()

    await service.pull_ticket(ticket, operator_id=7)

    assert FakeClient.instances[0].calls[0] == ("get_issue", 88, {"include": "journals,attachments"})
    assert ticket.status == "done"
    assert ticket.redmine_status_id == 5
    assert ticket.redmine_status_name == "Resolved"
    assert isinstance(ticket.redmine_last_updated_on, datetime)


@pytest.mark.anyio
async def test_push_ticket_requires_enabled_redmine(monkeypatch):
    async def get_full_dict():
        return {"redmine_enabled": False}

    monkeypatch.setattr("app.services.redmine_sync_service.system_setting_controller.get_full_dict", get_full_dict)

    with pytest.raises(HTTPException) as exc_info:
        await RedmineSyncService().push_ticket(FakeTicket(), operator_id=7)

    assert exc_info.value.status_code == 400
