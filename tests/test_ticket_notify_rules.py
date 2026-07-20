import pytest

from app.controllers import ticket as ticket_module
from app.controllers import mail as mail_module
from app.controllers.mail import mail_controller
from app.controllers.ticket import ticket_controller
from app.models.enums import TicketStatus


class Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class AwaitableValue:
    def __init__(self, value):
        self.value = value

    def __await__(self):
        async def _result():
            return self.value

        return _result().__await__()


class UserQuery:
    def __init__(self, users):
        self.users = users

    def prefetch_related(self, *args):
        return self

    async def first(self):
        return self.users[0] if self.users else None

    def __await__(self):
        async def _result():
            return self.users

        return _result().__await__()


def user(user_id, role, email=None):
    return Obj(
        id=user_id,
        username=f"user{user_id}",
        alias=role,
        email=email or f"user{user_id}@example.com",
        is_superuser=False,
        roles=AwaitableValue([Obj(name=role)]),
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "expected_ids"),
    [
        (TicketStatus.PENDING_REVIEW, [7]),
        (TicketStatus.TECH_PROCESSING, [7]),
        (TicketStatus.PRODUCT_EVALUATION, [7]),
        (TicketStatus.TEST_FILTERING, [7]),
        (TicketStatus.RD_PROCESSING, [7]),
        (TicketStatus.TEST_VERIFICATION, [7]),
        (TicketStatus.FIELD_VERIFICATION, [7]),
        (TicketStatus.PENDING_CLOSE, []),
        (TicketStatus.CS_REJECTED, [7]),
        (TicketStatus.TECH_REJECTED, [7]),
        (TicketStatus.DONE, []),
    ],
)
async def test_ticket_notify_rules_send_to_assignee(monkeypatch, status, expected_ids):
    users = [
        user(1, "用户"),
        user(2, "客服"),
        user(3, "技术"),
        user(4, "产品"),
        user(5, "测试"),
        user(6, "研发"),
        user(7, "用户"),
        user(99, "管理员"),
    ]
    sent = []

    def fake_user_filter(**kwargs):
        if "id" in kwargs:
            return UserQuery([item for item in users if item.id == kwargs["id"]])
        return UserQuery([])

    async def fake_send(**kwargs):
        sent.append(kwargs["to_user"].id)

    monkeypatch.setattr(ticket_module.User, "filter", fake_user_filter)
    monkeypatch.setattr(ticket_module.mail_controller, "send_ticket_status_notice", fake_send)

    await ticket_controller._notify_ticket_status_if_needed(
        ticket=Obj(
            id=10,
            ticket_no="T-10",
            title="通知测试",
            status=status,
            submitter_id=1,
            tech_id=3,
            assigned_to_id=7,
        ),
        operator_id=99,
    )

    assert sent == expected_ids


@pytest.mark.anyio
async def test_ticket_notify_rules_skip_self_assignee(monkeypatch):
    sent = []

    async def fake_send(**kwargs):
        sent.append(kwargs)

    monkeypatch.setattr(ticket_module.mail_controller, "send_ticket_status_notice", fake_send)

    await ticket_controller._notify_ticket_status_if_needed(
        ticket=Obj(id=10, ticket_no="T-10", title="通知测试", status=TicketStatus.TECH_PROCESSING, assigned_to_id=7),
        operator_id=7,
    )

    assert sent == []


@pytest.mark.anyio
async def test_ticket_notice_template_includes_issue_url(monkeypatch):
    sent = []
    scheduled = []

    async def fake_setting():
        return {
            "site_base_url": "http://example.test/app",
            "ticket_notify_subject": "工单状态提醒：{ticket_no}",
            "ticket_notify_template": "请处理",
            "ticket_notify_is_html": False,
        }

    async def fake_send_email(**kwargs):
        sent.append(kwargs)

    def fake_schedule(coro, *, tag):
        scheduled.append(coro)

    monkeypatch.setattr(mail_module.system_setting_controller, "get_full_dict", fake_setting)
    monkeypatch.setattr(mail_controller, "_send_email", fake_send_email)
    monkeypatch.setattr(mail_controller, "_schedule", fake_schedule)

    await mail_controller.send_ticket_status_notice(
        ticket=Obj(id=80, ticket_no="T-80", title="链接测试"),
        to_user=Obj(id=7, username="user7", alias="用户7", email="user7@example.com"),
        status=TicketStatus.TECH_PROCESSING,
        operator_name="op",
    )
    await scheduled[0]

    assert sent[0]["content"] == "请处理\n查看链接：http://example.test/app/issue/detail/issue_id/80"


def test_ticket_url_does_not_guess_from_cors(monkeypatch):
    monkeypatch.setattr(mail_module.settings, "APP_PUBLIC_BASE_URL", "")
    monkeypatch.setattr(mail_module.settings, "CORS_ORIGINS", ["http://localhost:3100"])

    assert mail_controller._ticket_url(Obj(id=98), {}) == "/issue/detail/issue_id/98"


@pytest.mark.anyio
async def test_ticket_notice_translates_test_filtering_status(monkeypatch):
    sent = []
    scheduled = []

    async def fake_setting():
        return {
            "site_base_url": "http://example.test",
            "ticket_notify_subject": "工单状态提醒：{ticket_no}",
            "ticket_notify_template": "当前状态：{status}",
            "ticket_notify_is_html": False,
        }

    async def fake_send_email(**kwargs):
        sent.append(kwargs)

    def fake_schedule(coro, *, tag):
        scheduled.append(coro)

    monkeypatch.setattr(mail_module.system_setting_controller, "get_full_dict", fake_setting)
    monkeypatch.setattr(mail_controller, "_send_email", fake_send_email)
    monkeypatch.setattr(mail_controller, "_schedule", fake_schedule)

    await mail_controller.send_ticket_status_notice(
        ticket=Obj(id=98, ticket_no="T-98", title="状态测试"),
        to_user=Obj(id=7, username="user7", alias="用户7", email="user7@example.com"),
        status=TicketStatus.TEST_FILTERING,
        operator_name="op",
    )
    await scheduled[0]

    assert "当前状态：测试过滤" in sent[0]["content"]


@pytest.mark.anyio
async def test_ticket_notice_repairs_view_ticket_link_without_href(monkeypatch):
    sent = []
    scheduled = []

    async def fake_setting():
        return {
            "site_base_url": "http://example.test",
            "ticket_notify_subject": "工单状态提醒：{ticket_no}",
            "ticket_notify_template": (
                '<a {ticket_url} style="display:inline-block;padding:8px 12px;'
                'border-radius:6px;background:#2563eb;color:#fff;text-decoration:none;"'
                'target="_blank" rel="noopener noreferrer">查看工单</a>'
            ),
            "ticket_notify_is_html": True,
        }

    async def fake_send_email(**kwargs):
        sent.append(kwargs)

    def fake_schedule(coro, *, tag):
        scheduled.append(coro)

    monkeypatch.setattr(mail_module.system_setting_controller, "get_full_dict", fake_setting)
    monkeypatch.setattr(mail_controller, "_send_email", fake_send_email)
    monkeypatch.setattr(mail_controller, "_schedule", fake_schedule)

    await mail_controller.send_ticket_status_notice(
        ticket=Obj(id=98, ticket_no="T-98", title="链接测试"),
        to_user=Obj(id=7, username="user7", alias="用户7", email="user7@example.com"),
        status=TicketStatus.TEST_FILTERING,
        operator_name="op",
    )
    await scheduled[0]

    assert 'href="http://example.test/issue/detail/issue_id/98"' in sent[0]["content"]
    assert 'target="_blank"' in sent[0]["content"]
    assert "查看工单" in sent[0]["content"]


@pytest.mark.anyio
async def test_ticket_notice_template_replaces_ticket_url_in_href(monkeypatch):
    sent = []
    scheduled = []

    async def fake_setting():
        return {
            "site_base_url": "http://example.test",
            "ticket_notify_subject": "工单状态提醒：{ticket_no}",
            "ticket_notify_template": (
                '<div style="font-family:Arial,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;'
                'color:#1f2937;line-height:1.7;background:#f8fbff;border:1px solid #dbeafe;'
                'border-radius:12px;padding:16px 18px;"><h2 style="margin:0 0 12px;'
                'font-size:18px;color:#1d4ed8;">工单状态提醒</h2><p style="margin:0 0 8px;">'
                '您好，<b>{name}</b>：</p><p style="margin:0 0 6px;">工单ID：<b>{ticket_no}</b></p>'
                '<p style="margin:0 0 6px;">工单标题：{title}</p><p style="margin:0 0 6px;">'
                '当前状态：<b style="color:#1d4ed8;">{status}</b></p><p style="margin:0 0 6px;">'
                '操作人：{operator}</p><p style="margin:10px 0 0;"><a href="{ticket_url}" '
                'style="display:inline-block;padding:8px 12px;border-radius:6px;background:#2563eb;'
                'color:#fff;text-decoration:none;">查看工单</a></p><p style="margin:8px 0 0;'
                'color:#6b7280;">请及时登录系统处理。</p></div>'
            ),
            "ticket_notify_is_html": True,
        }

    async def fake_send_email(**kwargs):
        sent.append(kwargs)

    def fake_schedule(coro, *, tag):
        scheduled.append(coro)

    monkeypatch.setattr(mail_module.system_setting_controller, "get_full_dict", fake_setting)
    monkeypatch.setattr(mail_controller, "_send_email", fake_send_email)
    monkeypatch.setattr(mail_controller, "_schedule", fake_schedule)

    await mail_controller.send_ticket_status_notice(
        ticket=Obj(id=98, ticket_no="T-98", title="链接测试 工单编号：原始内容"),
        to_user=Obj(id=7, username="user7", alias="用户7", email="user7@example.com"),
        status=TicketStatus.TEST_FILTERING,
        operator_name="op",
    )
    await scheduled[0]

    assert 'href="http://example.test/issue/detail/issue_id/98"' in sent[0]["content"]
    assert "工单ID：<b>98</b>" in sent[0]["content"]
    assert "工单标题：链接测试 工单编号：原始内容" in sent[0]["content"]
    assert "T-98" not in sent[0]["content"]
    assert "{ticket_url}" not in sent[0]["content"]


def test_system_setting_sections_have_defaults():
    from app.controllers.system_setting import system_setting_controller

    assert system_setting_controller._SECTIONS <= system_setting_controller._DEFAULTS.keys()
