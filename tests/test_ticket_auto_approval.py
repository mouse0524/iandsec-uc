import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.controllers.ticket import TicketController
from app.models.enums import TicketActionType, TicketStatus


def test_ticket_create_auto_approves_when_enabled():
    controller = TicketController()
    created_ticket = SimpleNamespace(id=201, status="pending_review")
    approved_ticket = SimpleNamespace(id=201, status="tech_processing")
    tech_user = SimpleNamespace(id=12)

    async def run():
        with (
            patch.object(controller, "create_ticket", AsyncMock(return_value=created_ticket)) as mock_create,
            patch.object(
                controller,
                "set_customer_service_review",
                AsyncMock(return_value=approved_ticket),
            ) as mock_review,
            patch(
                "app.controllers.ticket.system_setting_controller.get_public_config",
                AsyncMock(
                    return_value={
                        "customer_service_auto_approve_ticket": True,
                        "ticket_cs_review_project_phases": ["实施", "售后"],
                    }
                ),
            ),
            patch("app.controllers.ticket.User.filter") as mock_filter,
        ):
            mock_filter.return_value.order_by.return_value.first = AsyncMock(return_value=tech_user)

            result = await controller.create_ticket_with_optional_auto_review(
                submitter_id=3,
                payload={"title": "Demo", "project_phase": "实施"},
            )

        mock_create.assert_awaited_once_with(
            submitter_id=3,
            payload={"title": "Demo", "project_phase": "实施"},
            notify_pending_review=False,
        )
        mock_review.assert_awaited_once_with(
            ticket_id=201,
            reviewer_id=0,
            approved=True,
            comment="客服自动审批",
            tech_id=12,
        )
        return result

    result = asyncio.run(run())

    assert result.status == "tech_processing"


def test_ticket_create_waits_for_review_when_auto_approve_disabled():
    controller = TicketController()
    created_ticket = SimpleNamespace(id=202, status="pending_review")

    async def run():
        with (
            patch.object(controller, "create_ticket", AsyncMock(return_value=created_ticket)) as mock_create,
            patch.object(controller, "set_customer_service_review", AsyncMock()) as mock_review,
            patch(
                "app.controllers.ticket.system_setting_controller.get_public_config",
                AsyncMock(
                    return_value={
                        "customer_service_auto_approve_ticket": False,
                        "ticket_cs_review_project_phases": ["实施", "售后"],
                    }
                ),
            ),
        ):
            result = await controller.create_ticket_with_optional_auto_review(
                submitter_id=4,
                payload={"title": "Demo", "project_phase": "实施"},
            )

        mock_create.assert_awaited_once_with(
            submitter_id=4,
            payload={"title": "Demo", "project_phase": "实施"},
            notify_pending_review=True,
        )
        mock_review.assert_not_awaited()
        return result

    result = asyncio.run(run())

    assert result.status == "pending_review"


def test_ticket_create_notifies_pending_when_auto_approve_has_no_tech_user():
    controller = TicketController()
    created_ticket = SimpleNamespace(id=203, status="pending_review")

    async def run():
        with (
            patch.object(controller, "create_ticket", AsyncMock(return_value=created_ticket)) as mock_create,
            patch.object(controller, "_notify_ticket_status_if_needed", AsyncMock()) as mock_notify,
            patch.object(controller, "set_customer_service_review", AsyncMock()) as mock_review,
            patch(
                "app.controllers.ticket.system_setting_controller.get_public_config",
                AsyncMock(
                    return_value={
                        "customer_service_auto_approve_ticket": True,
                        "ticket_cs_review_project_phases": ["实施", "售后"],
                    }
                ),
            ),
            patch("app.controllers.ticket.User.filter") as mock_filter,
        ):
            mock_filter.return_value.order_by.return_value.first = AsyncMock(return_value=None)

            result = await controller.create_ticket_with_optional_auto_review(
                submitter_id=5,
                payload={"title": "Demo", "project_phase": "实施"},
            )

        mock_create.assert_awaited_once_with(
            submitter_id=5,
            payload={"title": "Demo", "project_phase": "实施"},
            notify_pending_review=False,
        )
        mock_review.assert_not_awaited()
        mock_notify.assert_awaited_once_with(ticket=created_ticket, operator_id=5)
        return result

    result = asyncio.run(run())

    assert result.status == "pending_review"


def test_ticket_create_skips_cs_review_for_non_configured_phase():
    controller = TicketController()

    class FakeTicket(SimpleNamespace):
        async def save(self):
            return None

    created_ticket = FakeTicket(id=204, status="pending_review", tech_id=None)
    tech_user = SimpleNamespace(id=13)

    async def run():
        with (
            patch.object(controller, "create_ticket", AsyncMock(return_value=created_ticket)) as mock_create,
            patch.object(controller, "_write_action", AsyncMock()) as mock_write_action,
            patch.object(controller, "_notify_ticket_status_if_needed", AsyncMock()) as mock_notify,
            patch(
                "app.controllers.ticket.system_setting_controller.get_public_config",
                AsyncMock(
                    return_value={
                        "customer_service_auto_approve_ticket": False,
                        "ticket_cs_review_project_phases": ["实施", "售后"],
                    }
                ),
            ),
            patch("app.controllers.ticket.User.filter") as mock_filter,
        ):
            mock_filter.return_value.order_by.return_value.first = AsyncMock(return_value=tech_user)

            result = await controller.create_ticket_with_optional_auto_review(
                submitter_id=6,
                payload={"title": "Demo", "project_phase": "售前"},
            )

        mock_create.assert_awaited_once_with(
            submitter_id=6,
            payload={"title": "Demo", "project_phase": "售前"},
            notify_pending_review=False,
        )
        mock_write_action.assert_awaited_once()
        mock_notify.assert_awaited_once_with(ticket=created_ticket, operator_id=6)
        return result

    result = asyncio.run(run())

    assert result.status == "tech_processing"


def test_ticket_update_from_cs_rejected_skips_cs_review_for_non_configured_phase():
    controller = TicketController()

    class FakeTicket(SimpleNamespace):
        async def save(self):
            return None

        async def refresh_from_db(self):
            return None

    ticket = FakeTicket(
        id=205,
        submitter_id=7,
        status=TicketStatus.CS_REJECTED,
        project_phase="实施",
        tech_id=None,
        reject_reason="信息需补充",
    )
    tech_user = SimpleNamespace(id=14)

    async def run():
        with (
            patch.object(controller, "get_ticket", AsyncMock(return_value=ticket)),
            patch.object(controller, "_write_action", AsyncMock()) as mock_write_action,
            patch.object(controller, "_notify_ticket_status_if_needed", AsyncMock()) as mock_notify,
            patch(
                "app.controllers.ticket.system_setting_controller.get_public_config",
                AsyncMock(
                    return_value={
                        "ticket_cs_review_project_phases": ["实施", "售后"],
                    }
                ),
            ),
            patch("app.controllers.ticket.User.filter") as mock_filter,
        ):
            mock_filter.return_value.order_by.return_value.first = AsyncMock(return_value=tech_user)

            result = await controller.update_ticket(
                ticket_id=205,
                submitter_id=7,
                payload={"project_phase": "售前"},
                attachment_ids=[],
            )

        mock_write_action.assert_awaited_once_with(
            ticket_id=205,
            action=TicketActionType.TECH_START,
            from_status=TicketStatus.CS_REJECTED,
            to_status=TicketStatus.TECH_PROCESSING,
            operator_id=7,
            comment="提交者编辑后无需客服审核，重新流转技术处理",
        )
        mock_notify.assert_awaited_once_with(ticket=ticket, operator_id=7)
        return result

    result = asyncio.run(run())

    assert result.status == TicketStatus.TECH_PROCESSING
    assert result.tech_id == 14


def test_ticket_resubmit_from_cs_rejected_skips_cs_review_when_phase_no_longer_requires_it():
    controller = TicketController()

    class FakeTicket(SimpleNamespace):
        async def save(self):
            return None

    ticket = FakeTicket(
        id=206,
        submitter_id=8,
        status=TicketStatus.CS_REJECTED,
        project_phase="售前",
        tech_id=None,
        reject_reason="信息需补充",
    )
    tech_user = SimpleNamespace(id=15)

    async def run():
        with (
            patch.object(controller, "get_ticket", AsyncMock(return_value=ticket)),
            patch.object(controller, "_write_action", AsyncMock()) as mock_write_action,
            patch.object(controller, "_notify_ticket_status_if_needed", AsyncMock()) as mock_notify,
            patch(
                "app.controllers.ticket.system_setting_controller.get_public_config",
                AsyncMock(
                    return_value={
                        "ticket_cs_review_project_phases": ["实施", "售后"],
                    }
                ),
            ),
            patch("app.controllers.ticket.User.filter") as mock_filter,
        ):
            mock_filter.return_value.order_by.return_value.first = AsyncMock(return_value=tech_user)

            result = await controller.resubmit_ticket(
                ticket_id=206,
                submitter_id=8,
                description="补充说明",
                attachment_ids=[],
            )

        mock_write_action.assert_awaited_once_with(
            ticket_id=206,
            action=TicketActionType.TECH_START,
            from_status=TicketStatus.CS_REJECTED,
            to_status=TicketStatus.TECH_PROCESSING,
            operator_id=8,
            comment="重提后无需客服审核，自动进入技术处理",
        )
        mock_notify.assert_awaited_once_with(ticket=ticket, operator_id=8)
        return result

    result = asyncio.run(run())

    assert result.status == TicketStatus.TECH_PROCESSING
    assert result.tech_id == 15
