from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.controllers.notice import NoticeController
from app.schemas.notice import NoticeCreateIn


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _NoticeUserFactory:
    created_rows = []

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    async def bulk_create(cls, rows):
        cls.created_rows.extend(rows)


class _UserQuery:
    def __init__(self, users):
        self.users = users

    async def all(self):
        return self.users


class _UserModel:
    users = []
    filter_kwargs = None

    @classmethod
    def filter(cls, **kwargs):
        cls.filter_kwargs = kwargs
        return _UserQuery(cls.users)


class _NoticeModel:
    created_payload = None

    @classmethod
    async def create(cls, **kwargs):
        cls.created_payload = kwargs
        return SimpleNamespace(id=99, title=kwargs.get("title"))


def _controller(monkeypatch, recipients):
    controller = NoticeController()
    monkeypatch.setattr(controller, "_resolve_target_user_ids", AsyncMock(return_value=recipients))
    monkeypatch.setattr(controller, "_clear_inbox_cache", AsyncMock())
    monkeypatch.setattr(controller, "_clear_unread_cache", AsyncMock())
    monkeypatch.setattr(controller, "_get_cached_unread", AsyncMock(return_value=None))
    monkeypatch.setattr(controller, "_set_cached_unread", AsyncMock())
    return controller


def _reset_fakes():
    _NoticeUserFactory.created_rows = []
    _NoticeModel.created_payload = None
    _UserModel.users = []
    _UserModel.filter_kwargs = None


@pytest.mark.anyio
async def test_create_notice_defaults_to_site_delivery(monkeypatch):
    _reset_fakes()
    controller = _controller(monkeypatch, [2, 3, 2])
    monkeypatch.setattr("app.controllers.notice.GlobalNotice", _NoticeModel)
    monkeypatch.setattr("app.controllers.notice.GlobalNoticeUser", _NoticeUserFactory)
    send_mail = AsyncMock(return_value=0)
    monkeypatch.setattr("app.controllers.notice.mail_controller.send_global_notice", send_mail)

    notice, stats = await controller.create_notice(
        creator_id=1,
        payload={"title": "通知", "content_html": "<p>内容</p>", "target_type": "all"},
    )

    assert notice.id == 99
    assert _NoticeModel.created_payload["delivery_channels"] == ["site"]
    assert [row.user_id for row in _NoticeUserFactory.created_rows] == [2, 3]
    assert stats == {"recipient_count": 2, "site_recipient_count": 2, "email_recipient_count": 0}
    send_mail.assert_not_called()


@pytest.mark.anyio
async def test_create_notice_can_send_email_without_site_inbox(monkeypatch):
    _reset_fakes()
    controller = _controller(monkeypatch, [2, 3])
    _UserModel.users = [
        SimpleNamespace(id=2, email="a@example.com"),
        SimpleNamespace(id=3, email=""),
    ]
    monkeypatch.setattr("app.controllers.notice.GlobalNotice", _NoticeModel)
    monkeypatch.setattr("app.controllers.notice.GlobalNoticeUser", _NoticeUserFactory)
    monkeypatch.setattr("app.controllers.notice.User", _UserModel)
    send_mail = AsyncMock(return_value=1)
    monkeypatch.setattr("app.controllers.notice.mail_controller.send_global_notice", send_mail)

    _, stats = await controller.create_notice(
        creator_id=1,
        payload={
            "title": "通知",
            "content_html": "<p>内容</p>",
            "target_type": "all",
            "delivery_channels": ["email"],
        },
    )

    assert _NoticeUserFactory.created_rows == []
    assert _UserModel.filter_kwargs == {"is_active": True, "id__in": [2, 3]}
    send_mail.assert_awaited_once()
    assert stats == {"recipient_count": 2, "site_recipient_count": 0, "email_recipient_count": 1}


@pytest.mark.anyio
async def test_create_notice_can_send_site_and_email(monkeypatch):
    _reset_fakes()
    controller = _controller(monkeypatch, [2, 3])
    _UserModel.users = [SimpleNamespace(id=2, email="a@example.com")]
    monkeypatch.setattr("app.controllers.notice.GlobalNotice", _NoticeModel)
    monkeypatch.setattr("app.controllers.notice.GlobalNoticeUser", _NoticeUserFactory)
    monkeypatch.setattr("app.controllers.notice.User", _UserModel)
    send_mail = AsyncMock(return_value=1)
    monkeypatch.setattr("app.controllers.notice.mail_controller.send_global_notice", send_mail)

    _, stats = await controller.create_notice(
        creator_id=1,
        payload={
            "title": "通知",
            "content_html": "<p>内容</p>",
            "target_type": "all",
            "delivery_channels": ["site", "email", "site"],
        },
    )

    assert _NoticeModel.created_payload["delivery_channels"] == ["site", "email"]
    assert len(_NoticeUserFactory.created_rows) == 2
    assert stats == {"recipient_count": 2, "site_recipient_count": 2, "email_recipient_count": 1}


@pytest.mark.anyio
async def test_create_notice_rejects_empty_delivery_channels(monkeypatch):
    _reset_fakes()
    controller = _controller(monkeypatch, [2])

    with pytest.raises(HTTPException) as exc:
        await controller.create_notice(
            creator_id=1,
            payload={
                "title": "通知",
                "content_html": "<p>内容</p>",
                "target_type": "all",
                "delivery_channels": [],
            },
        )

    assert exc.value.status_code == 400


def test_notice_schema_validates_delivery_channels():
    payload = NoticeCreateIn(
        title="通知",
        content_html="<p>内容</p>",
        target_type="all",
        delivery_channels=["site", "email", "site"],
    )
    assert payload.delivery_channels == ["site", "email"]

    with pytest.raises(ValidationError):
        NoticeCreateIn(title="通知", content_html="<p>内容</p>", target_type="all", delivery_channels=[])

    with pytest.raises(ValidationError):
        NoticeCreateIn(title="通知", content_html="<p>内容</p>", target_type="all", delivery_channels=["sms"])
