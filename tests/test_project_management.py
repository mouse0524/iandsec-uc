from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.controllers import project as project_module
from app.controllers.project import project_controller


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_project_payload_uses_configured_products_and_statuses(monkeypatch):
    async def fake_config():
        return {
            "project_products": ["安得卫士"],
            "project_statuses": ["售前", "待实施", "实施中", "待验收", "已验收", "丢单"],
            "project_regions": ["华东"],
            "project_activity_types": ["迁移库"],
        }

    monkeypatch.setattr(project_module.system_setting_controller, "get_full_dict", fake_config)

    data = await project_controller._validate_payload(
        {"project_name": "项目A", "product_points": [{"product_name": "安得卫士", "points": -3}]}
    )
    assert data["status"] == "售前"
    assert data["product_points"] == [{"product_name": "安得卫士", "points": 0}]

    data = await project_controller._validate_payload(
        {"project_name": "项目A", "region": "华东", "product_points": [{"product_name": "安得卫士", "points": 1}]}
    )
    assert data["region"] == "华东"

    with pytest.raises(HTTPException):
        await project_controller._validate_payload(
            {"project_name": "项目A", "product_points": [{"product_name": "未配置产品", "points": 1}]}
        )

    with pytest.raises(HTTPException):
        await project_controller._validate_payload(
            {"project_name": "项目A", "region": "华南", "product_points": [{"product_name": "安得卫士", "points": 1}]}
        )


@pytest.mark.anyio
async def test_project_row_counts_linked_tickets_and_activities(monkeypatch):
    class CountQuery:
        def __init__(self, count):
            self._count = count

        async def count(self):
            return self._count

    class FakeTicket:
        @staticmethod
        def filter(**kwargs):
            assert kwargs.get("company_name") == "项目A"
            if kwargs.get("issue_type") == "现网问题":
                return CountQuery(2)
            if kwargs.get("issue_type") == "现网需求":
                return CountQuery(1)
            return CountQuery(0)

    class FakeActivity:
        @staticmethod
        def filter(**kwargs):
            return CountQuery(3 if kwargs.get("project_id") == 9 else 0)

    project_dict = {
        "id": 9,
        "project_name": "项目A",
    }
    project = SimpleNamespace(
        id=9,
        project_name="项目A",
        assignee_id=None,
        created_by=1,
    )

    async def fake_to_dict():
        return dict(project_dict)

    async def fake_user_name(user_id):
        return "管理员" if user_id else ""

    project.to_dict = fake_to_dict
    monkeypatch.setattr(project_module, "Ticket", FakeTicket)
    monkeypatch.setattr(project_module, "ProjectActivity", FakeActivity)
    monkeypatch.setattr(project_controller, "_user_name", fake_user_name)

    row = await project_controller._project_row(project)

    assert row["issue_count"] == 2
    assert row["requirement_count"] == 1
    assert row["activity_count"] == 3


@pytest.mark.anyio
async def test_visible_projects_filter_by_assignee(monkeypatch):
    calls = {}

    class AwaitableList(list):
        def __await__(self):
            async def _coro():
                return self

            return _coro().__await__()

    class FakeProject:
        @staticmethod
        def filter(q):
            calls["q"] = q
            return AwaitableList()

    monkeypatch.setattr(project_module, "Project", FakeProject)

    await project_controller.visible_projects_for_user(7)

    assert calls["q"].filters == {"assignee_id": 7}
