import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.controllers.ticket import TicketController


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
                AsyncMock(return_value={"customer_service_auto_approve_ticket": True}),
            ),
            patch("app.controllers.ticket.User.filter") as mock_filter,
        ):
            mock_filter.return_value.order_by.return_value.first = AsyncMock(return_value=tech_user)

            result = await controller.create_ticket_with_optional_auto_review(
                submitter_id=3,
                payload={"title": "Demo"},
            )

        mock_create.assert_awaited_once_with(
            submitter_id=3,
            payload={"title": "Demo"},
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
                AsyncMock(return_value={"customer_service_auto_approve_ticket": False}),
            ),
        ):
            result = await controller.create_ticket_with_optional_auto_review(
                submitter_id=4,
                payload={"title": "Demo"},
            )

        mock_create.assert_awaited_once_with(
            submitter_id=4,
            payload={"title": "Demo"},
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
                AsyncMock(return_value={"customer_service_auto_approve_ticket": True}),
            ),
            patch("app.controllers.ticket.User.filter") as mock_filter,
        ):
            mock_filter.return_value.order_by.return_value.first = AsyncMock(return_value=None)

            result = await controller.create_ticket_with_optional_auto_review(
                submitter_id=5,
                payload={"title": "Demo"},
            )

        mock_create.assert_awaited_once_with(
            submitter_id=5,
            payload={"title": "Demo"},
            notify_pending_review=False,
        )
        mock_review.assert_not_awaited()
        mock_notify.assert_awaited_once_with(ticket=created_ticket, operator_id=5)
        return result

    result = asyncio.run(run())

    assert result.status == "pending_review"
