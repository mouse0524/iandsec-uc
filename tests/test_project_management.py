from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.controllers import project as project_module
from app.controllers.project import project_controller
from app.core.init_app import _project_api_paths
from app.models.enums import PartnerLevel
from app.schemas.depts import DeptCreate
from app.schemas.partner import PartnerRegisterIn


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_project_activity_delete_api_is_in_permission_seed():
    assert "/api/v1/project/activity/delete" in _project_api_paths()


@pytest.mark.anyio
async def test_project_payload_uses_configured_products_and_statuses(monkeypatch):
    async def fake_config():
        return {
            "project_products": ["安得卫士"],
            "project_statuses": ["售前", "待实施", "实施中", "待验收", "已验收", "关闭"],
            "project_regions": ["华东"],
            "project_activity_types": ["迁移库"],
            "project_server_versions": ["5.6.1"],
            "project_client_versions": ["2.25"],
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

    data = await project_controller._validate_payload(
        {
            "project_name": "项目A",
            "server_version": "5.6.1",
            "client_version": "2.25",
            "product_points": [{"product_name": "安得卫士", "points": 1}],
        }
    )
    assert data["server_version"] == "5.6.1"
    assert data["client_version"] == "2.25"

    with pytest.raises(HTTPException):
        await project_controller._validate_payload(
            {"project_name": "项目A", "product_points": [{"product_name": "未配置产品", "points": 1}]}
        )

    with pytest.raises(HTTPException):
        await project_controller._validate_payload(
            {"project_name": "项目A", "region": "华南", "product_points": [{"product_name": "安得卫士", "points": 1}]}
        )

    with pytest.raises(HTTPException):
        await project_controller._validate_payload(
            {"project_name": "项目A", "server_version": "5.7", "product_points": [{"product_name": "安得卫士", "points": 1}]}
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

    class AttachmentQuery(list):
        def order_by(self, *args):
            return self

        def __await__(self):
            async def _coro():
                return self

            return _coro().__await__()

    class FakeAttachment:
        @staticmethod
        def filter(**kwargs):
            return AttachmentQuery()

    project_dict = {
        "id": 9,
        "project_name": "项目A",
    }
    project = SimpleNamespace(
        id=9,
        project_name="项目A",
        agent_id=None,
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
    monkeypatch.setattr(project_module, "ProjectAttachment", FakeAttachment)
    monkeypatch.setattr(project_controller, "_user_name", fake_user_name)

    row = await project_controller._project_row(project)

    assert row["issue_count"] == 2
    assert row["requirement_count"] == 1
    assert row["activity_count"] == 3
    assert row["attachment_count"] == 0


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


def test_project_query_supports_agent_filter():
    q = project_controller._project_q({"agent_id": 11})

    assert any(child.filters == {"agent_id": 11} for child in q.children)


@pytest.mark.anyio
async def test_project_summary_aggregates_product_points(monkeypatch):
    async def fake_redis(command, *args, **kwargs):
        return None

    class ProjectQuery:
        async def count(self):
            return 2

        async def all(self):
            return [
                SimpleNamespace(product_points=[{"product_name": "EDG", "points": 2}]),
                SimpleNamespace(product_points=[{"product_name": "EDG", "points": 3}, {"product_name": "ASG", "points": 1}]),
            ]

    class FakeProject:
        @staticmethod
        def filter(*args, **kwargs):
            return ProjectQuery()

    monkeypatch.setattr(project_module, "execute_redis", fake_redis)
    monkeypatch.setattr(project_module, "Project", FakeProject)

    summary = await project_controller.project_summary({})

    assert summary["product_points"] == [
        {"product_name": "ASG", "points": 1},
        {"product_name": "EDG", "points": 5},
    ]


@pytest.mark.anyio
async def test_project_summary_uses_redis_cache(monkeypatch):
    async def fake_redis(command, *args, **kwargs):
        assert command == "get"
        return '{"total": 3, "product_points": [{"product_name": "EDG", "points": 7}]}'

    monkeypatch.setattr(project_module, "execute_redis", fake_redis)

    summary = await project_controller.project_summary({})

    assert summary["total"] == 3
    assert summary["product_points"] == [{"product_name": "EDG", "points": 7}]


def test_partner_register_company_name_must_be_full_company_name():
    payload = {
        "company_name": "安得",
        "contact_name": "张三",
        "email": "test@example.com",
        "phone": "13800000000",
        "password": "Password123",
        "email_code": "123456",
    }

    with pytest.raises(ValidationError):
        PartnerRegisterIn(**payload)

    payload["company_name"] = "安得科技有限公司"
    assert PartnerRegisterIn(**payload).company_name == "安得科技有限公司"


def test_dept_accepts_channel_level():
    payload = DeptCreate(name="安得科技有限公司", channel_level=PartnerLevel.GOLD)

    assert payload.channel_level == PartnerLevel.GOLD


@pytest.mark.anyio
async def test_delete_projects_removes_activities_and_unbinds_attachments(monkeypatch):
    calls = []

    async def fake_clear_summary_cache():
        return None

    class DeleteQuery:
        def __init__(self, label):
            self.label = label

        async def delete(self):
            calls.append((self.label, "delete"))
            return 2 if self.label == "project" else 0

        async def update(self, **kwargs):
            calls.append((self.label, "update", kwargs))
            return 0

    class FakeProject:
        @staticmethod
        def filter(**kwargs):
            calls.append(("project", kwargs))
            return DeleteQuery("project")

    class FakeProjectActivity:
        @staticmethod
        def filter(**kwargs):
            calls.append(("activity", kwargs))
            return DeleteQuery("activity")

    class FakeProjectAttachment:
        @staticmethod
        def filter(**kwargs):
            calls.append(("attachment", kwargs))
            return DeleteQuery("attachment")

    monkeypatch.setattr(project_module, "Project", FakeProject)
    monkeypatch.setattr(project_module, "ProjectActivity", FakeProjectActivity)
    monkeypatch.setattr(project_module, "ProjectAttachment", FakeProjectAttachment)
    monkeypatch.setattr(project_controller, "clear_summary_cache", fake_clear_summary_cache)

    assert await project_controller.delete_projects.__wrapped__(project_controller, [1, 2]) == 2
    assert calls == [
        ("activity", {"project_id__in": [1, 2]}),
        ("activity", "delete"),
        ("attachment", {"project_id__in": [1, 2]}),
        ("attachment", "update", {"project_id": None}),
        ("project", {"id__in": [1, 2]}),
        ("project", "delete"),
    ]


@pytest.mark.anyio
async def test_delete_activity_removes_activity(monkeypatch):
    calls = []

    class DeleteQuery:
        async def delete(self):
            calls.append("delete")
            return 1

    class FakeProjectActivity:
        @staticmethod
        def filter(**kwargs):
            calls.append(kwargs)
            return DeleteQuery()

    monkeypatch.setattr(project_module, "ProjectActivity", FakeProjectActivity)

    assert await project_controller.delete_activity(9) == 1
    assert calls == [{"id": 9}, "delete"]


def test_import_points_ignore_server_count_and_map_products():
    rows = project_controller._parse_import_product_points("1-0-0-5", ["EDG", "ASG", "TSafe"])

    assert rows == [{"product_name": "TSafe", "points": 5}]


def test_import_points_support_multiplier_cells():
    rows = project_controller._parse_import_product_points("0-5-0-5*6", ["EDG", "ASG", "TSafe"])

    assert rows == [{"product_name": "EDG", "points": 5}, {"product_name": "TSafe", "points": 30}]


def test_import_points_support_omitted_trailing_zero_and_sum_cells():
    rows = project_controller._parse_import_product_points("1-100+62-0", ["EDG", "ASG", "TSafe"])

    assert rows == [{"product_name": "EDG", "points": 162}]


def test_import_points_support_server_only_cells():
    rows = project_controller._parse_import_product_points("/", ["EDG", "ASG", "TSafe"])

    assert rows == [{"product_name": "EDG", "points": 0}]


def test_import_points_support_single_count_products():
    rows = project_controller._parse_import_product_points(1, ["EDG", "DAS"], "DAS")

    assert rows == [{"product_name": "DAS", "points": 1}]


def test_import_points_skip_count_for_service_products():
    rows = project_controller._parse_import_product_points(99, ["EDG", "服务"], "服务")

    assert rows == [{"product_name": "服务", "points": 1}]


def test_import_points_merge_existing_project_points():
    rows = project_controller._merge_product_points(
        [{"product_name": "EDG", "points": 100}, {"product_name": "TSafe", "points": 5}],
        [{"product_name": "EDG", "points": 62}, {"product_name": "ASG", "points": 1}],
    )

    assert rows == [
        {"product_name": "EDG", "points": 162},
        {"product_name": "TSafe", "points": 5},
        {"product_name": "ASG", "points": 1},
    ]


def test_import_points_support_tdlp_segment():
    rows = project_controller._parse_import_product_points("1-0-0-0-200", ["EDG", "ASG", "TSafe", "TDLP"])

    assert rows == [{"product_name": "TDLP", "points": 200}]


@pytest.mark.anyio
async def test_sync_project_attachments_unbinds_removed_ids(monkeypatch):
    calls = []

    class AttachmentQuery:
        def __init__(self, label):
            self.label = label

        def exclude(self, **kwargs):
            calls.append(("exclude", self.label, kwargs))
            return self

        async def update(self, **kwargs):
            calls.append(("update", self.label, kwargs))

    class FakeAttachment:
        @staticmethod
        def filter(**kwargs):
            calls.append(("filter", kwargs))
            return AttachmentQuery(kwargs)

    monkeypatch.setattr(project_module, "ProjectAttachment", FakeAttachment)

    await project_controller._sync_attachments(project_id=9, attachment_ids=[1, 2], owner_ids=[7])

    assert ("exclude", {"project_id": 9}, {"id__in": [1, 2]}) in calls
    assert ("update", {"project_id": 9}, {"project_id": None}) in calls
    assert ("filter", {"id__in": [1, 2], "project_id": None, "uploader_id__in": [7]}) in calls


@pytest.mark.anyio
async def test_batch_update_projects_only_updates_batch_fields(monkeypatch):
    calls = {}

    async def fake_clear_summary_cache():
        return None

    async def fake_config():
        return {
            "project_products": ["EDG"],
            "project_statuses": ["售前", "实施中"],
            "project_regions": ["华东"],
            "project_activity_types": [],
            "project_server_versions": [],
            "project_client_versions": [],
        }

    class ProjectQuery:
        async def update(self, **kwargs):
            calls["update"] = kwargs
            return 2

    class FakeProject:
        @staticmethod
        def filter(**kwargs):
            calls["filter"] = kwargs
            return ProjectQuery()

    async def fake_validate_assignee(assignee_id):
        calls["assignee_id"] = assignee_id

    monkeypatch.setattr(project_module.system_setting_controller, "get_full_dict", fake_config)
    monkeypatch.setattr(project_module, "Project", FakeProject)
    monkeypatch.setattr(project_controller, "_validate_assignee", fake_validate_assignee)
    monkeypatch.setattr(project_controller, "clear_summary_cache", fake_clear_summary_cache)

    count = await project_controller.batch_update_projects(
        project_ids=[1, 2],
        user_id=7,
        payload={"region": "华东", "status": "实施中", "assignee_id": 9, "project_name": "ignored"},
    )

    assert count == 2
    assert calls["filter"] == {"id__in": [1, 2]}
    assert calls["assignee_id"] == 9
    assert calls["update"]["region"] == "华东"
    assert calls["update"]["status"] == "实施中"
    assert calls["update"]["assignee_id"] == 9
    assert "project_name" not in calls["update"]


@pytest.mark.anyio
async def test_import_projects_creates_agent_under_channel_dept(monkeypatch):
    calls = []

    async def fake_clear_summary_cache():
        return None

    class FakeSheet:
        def iter_rows(self, values_only=True):
            return iter([
                ("所属代理商", "项目名称", "产品名称", "终端点数"),
                ("代理商A", "项目A", "TSafe", "1-0-0-5"),
            ])

    class FakeWorkbook:
        active = FakeSheet()

    class FakeProjectQuery:
        async def first(self):
            return None

    class FakeProject:
        @staticmethod
        def filter(**kwargs):
            return FakeProjectQuery()

        @staticmethod
        async def create(**kwargs):
            calls.append(("project_create", kwargs))
            return SimpleNamespace(id=1)

    class FakeFile:
        filename = "import.xlsx"

        async def read(self):
            return b"xlsx"

    async def fake_config():
        return {"products": ["EDG", "ASG", "TSafe"], "statuses": ["售前"], "regions": []}

    async def fake_get_or_create(**kwargs):
        calls.append(("dept", kwargs))
        return SimpleNamespace(id=10 if kwargs["parent_id"] == 0 else 11, parent_id=kwargs["parent_id"])

    async def fake_validate_payload(payload):
        return {"project_name": payload["project_name"], "agent_id": payload["agent_id"], "product_points": payload["product_points"], "status": "售前"}

    monkeypatch.setattr(project_module, "load_workbook", lambda *args, **kwargs: FakeWorkbook())
    monkeypatch.setattr(project_module, "Project", FakeProject)
    monkeypatch.setattr(project_module.dept_controller, "get_or_create", fake_get_or_create)
    monkeypatch.setattr(project_controller, "_config", fake_config)
    monkeypatch.setattr(project_controller, "_validate_payload", fake_validate_payload)
    monkeypatch.setattr(project_controller, "clear_summary_cache", fake_clear_summary_cache)

    result = await project_controller.import_projects(user_id=7, file=FakeFile())

    assert result["created"] == 1
    assert calls[0] == ("dept", {"name": "渠道部门", "parent_id": 0, "desc": "项目导入自动创建"})
    assert calls[1] == ("dept", {"name": "代理商A", "parent_id": 10, "desc": "项目导入自动创建"})


@pytest.mark.anyio
async def test_import_projects_accumulates_points_and_updates_region_status(monkeypatch):
    calls = []

    async def fake_clear_summary_cache():
        return None

    class FakeSheet:
        def iter_rows(self, values_only=True):
            return iter([
                ("所属代理商", "项目名称", "产品名称", "终端点数", "区域", "状态"),
                ("代理商A", "北纬三七（苏州）科技有限公司", "EDG", "1-62-0-0", "华东", "实施中"),
                ("代理商A", "北纬三七（苏州）科技有限公司", "EDG", "1-38-0-0", "华东", "实施中"),
            ])

    class FakeWorkbook:
        active = FakeSheet()

    class ExistingProject:
        product_points = [{"product_name": "EDG", "points": 5}]
        region = None
        status = "售前"

        async def save(self):
            calls.append(("project_save", self.product_points, self.region, self.status))

    existing_project = ExistingProject()

    class FakeProjectQuery:
        async def first(self):
            return existing_project

    class FakeProject:
        @staticmethod
        def filter(**kwargs):
            calls.append(("project_filter", kwargs))
            return FakeProjectQuery()

    class FakeFile:
        filename = "import.xlsx"

        async def read(self):
            return b"xlsx"

    async def fake_config():
        return {"products": ["EDG", "ASG", "TSafe"], "statuses": ["售前", "实施中"], "regions": ["华东"]}

    async def fake_get_or_create(**kwargs):
        return SimpleNamespace(id=10 if kwargs["parent_id"] == 0 else 11, parent_id=kwargs["parent_id"])

    async def fake_validate_payload(payload):
        return {
            "project_name": payload["project_name"],
            "agent_id": payload["agent_id"],
            "product_points": payload["product_points"],
            "region": payload.get("region"),
            "status": payload.get("status") or "售前",
        }

    monkeypatch.setattr(project_module, "load_workbook", lambda *args, **kwargs: FakeWorkbook())
    monkeypatch.setattr(project_module, "Project", FakeProject)
    monkeypatch.setattr(project_module.dept_controller, "get_or_create", fake_get_or_create)
    monkeypatch.setattr(project_controller, "_config", fake_config)
    monkeypatch.setattr(project_controller, "_validate_payload", fake_validate_payload)
    monkeypatch.setattr(project_controller, "clear_summary_cache", fake_clear_summary_cache)

    result = await project_controller.import_projects(user_id=7, file=FakeFile())

    assert result["updated"] == 2
    assert ("project_save", [{"product_name": "EDG", "points": 100}], "华东", "实施中") in calls


@pytest.mark.anyio
async def test_validate_agent_requires_channel_child(monkeypatch):
    class DeptQuery:
        def __init__(self, result):
            self.result = result

        async def first(self):
            return self.result

        async def exists(self):
            return bool(self.result)

    class FakeDept:
        @staticmethod
        def filter(**kwargs):
            if kwargs.get("name") == project_module.IMPORT_AGENT_PARENT_DEPT_NAME:
                return DeptQuery(SimpleNamespace(id=10))
            if kwargs.get("id") == 11 and kwargs.get("parent_id") == 10:
                return DeptQuery(SimpleNamespace(id=11))
            return DeptQuery(None)

    monkeypatch.setattr(project_module, "Dept", FakeDept)

    await project_controller._validate_agent(11)

    with pytest.raises(HTTPException):
        await project_controller._validate_agent(12)


@pytest.mark.anyio
async def test_import_projects_moves_existing_agent_under_channel_dept(monkeypatch):
    calls = []

    async def fake_clear_summary_cache():
        return None

    class FakeSheet:
        def iter_rows(self, values_only=True):
            return iter([
                ("所属代理商", "项目名称", "产品名称", "终端点数"),
                ("代理商A", "项目A", "TSafe", "1-0-0-5"),
            ])

    class FakeWorkbook:
        active = FakeSheet()

    class FakeProjectQuery:
        async def first(self):
            return None

    class FakeProject:
        @staticmethod
        def filter(**kwargs):
            return FakeProjectQuery()

        @staticmethod
        async def create(**kwargs):
            calls.append(("project_create", kwargs))
            return SimpleNamespace(id=1)

    class FakeFile:
        filename = "import.xlsx"

        async def read(self):
            return b"xlsx"

    class FakeAgent:
        id = 11
        parent_id = 99

        async def save(self):
            calls.append(("agent_save", self.parent_id))

    async def fake_config():
        return {"products": ["EDG", "ASG", "TSafe"], "statuses": ["售前"], "regions": []}

    async def fake_get_or_create(**kwargs):
        calls.append(("dept", kwargs))
        return SimpleNamespace(id=10, parent_id=0) if kwargs["parent_id"] == 0 else FakeAgent()

    async def fake_validate_payload(payload):
        return {"project_name": payload["project_name"], "agent_id": payload["agent_id"], "product_points": payload["product_points"], "status": "售前"}

    async def fake_clear_cache():
        calls.append(("clear_cache", None))

    monkeypatch.setattr(project_module, "load_workbook", lambda *args, **kwargs: FakeWorkbook())
    monkeypatch.setattr(project_module, "Project", FakeProject)
    monkeypatch.setattr(project_module.dept_controller, "get_or_create", fake_get_or_create)
    monkeypatch.setattr(project_module.dept_controller, "clear_dept_dict_cache", fake_clear_cache)
    monkeypatch.setattr(project_controller, "_config", fake_config)
    monkeypatch.setattr(project_controller, "_validate_payload", fake_validate_payload)
    monkeypatch.setattr(project_controller, "clear_summary_cache", fake_clear_summary_cache)

    result = await project_controller.import_projects(user_id=7, file=FakeFile())

    assert result["created"] == 1
    assert ("agent_save", 10) in calls
    assert ("clear_cache", None) in calls


@pytest.mark.anyio
async def test_import_projects_leaves_missing_assignee_blank(monkeypatch):
    calls = []

    async def fake_clear_summary_cache():
        return None

    class FakeSheet:
        def iter_rows(self, values_only=True):
            return iter([
                ("所属代理商", "项目名称", "终端点数", "负责人"),
                ("代理商A", "项目A", "1-0-0-5", "不存在的负责人"),
            ])

    class FakeWorkbook:
        active = FakeSheet()

    class FakeProjectQuery:
        async def first(self):
            return None

    class FakeProject:
        @staticmethod
        def filter(**kwargs):
            return FakeProjectQuery()

        @staticmethod
        async def create(**kwargs):
            calls.append(("project_create", kwargs))
            return SimpleNamespace(id=1)

    class FakeFile:
        filename = "import.xlsx"

        async def read(self):
            return b"xlsx"

    async def fake_config():
        return {"products": ["EDG", "ASG", "TSafe"], "statuses": ["售前"], "regions": []}

    async def fake_get_or_create(**kwargs):
        return SimpleNamespace(id=10 if kwargs["parent_id"] == 0 else 11, parent_id=kwargs["parent_id"])

    async def fake_validate_payload(payload):
        return {"project_name": payload["project_name"], "agent_id": payload["agent_id"], "product_points": payload["product_points"], "assignee_id": payload["assignee_id"], "status": "售前"}

    async def fake_resolve_assignee(value):
        calls.append(("resolve_assignee", value))
        return None

    monkeypatch.setattr(project_module, "load_workbook", lambda *args, **kwargs: FakeWorkbook())
    monkeypatch.setattr(project_module, "Project", FakeProject)
    monkeypatch.setattr(project_module.dept_controller, "get_or_create", fake_get_or_create)
    monkeypatch.setattr(project_controller, "_config", fake_config)
    monkeypatch.setattr(project_controller, "_validate_payload", fake_validate_payload)
    monkeypatch.setattr(project_controller, "_resolve_import_assignee", fake_resolve_assignee)
    monkeypatch.setattr(project_controller, "clear_summary_cache", fake_clear_summary_cache)

    result = await project_controller.import_projects(user_id=7, file=FakeFile())

    assert result["created"] == 1
    assert ("resolve_assignee", "不存在的负责人") in calls
    project_create = next(item for item in calls if item[0] == "project_create")[1]
    assert project_create["assignee_id"] is None
    assert project_create["assigned_by"] is None
    assert project_create["assigned_at"] is None


@pytest.mark.anyio
async def test_import_assignee_matches_alias_only(monkeypatch):
    calls = []

    class UserQuery:
        def __init__(self, user):
            self.user = user

        def prefetch_related(self, *args):
            return self

        async def first(self):
            return self.user

    class FakeUser:
        @staticmethod
        def filter(**kwargs):
            calls.append(kwargs)
            user = SimpleNamespace(id=9) if kwargs == {"alias": "张三", "is_active": True} else None
            if user:
                async def roles():
                    return [SimpleNamespace(name="技术")]
                user.roles = roles()
            return UserQuery(user)

    monkeypatch.setattr(project_module, "User", FakeUser)

    assert await project_controller._resolve_import_assignee("zhangsan") is None
    assert await project_controller._resolve_import_assignee("张三") == 9
    assert calls == [
        {"alias": "zhangsan", "is_active": True},
        {"alias": "张三", "is_active": True},
    ]
