import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.controllers.ticket import TicketController
from app.models.enums import TicketActionType, TicketStatus


class TicketAssignTechTestCase(unittest.TestCase):
    def test_assign_tech_updates_processing_ticket_and_writes_action(self):
        controller = TicketController()
        ticket = SimpleNamespace(
            id=101,
            status=TicketStatus.TECH_PROCESSING,
            tech_id=12,
            save=AsyncMock(),
        )

        async def run():
            with (
                patch.object(controller, "get_ticket", AsyncMock(return_value=ticket)),
                patch.object(controller, "_write_action", AsyncMock()) as write_action,
                patch.object(controller, "_notify_ticket_status_if_needed", AsyncMock()) as notify,
                patch("app.controllers.ticket.User.filter") as user_filter,
            ):
                user_filter.return_value.first = AsyncMock(return_value=MagicMock(id=13))

                result = await controller.assign_tech(
                    ticket_id=101,
                    operator_id=7,
                    tech_id=13,
                    comment="转给张工处理",
                )

            self.assertEqual(result.tech_id, 13)
            ticket.save.assert_awaited_once()
            write_action.assert_awaited_once_with(
                ticket_id=101,
                action=TicketActionType.TECH_ASSIGN,
                from_status=TicketStatus.TECH_PROCESSING,
                to_status=TicketStatus.TECH_PROCESSING,
                operator_id=7,
                comment="转给张工处理",
            )
            notify.assert_awaited_once_with(ticket=ticket, operator_id=7)

        asyncio.run(run())

    def test_assign_tech_rejects_non_processing_ticket(self):
        controller = TicketController()
        ticket = SimpleNamespace(id=101, status=TicketStatus.DONE, tech_id=12)

        async def run():
            with patch.object(controller, "get_ticket", AsyncMock(return_value=ticket)):
                with self.assertRaises(HTTPException) as ctx:
                    await controller.assign_tech(ticket_id=101, operator_id=7, tech_id=13, comment=None)
                self.assertEqual(ctx.exception.status_code, 400)

        asyncio.run(run())


class TicketAssignTechApiTestCase(unittest.TestCase):
    def test_tech_role_can_assign_own_ticket(self):
        from app.api.v1.tickets import tickets as ticket_api

        current_user = SimpleNamespace(id=12, is_superuser=False)
        current_ticket = SimpleNamespace(id=101, tech_id=12)
        assigned_ticket = SimpleNamespace(id=101, tech_id=13, to_dict=AsyncMock(return_value={"id": 101, "tech_id": 13}))

        async def run():
            with (
                patch.object(ticket_api, "_get_current_user", AsyncMock(return_value=current_user)),
                patch.object(ticket_api, "_get_user_role_names", AsyncMock(return_value=["技术"])),
                patch.object(ticket_api.ticket_controller, "get_ticket", AsyncMock(return_value=current_ticket)),
                patch.object(ticket_api.ticket_controller, "assign_tech", AsyncMock(return_value=assigned_ticket)) as assign_tech,
            ):
                response = await ticket_api.assign_ticket_tech(
                    ticket_api.TicketAssignTechIn(ticket_id=101, tech_id=13, comment="交给李工")
                )

            assign_tech.assert_awaited_once_with(ticket_id=101, operator_id=12, tech_id=13, comment="交给李工")
            return response

        response = asyncio.run(run())

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
