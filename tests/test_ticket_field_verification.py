import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.controllers.ticket import TicketController
from app.models.enums import TicketActionType, TicketStatus


def test_submitter_can_accept_field_verification_and_close_ticket():
    controller = TicketController()
    ticket = SimpleNamespace(
        id=101,
        status=TicketStatus.FIELD_VERIFICATION,
        submitter_id=7,
        tech_id=12,
        reject_reason="",
        finished_at=None,
        save=AsyncMock(),
    )

    async def run():
        with (
            patch.object(controller, "get_ticket", AsyncMock(return_value=ticket)),
            patch.object(controller, "_write_action", AsyncMock()) as write_action,
            patch.object(controller, "_notify_ticket_status_if_needed", AsyncMock()) as notify,
        ):
            result = await controller.set_field_verification_result(
                ticket_id=101,
                operator_id=7,
                approved=True,
                comment="关闭工单",
            )

        assert result.status == TicketStatus.DONE
        assert result.reject_reason is None
        assert result.finished_at is not None
        ticket.save.assert_awaited_once()
        write_action.assert_awaited_once_with(
            ticket_id=101,
            action=TicketActionType.CLOSE,
            from_status=TicketStatus.FIELD_VERIFICATION,
            to_status=TicketStatus.DONE,
            operator_id=7,
            comment="关闭工单",
        )
        notify.assert_awaited_once_with(ticket=ticket, operator_id=7)

    asyncio.run(run())


def test_submitter_can_reject_field_verification_back_to_tech_processing():
    controller = TicketController()
    ticket = SimpleNamespace(
        id=102,
        status=TicketStatus.FIELD_VERIFICATION,
        submitter_id=7,
        tech_id=12,
        reject_reason="",
        finished_at=None,
        save=AsyncMock(),
    )

    async def run():
        with (
            patch.object(controller, "get_ticket", AsyncMock(return_value=ticket)),
            patch.object(controller, "_write_action", AsyncMock()) as write_action,
            patch.object(controller, "_notify_ticket_status_if_needed", AsyncMock()) as notify,
        ):
            result = await controller.set_field_verification_result(
                ticket_id=102,
                operator_id=7,
                approved=False,
                comment="现场验证不通过",
            )

        assert result.status == TicketStatus.TECH_PROCESSING
        assert result.reject_reason == "现场验证不通过"
        ticket.save.assert_awaited_once()
        write_action.assert_awaited_once_with(
            ticket_id=102,
            action=TicketActionType.FIELD_REJECT,
            from_status=TicketStatus.FIELD_VERIFICATION,
            to_status=TicketStatus.TECH_PROCESSING,
            operator_id=7,
            comment="现场验证不通过",
        )
        notify.assert_awaited_once_with(ticket=ticket, operator_id=7)

    asyncio.run(run())


def test_field_verification_result_rejects_non_submitter():
    controller = TicketController()
    ticket = SimpleNamespace(id=103, status=TicketStatus.FIELD_VERIFICATION, submitter_id=7)

    async def run():
        with patch.object(controller, "get_ticket", AsyncMock(return_value=ticket)):
            try:
                await controller.set_field_verification_result(
                    ticket_id=103,
                    operator_id=8,
                    approved=True,
                    comment=None,
                )
            except HTTPException as exc:
                assert exc.status_code == 403
                return
        raise AssertionError("expected HTTPException")

    asyncio.run(run())
