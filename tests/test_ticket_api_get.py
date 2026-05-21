import unittest
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api.v1.tickets import tickets as tickets_module
from app.core.dependency import AuthControl


class TicketGetApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(tickets_module.router, prefix="/api/v1/tickets")

        async def _fake_auth():
            return SimpleNamespace(id=1)

        self.app.dependency_overrides[AuthControl.is_authed] = _fake_auth
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_get_ticket_forbidden(self):
        current_user = SimpleNamespace(id=10, is_superuser=False)
        ticket = SimpleNamespace(id=1001, submitter_id=11, tech_id=12, status="pending_review")

        with (
            patch.object(tickets_module, "_get_current_user", AsyncMock(return_value=current_user)),
            patch.object(tickets_module, "_get_user_role_names", AsyncMock(return_value=[])),
            patch.object(tickets_module.Ticket, "get", AsyncMock(return_value=ticket)),
        ):
            resp = self.client.get("/api/v1/tickets/get", params={"ticket_id": 1001})

        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertEqual(body.get("code"), 403)

    def test_get_ticket_success_for_admin(self):
        current_user = SimpleNamespace(id=10, is_superuser=False)
        ticket = SimpleNamespace(id=1001, submitter_id=11, tech_id=12, status="done")
        detail = {"id": 1001, "title": "demo"}

        with (
            patch.object(tickets_module, "_get_current_user", AsyncMock(return_value=current_user)),
            patch.object(tickets_module, "_get_user_role_names", AsyncMock(return_value=["管理员"])),
            patch.object(tickets_module.Ticket, "get", AsyncMock(return_value=ticket)),
            patch.object(tickets_module.ticket_controller, "get_ticket_detail", AsyncMock(return_value=detail)),
        ):
            resp = self.client.get("/api/v1/tickets/get", params={"ticket_id": 1001})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body.get("code"), 200)
        self.assertEqual(body.get("data", {}).get("id"), 1001)

    def test_list_ticket_for_tech_role_applies_scope_filter(self):
        current_user = SimpleNamespace(id=10, is_superuser=False)

        with (
            patch.object(tickets_module, "_get_current_user", AsyncMock(return_value=current_user)),
            patch.object(tickets_module, "_get_user_role_names", AsyncMock(return_value=["技术"])),
            patch.object(tickets_module.ticket_controller, "list_tickets", AsyncMock(return_value=(1, [{"id": 1}])) ) as mock_list,
        ):
            resp = self.client.get("/api/v1/tickets/list", params={"page": 1, "page_size": 10})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body.get("code"), 200)
        self.assertEqual(body.get("total"), 1)

        call_kwargs = mock_list.await_args.kwargs
        self.assertEqual(call_kwargs.get("page"), 1)
        self.assertEqual(call_kwargs.get("page_size"), 10)

        search_q = call_kwargs.get("search")
        self.assertEqual(getattr(search_q, "join_type", ""), "AND")
        scope_q = search_q.children[-1]
        self.assertEqual(getattr(scope_q, "join_type", ""), "AND")
        self.assertEqual(scope_q.filters.get("tech_id"), 10)

    def test_ticket_actions_forbidden(self):
        current_user = SimpleNamespace(id=10, is_superuser=False)
        ticket = SimpleNamespace(id=1001, submitter_id=11, tech_id=12, status="pending_review")

        with (
            patch.object(tickets_module, "_get_current_user", AsyncMock(return_value=current_user)),
            patch.object(tickets_module, "_get_user_role_names", AsyncMock(return_value=[])),
            patch.object(tickets_module.Ticket, "get", AsyncMock(return_value=ticket)),
        ):
            resp = self.client.get("/api/v1/tickets/actions", params={"ticket_id": 1001})

        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertEqual(body.get("code"), 403)

    def test_export_ticket_includes_detail_fields(self):
        current_user = SimpleNamespace(id=10, is_superuser=True)
        created_at = datetime(2026, 5, 21, 9, 10, 11)
        ticket = SimpleNamespace(
            id=1001,
            ticket_no="TK001",
            status="done",
            project_phase="售后",
            category="系统异常",
            root_cause="配置错误",
            title="导出测试",
            company_name="安得",
            contact_name="张三",
            email="zhangsan@example.com",
            phone="13800000000",
            submitter_id=11,
            reviewer_id=12,
            tech_id=13,
            description="<p>第一行<br>第二行</p>",
            reject_reason="",
            created_at=created_at,
            updated_at=created_at,
            finished_at=created_at,
        )
        attachment = SimpleNamespace(ticket_id=1001, origin_name="截图.png", file_size=123)
        action = SimpleNamespace(
            ticket_id=1001,
            action="finish",
            from_status="tech_processing",
            to_status="done",
            operator_id=13,
            comment="处理完成",
            created_at=created_at,
        )

        class FakeTicketQuery:
            async def count(self):
                return 1

            def order_by(self, *args):
                return self

            def limit(self, value):
                return self

            def __await__(self):
                async def _result():
                    return [ticket]

                return _result().__await__()

        class FakeRowsQuery:
            def __init__(self, rows):
                self.rows = rows

            def order_by(self, *args):
                return self

            def __await__(self):
                async def _result():
                    return self.rows

                return _result().__await__()

        with (
            patch.object(tickets_module, "_get_current_user", AsyncMock(return_value=current_user)),
            patch.object(tickets_module, "_get_user_role_names", AsyncMock(return_value=["管理员"])),
            patch.object(tickets_module.Ticket, "filter", return_value=FakeTicketQuery()),
            patch.object(tickets_module.TicketAttachment, "filter", return_value=FakeRowsQuery([attachment])),
            patch.object(tickets_module.TicketActionLog, "filter", return_value=FakeRowsQuery([action])),
            patch.object(
                tickets_module.user_controller,
                "get_user_basic",
                AsyncMock(side_effect=lambda uid: {"alias": f"用户{uid}", "username": f"user{uid}"}),
            ),
        ):
            resp = self.client.get("/api/v1/tickets/export")

        self.assertEqual(resp.status_code, 200)
        workbook = load_workbook(BytesIO(resp.content))
        sheet = workbook.active
        values = [cell.value for cell in sheet[2]]
        self.assertIn("安得", values)
        self.assertIn("张三", values)
        self.assertIn("第一行\n第二行", values)
        self.assertTrue(any("截图.png" in str(value) for value in values))
        self.assertTrue(any("处理完成" in str(value) for value in values))

    def test_export_ticket_keeps_description_image_sources(self):
        current_user = SimpleNamespace(id=10, is_superuser=True)
        created_at = datetime(2026, 5, 21, 9, 10, 11)
        ticket = SimpleNamespace(
            id=1001,
            ticket_no="TK001",
            status="done",
            project_phase="售后",
            category="系统异常",
            root_cause="配置错误",
            title="导出测试",
            company_name="安得",
            contact_name="张三",
            email="zhangsan@example.com",
            phone="13800000000",
            submitter_id=11,
            reviewer_id=None,
            tech_id=None,
            description='<p>现象</p><img src="/api/v1/ticket/attachment/download?attachment_id=99">',
            reject_reason="",
            created_at=created_at,
            updated_at=created_at,
            finished_at=created_at,
        )

        class FakeTicketQuery:
            async def count(self):
                return 1

            def order_by(self, *args):
                return self

            def limit(self, value):
                return self

            def __await__(self):
                async def _result():
                    return [ticket]

                return _result().__await__()

        class FakeRowsQuery:
            def order_by(self, *args):
                return self

            def __await__(self):
                async def _result():
                    return []

                return _result().__await__()

        with (
            patch.object(tickets_module, "_get_current_user", AsyncMock(return_value=current_user)),
            patch.object(tickets_module, "_get_user_role_names", AsyncMock(return_value=["管理员"])),
            patch.object(tickets_module.Ticket, "filter", return_value=FakeTicketQuery()),
            patch.object(tickets_module.TicketAttachment, "filter", return_value=FakeRowsQuery()),
            patch.object(tickets_module.TicketActionLog, "filter", return_value=FakeRowsQuery()),
            patch.object(tickets_module.user_controller, "get_user_basic", AsyncMock(return_value={"alias": "用户"})),
        ):
            resp = self.client.get("/api/v1/tickets/export")

        self.assertEqual(resp.status_code, 200)
        workbook = load_workbook(BytesIO(resp.content))
        values = [cell.value for cell in workbook.active[2]]
        self.assertTrue(any("/api/v1/ticket/attachment/download?attachment_id=99" in str(value) for value in values))

    def test_export_ticket_rejects_too_many_rows_with_http_error(self):
        current_user = SimpleNamespace(id=10, is_superuser=True)

        class FakeTicketQuery:
            async def count(self):
                return tickets_module.TICKET_EXPORT_MAX_ROWS + 1

        with (
            patch.object(tickets_module, "_get_current_user", AsyncMock(return_value=current_user)),
            patch.object(tickets_module, "_get_user_role_names", AsyncMock(return_value=["管理员"])),
            patch.object(tickets_module.Ticket, "filter", return_value=FakeTicketQuery()),
        ):
            resp = self.client.get("/api/v1/tickets/export")

        self.assertEqual(resp.status_code, 400)
        self.assertIn("导出数据量过大", resp.json().get("detail", ""))


if __name__ == "__main__":
    unittest.main()
