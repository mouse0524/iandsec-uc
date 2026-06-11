import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.controllers.ticket import TicketController
from app.models.enums import TicketActionType, TicketStatus


def test_field_verify_requires_root_cause():
    controller = TicketController()
    ticket = SimpleNamespace(id=101, status=TicketStatus.TECH_PROCESSING, tech_id=12)

    async def run():
        with (
            patch.object(controller, "get_ticket", AsyncMock(return_value=ticket)),
            patch(
                "app.controllers.ticket.system_setting_controller.get_public_config",
                AsyncMock(return_value={"ticket_root_causes": ["配置错误"]}),
            ),
        ):
            try:
                await controller.set_tech_action(
                    ticket_id=101,
                    tech_id=12,
                    action=TicketActionType.FIELD_VERIFY,
                    comment="转现场验证",
                    root_cause=None,
                )
            except HTTPException as exc:
                assert exc.status_code == 400
                return
        raise AssertionError("expected HTTPException")

    asyncio.run(run())


def test_field_verify_saves_root_cause():
    controller = TicketController()
    ticket = SimpleNamespace(
        id=102,
        status=TicketStatus.TECH_PROCESSING,
        tech_id=12,
        reject_reason="",
        root_cause=None,
        save=AsyncMock(),
    )

    async def run():
        with (
            patch.object(controller, "get_ticket", AsyncMock(return_value=ticket)),
            patch.object(controller, "_write_action", AsyncMock()) as write_action,
            patch.object(controller, "_notify_ticket_status_if_needed", AsyncMock()) as notify,
            patch(
                "app.controllers.ticket.system_setting_controller.get_public_config",
                AsyncMock(return_value={"ticket_root_causes": ["配置错误"]}),
            ),
        ):
            result = await controller.set_tech_action(
                ticket_id=102,
                tech_id=12,
                action=TicketActionType.FIELD_VERIFY,
                comment="转现场验证",
                root_cause="配置错误",
            )

        assert result.status == TicketStatus.FIELD_VERIFICATION
        assert result.root_cause == "配置错误"
        ticket.save.assert_awaited_once()
        write_action.assert_awaited_once_with(
            ticket_id=102,
            action=TicketActionType.FIELD_VERIFY,
            from_status=TicketStatus.TECH_PROCESSING,
            to_status=TicketStatus.FIELD_VERIFICATION,
            operator_id=12,
            comment="转现场验证",
        )
        notify.assert_awaited_once_with(ticket=ticket, operator_id=12)

    asyncio.run(run())
