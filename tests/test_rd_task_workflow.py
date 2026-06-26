from types import SimpleNamespace

import pytest

from app.models.enums import RdTaskStatus, RdTaskType
from app.controllers.rd_task import RdTaskController
from fastapi import HTTPException


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_create_rd_task_from_ticket_defaults_requirement_to_product_review(monkeypatch):
    created_tasks = []
    created_links = []
    created_logs = []

    class FakeTaskModel:
        @staticmethod
        async def create(**kwargs):
            task = SimpleNamespace(id=8, **kwargs)
            created_tasks.append(kwargs)
            return task

    class FakeLinkModel:
        @staticmethod
        async def create(**kwargs):
            created_links.append(kwargs)
            return SimpleNamespace(**kwargs)

    class FakeLogModel:
        @staticmethod
        async def create(**kwargs):
            created_logs.append(kwargs)
            return SimpleNamespace(**kwargs)

    class FakeTicketModel:
        @staticmethod
        async def get(id):
            return SimpleNamespace(id=id, title="客户希望增加导出能力", description="希望支持批量导出")

    controller = RdTaskController(
        task_model=FakeTaskModel,
        link_model=FakeLinkModel,
        log_model=FakeLogModel,
        ticket_model=FakeTicketModel,
    )

    task = await controller.create_from_ticket(
        ticket_id=3,
        operator_id=9,
        task_type=RdTaskType.REQUIREMENT,
        title=None,
        description=None,
        priority="high",
        product_owner_id=11,
        dev_owner_id=None,
        test_owner_id=None,
        planned_version="V1.2",
    )

    assert task.status == RdTaskStatus.PENDING_PRODUCT_REVIEW
    assert created_tasks[0]["title"] == "客户希望增加导出能力"
    assert created_tasks[0]["description"] == "希望支持批量导出"
    assert created_tasks[0]["priority"] == "high"
    assert created_tasks[0]["product_owner_id"] == 11
    assert created_links == [{"ticket_id": 3, "rd_task_id": 8, "created_by": 9}]
    assert created_logs[0]["action"] == "create"
    assert created_logs[1]["action"] == "link_ticket"


@pytest.mark.anyio
async def test_complete_rd_task_records_ticket_followup_without_changing_ticket(monkeypatch):
    saved = []
    logs = []

    task = SimpleNamespace(
        id=5,
        status=RdTaskStatus.TEST_PASSED,
        result_note=None,
        save=lambda: None,
    )

    async def save():
        saved.append(task.status)

    task.save = save

    class FakeTaskModel:
        @staticmethod
        async def get(id):
            assert id == 5
            return task

    class FakeLogModel:
        @staticmethod
        async def create(**kwargs):
            logs.append(kwargs)
            return SimpleNamespace(**kwargs)

    class FakeLinkQuery:
        async def values_list(self, field, flat=False):
            assert field == "ticket_id"
            assert flat is True
            return [2, 3]

    class FakeLinkModel:
        @staticmethod
        def filter(**kwargs):
            assert kwargs == {"rd_task_id": 5}
            return FakeLinkQuery()

    controller = RdTaskController(
        task_model=FakeTaskModel,
        link_model=FakeLinkModel,
        log_model=FakeLogModel,
    )

    result = await controller.transition(
        task_id=5,
        operator_id=7,
        action="complete",
        comment="已发布到 V1.2",
        role_names=["技术"],
        is_superuser=False,
    )

    assert result["task"].status == RdTaskStatus.COMPLETED
    assert result["followup_ticket_ids"] == [2, 3]
    assert saved == [RdTaskStatus.COMPLETED]
    assert logs[0]["from_status"] == RdTaskStatus.TEST_PASSED
    assert logs[0]["to_status"] == RdTaskStatus.COMPLETED
    assert logs[0]["comment"] == "已发布到 V1.2"


@pytest.mark.anyio
async def test_transition_rejects_invalid_status_jump():
    task = SimpleNamespace(id=5, status=RdTaskStatus.PENDING_DEV)

    class FakeTaskModel:
        @staticmethod
        async def get(id):
            return task

    controller = RdTaskController(task_model=FakeTaskModel)

    with pytest.raises(HTTPException) as exc:
        await controller.transition(
            task_id=5,
            operator_id=7,
            action="test_pass",
            comment=None,
            role_names=["测试"],
            is_superuser=False,
        )

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_transition_rejects_action_outside_role_scope():
    task = SimpleNamespace(id=5, status=RdTaskStatus.PENDING_DEV)

    class FakeTaskModel:
        @staticmethod
        async def get(id):
            return task

    controller = RdTaskController(task_model=FakeTaskModel)

    with pytest.raises(HTTPException) as exc:
        await controller.transition(
            task_id=5,
            operator_id=7,
            action="dev_start",
            comment=None,
            role_names=["客服"],
            is_superuser=False,
        )

    assert exc.value.status_code == 403
