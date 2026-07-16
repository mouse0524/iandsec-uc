import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest


def _response_body(response):
    return json.loads(response.body.decode("utf-8"))


def test_issue_router_is_mounted():
    from app.api.v1 import v1_router

    paths = {route.path for route in v1_router.routes}

    assert "/issue/create" in paths
    assert "/issue/dashboard" in paths
    assert "/issue/list" in paths
    assert "/issue/get" in paths
    assert "/issue/metadata" in paths
    assert "/issue/status-options" in paths
    assert "/issue/assignees" in paths
    assert "/issue/update" in paths
    assert "/issue/watchers" in paths
    assert "/issue/watcher/add" in paths
    assert "/issue/watcher/delete" in paths
    assert "/issue/relations" in paths
    assert "/issue/relation/create" in paths
    assert "/issue/relation/delete" in paths
    assert "/issue/time-entries" in paths
    assert "/issue/time-entry/create" in paths
    assert "/issue/time-entry/delete" in paths
    assert "/issue/queries" in paths
    assert "/issue/query/create" in paths
    assert "/issue/query/update" in paths
    assert "/issue/query/delete" in paths
    assert "/issue/admin/config" in paths
    assert "/issue/admin/tracker/save" in paths
    assert "/issue/admin/status/save" in paths
    assert "/issue/admin/priority/save" in paths
    assert "/issue/admin/workflow/save" in paths
    assert "/issue/admin/custom-field/save" in paths


def test_rd_task_router_is_not_mounted():
    from app.api.v1 import v1_router

    paths = {route.path for route in v1_router.routes}

    assert not any(path.startswith("/rd-task/") for path in paths)


def test_issue_admin_api_paths_are_registered_for_init_permissions():
    from app.core.init_app import (
        _issue_admin_api_paths,
        _issue_create_api_paths,
        _issue_read_api_paths,
        _test_role_extra_api_paths,
        _issue_update_api_paths,
    )

    paths = set(_issue_admin_api_paths())

    assert "/api/v1/issue/dashboard" in _issue_read_api_paths()
    assert "/api/v1/issue/assignees" in _issue_read_api_paths()
    assert "/api/v1/issue/admin/config" in paths
    assert "/api/v1/issue/admin/tracker/save" in paths
    assert "/api/v1/issue/admin/status/save" in paths
    assert "/api/v1/issue/admin/priority/save" in paths
    assert "/api/v1/issue/admin/workflow/save" in paths
    assert "/api/v1/issue/admin/custom-field/save" in paths
    assert _test_role_extra_api_paths() == ["/api/v1/user/list", "/api/v1/ticket/prefill"]
    assert _issue_create_api_paths() == ["/api/v1/issue/create"]
    assert "/api/v1/issue/create" not in _issue_update_api_paths()


def test_issue_dashboard_data_counts_status_and_top_projects():
    from app.api.v1.issues import issues as issue_api

    now = datetime.now()
    data = issue_api._issue_dashboard_data(
        [
            {
                "id": 1,
                "title": "问题A",
                "issue_status_id": 1,
                "company_name": "A项目",
                "created_at": now,
                "updated_at": now - timedelta(days=8),
                "closed_at": None,
            },
            {
                "id": 2,
                "title": "问题B",
                "issue_status_id": 1,
                "company_name": "A项目",
                "created_at": now - timedelta(days=1),
                "updated_at": now,
                "closed_at": None,
            },
            {
                "id": 3,
                "title": "问题C",
                "issue_status_id": 2,
                "company_name": "B项目",
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(days=9),
                "closed_at": now,
            },
            {
                "id": 4,
                "title": "问题D",
                "issue_status_id": None,
                "company_name": "",
                "created_at": now - timedelta(days=15),
                "updated_at": now - timedelta(days=10),
                "closed_at": None,
            },
            {
                "id": 5,
                "title": "问题E",
                "issue_status_id": 1,
                "company_name": "C项目",
                "created_at": now,
                "updated_at": "invalid",
                "closed_at": None,
            },
        ],
        [{"id": 1, "name": "新建", "is_closed": False}, {"id": 2, "name": "关闭", "is_closed": True}],
    )

    assert data["total"] == 5
    assert data["status_counts"] == [
        {"status_id": 1, "name": "新建", "is_closed": False, "count": 3},
        {"status_id": 2, "name": "关闭", "is_closed": True, "count": 1},
        {"status_id": None, "name": "未设置", "is_closed": False, "count": 1},
    ]
    assert data["top_projects"][:2] == [
        {"project_name": "A项目", "count": 2},
        {"project_name": "B项目", "count": 1},
    ]
    assert data["created_trend"]["daily"][-1]["count"] == 2
    assert data["closed_trend"]["daily"][-1]["count"] == 1
    assert data["created_trend"]["weekly"][-1]["count"] >= 1
    assert len(data["created_trend"]["daily"]) == 7
    assert len(data["created_trend"]["weekly"]) == 7
    assert len(data["closed_trend"]["daily"]) == 7
    assert len(data["closed_trend"]["weekly"]) == 7
    assert [item["id"] for item in data["stale_issues"]] == [4, 1]
    assert data["stale_issues"][0]["project_name"] == "未填写项目"
    assert data["stale_issues"][0]["days"] >= data["stale_issues"][1]["days"] >= 7


def test_issue_submitter_roles_can_update_for_workflow_verification():
    from app.api.v1.issues import issues as issue_api

    assert issue_api.ISSUE_CREATE_ROLES is issue_api.ISSUE_UPDATE_ROLES
    assert {"用户", "渠道商", "代理商"} <= issue_api.ISSUE_UPDATE_ROLES


def test_issue_assignee_scope_follows_role_rules():
    from app.api.v1.issues import issues as issue_api

    user = SimpleNamespace(id=8, is_superuser=False, username="channel01")
    tech = SimpleNamespace(id=7, is_superuser=False, username="tech01")
    admin = SimpleNamespace(id=1, is_superuser=True, username="admin")
    ticket = SimpleNamespace(assigned_to_id=5)

    assert _q_filters(issue_api._issue_assignee_q(admin, [], ticket)) == []
    assert {"roles__id__in": [1, 2]} in _q_filters(
        issue_api._issue_assignee_q(admin, [], ticket, {2, 1})
    )
    assert {"id__in": [5, 8]} in _q_filters(issue_api._issue_assignee_q(user, ["渠道商"], ticket))
    assert _q_filters(issue_api._issue_assignee_q(tech, ["技术"], ticket)) == []


@pytest.mark.anyio
async def test_issue_assignee_role_ids_come_from_workflow(monkeypatch):
    from app.api.v1.issues import issues as issue_api

    calls = []

    class WorkflowQuery:
        async def values(self, *fields):
            calls.append(fields)
            return [{"role_id": 6}, {"role_id": 2}, {"role_id": 2}]

    def fake_filter(**kwargs):
        calls.append(kwargs)
        return WorkflowQuery()

    monkeypatch.setattr(issue_api.IssueWorkflowTransition, "filter", fake_filter)

    assert await issue_api._target_assignee_role_ids(status_id=20, tracker_id=3) == {2, 6}
    assert calls == [
        {"old_status_id": 20, "tracker_id": 3},
        ("role_id",),
    ]


@pytest.mark.anyio
async def test_issue_assignees_for_initial_status_only_return_submitter(monkeypatch):
    from app.api.v1.issues import issues as issue_api

    ticket = SimpleNamespace(id=9, submitter_id=3, assigned_to_id=7)
    user = SimpleNamespace(id=7, username="rd", is_superuser=False)

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return ["研发"]

    async def fake_get_issue(issue_id):
        return ticket

    async def fake_can_access(current_ticket, current_user, role_names):
        return True

    class StatusQuery:
        async def first(self):
            return SimpleNamespace(name="新建", is_default=True)

    class UserQuery:
        async def values(self, *fields):
            return [{"id": 3, "username": "submitter", "alias": "提交人", "email": "s@example.com"}]

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api, "_get_issue_or_none", fake_get_issue)
    monkeypatch.setattr(issue_api, "_can_access_ticket", fake_can_access)
    monkeypatch.setattr(issue_api.IssueStatus, "filter", lambda **kwargs: StatusQuery())
    monkeypatch.setattr(issue_api.User, "filter", lambda **kwargs: UserQuery())

    body = _response_body(await issue_api.get_issue_assignees(issue_id=9, status_id=1))

    assert body["data"] == [{"id": 3, "username": "submitter", "alias": "提交人", "email": "s@example.com"}]


@pytest.mark.anyio
async def test_issue_assignees_for_field_verification_return_submitter_and_tech(monkeypatch):
    from app.api.v1.issues import issues as issue_api

    ticket = SimpleNamespace(id=9, submitter_id=3, assigned_to_id=7)
    user = SimpleNamespace(id=7, username="rd", is_superuser=False)
    user_filter_calls = []

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return ["研发"]

    async def fake_get_issue(issue_id):
        return ticket

    async def fake_can_access(current_ticket, current_user, role_names):
        return True

    class StatusQuery:
        async def first(self):
            return SimpleNamespace(name="现场验证", is_default=False)

    class RoleQuery:
        async def first(self):
            return SimpleNamespace(id=4, name="技术")

    class UserQuery:
        def distinct(self):
            return self

        def order_by(self, *fields):
            return self

        async def values(self, *fields):
            return [
                {"id": 3, "username": "submitter", "alias": "提交人", "email": "s@example.com"},
                {"id": 4, "username": "tech", "alias": "技术", "email": "t@example.com"},
            ]

    def fake_user_filter(*args, **kwargs):
        user_filter_calls.append((args, kwargs))
        return UserQuery()

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api, "_get_issue_or_none", fake_get_issue)
    monkeypatch.setattr(issue_api, "_can_access_ticket", fake_can_access)
    monkeypatch.setattr(issue_api.IssueStatus, "filter", lambda **kwargs: StatusQuery())
    monkeypatch.setattr(issue_api.Role, "filter", lambda **kwargs: RoleQuery())
    monkeypatch.setattr(issue_api.User, "filter", fake_user_filter)

    body = _response_body(await issue_api.get_issue_assignees(issue_id=9, status_id=6, tracker_id=1))

    assert [item["id"] for item in body["data"]] == [3, 4]
    filters = _q_filters(user_filter_calls[0][0][0])
    assert {"id__in": [3]} in filters
    assert {"roles__id": 4} in filters


def test_issue_attachment_file_exists_rejects_missing_and_escaped_paths(monkeypatch, tmp_path):
    from app.api.v1.issues import issues as issue_api

    existing = tmp_path / "tickets" / "shot.png"
    existing.parent.mkdir()
    existing.write_bytes(b"ok")
    monkeypatch.setattr(issue_api.settings, "UPLOAD_DIR", str(tmp_path))

    assert issue_api._ticket_attachment_file_exists(SimpleNamespace(file_path="tickets/shot.png"))
    assert not issue_api._ticket_attachment_file_exists(SimpleNamespace(file_path="tickets/missing.png"))
    assert not issue_api._ticket_attachment_file_exists(SimpleNamespace(file_path="../outside.png"))


def _q_filters(q):
    filters = []
    if getattr(q, "filters", None):
        filters.append(q.filters)
    for child in getattr(q, "children", ()) or ():
        filters.extend(_q_filters(child))
    return filters


@pytest.mark.anyio
async def test_issue_name_filter_q_maps_names_to_search_conditions(monkeypatch):
    from app.api.v1.issues import issues as issue_api

    async def fake_ids(model, text, fields):
        if model is issue_api.Project:
            return [11]
        if model is issue_api.IssueStatus:
            return [22]
        if model is issue_api.User:
            return [33]
        return []

    monkeypatch.setattr(issue_api, "_ids_by_contains", fake_ids)

    q = await issue_api._issue_name_filter_q(
        {
            "issue_project_name": "安得",
            "issue_status_name": "新建",
            "assigned_to_name": "管理员",
            "submitter_name": "管理员",
        }
    )

    filters = _q_filters(q)
    assert {"company_name__contains": "安得"} in filters
    assert {"issue_project_id__in": [11]} in filters
    assert {"issue_status_id__in": [22]} in filters
    assert {"assigned_to_id__in": [33]} in filters
    assert {"submitter_id__in": [33]} in filters
    assert {"submitter_id": 33} in _q_filters(issue_api._apply_query_filters(issue_api.Q(), {"submitter_id": 33}))


@pytest.mark.anyio
async def test_issue_name_filter_q_ignores_empty_name_matches(monkeypatch):
    from app.api.v1.issues import issues as issue_api

    async def fake_ids(model, text, fields):
        return []

    monkeypatch.setattr(issue_api, "_ids_by_contains", fake_ids)

    q = await issue_api._issue_name_filter_q(
        {
            "issue_status_name": "不存在",
            "assigned_to_name": "不存在",
            "submitter_name": "不存在",
        }
    )

    assert {"id": 0} not in _q_filters(q)


@pytest.mark.anyio
async def test_issue_visibility_scope_follows_role_rules(monkeypatch):
    from app.api.v1.issues import issues as issue_api

    tech_user = SimpleNamespace(id=7, is_superuser=False, username="tech01")
    normal_user = SimpleNamespace(id=8, is_superuser=False, username="user01")
    all_user = SimpleNamespace(id=9, is_superuser=False, username="pm01")

    async def fake_related_submitters(tech_id):
        assert tech_id == 7
        return [11, 12]

    monkeypatch.setattr(issue_api, "_tech_related_submitter_ids", fake_related_submitters)

    assert _q_filters(await issue_api._issue_visibility_q(all_user, ["客服"], None)) == []
    assert _q_filters(await issue_api._issue_visibility_q(all_user, ["产品"], None)) == []
    assert _q_filters(await issue_api._issue_visibility_q(all_user, ["测试"], None)) == []
    assert _q_filters(await issue_api._issue_visibility_q(all_user, ["研发"], None)) == []
    assert _q_filters(await issue_api._issue_visibility_q(tech_user, ["技术"], None)) == []

    channel_filters = _q_filters(await issue_api._issue_visibility_q(normal_user, ["渠道商"], None))
    user_filters = _q_filters(await issue_api._issue_visibility_q(normal_user, ["用户"], None))
    assert {"submitter_id": 8} in channel_filters
    assert {"assigned_to_id": 8} in channel_filters
    assert {"submitter_id": 8} in user_filters
    assert {"assigned_to_id": 8} in user_filters

    assert await issue_api._can_access_ticket(SimpleNamespace(submitter_id=11), tech_user, ["技术"])
    assert await issue_api._can_access_ticket(SimpleNamespace(submitter_id=99, assigned_to_id=7), tech_user, ["技术"])
    assert await issue_api._can_access_ticket(SimpleNamespace(submitter_id=99, assigned_to_id=8), normal_user, ["用户"])
    assert await issue_api._can_access_ticket(SimpleNamespace(submitter_id=99), tech_user, ["技术"])
    assert await issue_api._can_access_ticket(SimpleNamespace(submitter_id=99), all_user, ["客服"])
    assert await issue_api._can_access_ticket(SimpleNamespace(submitter_id=99), all_user, ["研发"])
    assert not await issue_api._can_access_ticket(SimpleNamespace(submitter_id=99), normal_user, ["用户"])


def test_issue_assignee_filter_accepts_multiple_ids():
    from app.api.v1.issues import issues as issue_api

    filters = _q_filters(issue_api._apply_query_filters(issue_api.Q(), {"assigned_to_id": "7,8"}))

    assert {"assigned_to_id__in": [7, 8]} in filters


def test_issue_assignee_filter_permission_scope():
    from app.api.v1.issues import issues as issue_api

    user = SimpleNamespace(id=3, is_superuser=False, username="u")

    assert issue_api._allowed_assignee_filter(user, ["用户"], "7,8") == [3]
    assert issue_api._allowed_assignee_filter(user, ["渠道商"], [7, 8]) == [3]
    assert issue_api._allowed_assignee_filter(user, ["技术"], "7,8") == [7, 8]
    assert issue_api._allowed_assignee_filter(user, ["产品"], "7,8") == [7, 8]
    assert issue_api._allowed_assignee_filter(user, ["测试"], "7,8") == [7, 8]
    assert issue_api._allowed_assignee_filter(user, ["研发"], "7,8") == [7, 8]


def test_issue_list_fields_exclude_heavy_description():
    from app.api.v1.issues import issues as issue_api

    assert "description" not in issue_api.ISSUE_LIST_FIELDS


@pytest.mark.anyio
async def test_get_issue_returns_404_when_issue_is_missing(monkeypatch):
    from app.api.v1.issues import issues as issue_api

    user = SimpleNamespace(id=3, is_superuser=True, roles=[])

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return ["管理员"]

    class MissingTicketQuery:
        async def first(self):
            return None

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api.Ticket, "filter", lambda **kwargs: MissingTicketQuery())

    response = await issue_api.get_issue(issue_id=404)

    body = _response_body(response)
    assert body["code"] == 404


@pytest.mark.anyio
async def test_issue_admin_tracker_save_rejects_non_admin(monkeypatch):
    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueAdminTrackerSaveIn

    role = SimpleNamespace(id=5, name="研发")
    user = SimpleNamespace(id=3, is_superuser=False, roles=[role])

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return ["研发"]

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)

    response = await issue_api.save_issue_tracker(IssueAdminTrackerSaveIn(name="现网问题"))

    body = _response_body(response)
    assert body["code"] == 403


@pytest.mark.anyio
async def test_issue_admin_workflow_save_accepts_multiple_targets(monkeypatch):
    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueAdminWorkflowSaveIn

    calls = []
    user = SimpleNamespace(id=1, is_superuser=True, roles=[])

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return []

    class WorkflowQuery:
        def exclude(self, **kwargs):
            calls.append(("exclude", kwargs))
            return self

        async def delete(self):
            calls.append(("delete", None))
            return 1

    class WorkflowRow:
        def __init__(self, new_status_id):
            self.new_status_id = new_status_id
            self.assignee_required = False
            self.author_allowed = False
            self.assignee_allowed = True

        async def save(self):
            calls.append(("save", self.new_status_id))

        async def to_dict(self):
            return {"new_status_id": self.new_status_id}

    class WorkflowModel:
        @staticmethod
        def filter(**kwargs):
            calls.append(("filter", kwargs))
            return WorkflowQuery()

        @staticmethod
        async def get_or_create(**kwargs):
            calls.append(("get_or_create", kwargs))
            return WorkflowRow(kwargs["new_status_id"]), False

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api, "IssueWorkflowTransition", WorkflowModel)

    response = await issue_api.save_issue_workflow(
        IssueAdminWorkflowSaveIn(
            role_id=1,
            tracker_id=2,
            old_status_id=3,
            new_status_ids=[4, 5],
            assignee_required=True,
        )
    )

    body = _response_body(response)
    assert body["data"] == [{"new_status_id": 4}, {"new_status_id": 5}]
    assert ("filter", {"role_id": 1, "tracker_id": 2, "old_status_id": 3}) in calls
    assert ("exclude", {"new_status_id__in": [4, 5]}) in calls
    assert [call[1]["new_status_id"] for call in calls if call[0] == "get_or_create"] == [4, 5]


@pytest.mark.anyio
async def test_issue_admin_workflow_save_deletes_all_targets(monkeypatch):
    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueAdminWorkflowSaveIn

    calls = []
    user = SimpleNamespace(id=1, is_superuser=True, roles=[])

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return []

    class WorkflowQuery:
        def exclude(self, **kwargs):
            calls.append(("exclude", kwargs))
            return self

        async def delete(self):
            calls.append(("delete", None))
            return 2

    class WorkflowModel:
        @staticmethod
        def filter(**kwargs):
            calls.append(("filter", kwargs))
            return WorkflowQuery()

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api, "IssueWorkflowTransition", WorkflowModel)

    response = await issue_api.save_issue_workflow(
        IssueAdminWorkflowSaveIn(role_id=1, tracker_id=2, old_status_id=3, new_status_ids=[])
    )

    body = _response_body(response)
    assert body["data"] == []
    assert ("filter", {"role_id": 1, "tracker_id": 2, "old_status_id": 3}) in calls
    assert not [call for call in calls if call[0] == "exclude"]
    assert ("delete", None) in calls


@pytest.mark.anyio
async def test_create_issue_api_saves_custom_values(monkeypatch):
    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueCreateIn

    role = SimpleNamespace(id=9, name="用户")
    user = SimpleNamespace(
        id=3,
        is_superuser=False,
        roles=[role],
        company_name="客户A",
        alias="张三",
        username="zhangsan",
        email="a@example.com",
        phone="13800000000",
    )
    ticket = SimpleNamespace(id=7, to_dict=lambda: {"id": 7, "title": "自定义字段工单"})
    saved = []
    created = []

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return ["用户"]

    async def fake_create_ticket(**kwargs):
        created.append(kwargs)
        return ticket

    async def fake_apply_defaults(current_ticket):
        return current_ticket

    async def fake_save_custom_values(issue_id, values, *, validate_required=False):
        saved.append((issue_id, values, validate_required))
        return []

    async def fake_decorate(rows):
        rows[0]["custom_values"] = {"12": "高危"}
        return rows

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api.ticket_controller, "create_ticket", fake_create_ticket)
    monkeypatch.setattr(issue_api.issue_default_service, "apply_defaults", fake_apply_defaults)
    monkeypatch.setattr(issue_api, "_save_issue_custom_values", fake_save_custom_values)
    monkeypatch.setattr(issue_api, "_decorate_issue_rows", fake_decorate)

    response = await issue_api.create_issue(
        IssueCreateIn(
            title="自定义字段工单",
            company_name="客户A",
            issue_type="现网问题",
            issue_priority_id=1,
            description="desc",
            custom_values={"12": "高危"},
        )
    )

    body = _response_body(response)
    assert body["data"]["custom_values"] == {"12": "高危"}
    assert created[0]["notify_pending_review"] is False
    assert created[0]["payload"]["assigned_to_id"] == 3
    assert saved == [(7, {"12": "高危"}, True)]


def test_validate_create_issue_uses_chinese_required_labels():
    from fastapi import HTTPException

    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueCreateIn

    with pytest.raises(HTTPException) as exc_info:
        issue_api._validate_create_issue(
            IssueCreateIn(
                title="标题",
                company_name="",
                issue_type="现网问题",
                issue_priority_id=1,
                description="描述",
            )
        )

    assert exc_info.value.detail == "项目名称不能为空"


def test_validate_create_issue_rejects_empty_rich_text_description():
    from fastapi import HTTPException

    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueCreateIn

    with pytest.raises(HTTPException) as exc_info:
        issue_api._validate_create_issue(
            IssueCreateIn(
                title="标题",
                company_name="项目",
                issue_type="现网问题",
                issue_priority_id=1,
                description="<p><br></p>",
            )
        )

    assert exc_info.value.detail == "描述不能为空"


def test_create_issue_payload_drops_client_controlled_workflow_fields():
    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueCreateIn

    payload = IssueCreateIn(
        title="越权创建",
        company_name="客户A",
        issue_type="现网问题",
        issue_priority_id=1,
        issue_status_id=99,
        assigned_to_id=88,
        done_ratio=100,
        is_private=True,
        description="desc",
    )

    data = issue_api._create_issue_payload(payload, SimpleNamespace(id=3, alias="用户", email="", phone=""))

    assert data["assigned_to_id"] == 3
    assert "issue_status_id" not in data
    assert "done_ratio" not in data
    assert "is_private" not in data


@pytest.mark.anyio
async def test_get_issue_api_returns_ticket_attachments(monkeypatch):
    from app.api.v1.issues import issues as issue_api

    class AwaitableRows:
        def __init__(self, rows):
            self.rows = rows

        def order_by(self, *args):
            return self

        def __await__(self):
            async def _result():
                return self.rows

            return _result().__await__()

    user = SimpleNamespace(id=3, is_superuser=True, roles=[])
    ticket = SimpleNamespace(
        id=7,
        to_dict=lambda: {"id": 7, "title": "附件工单", "issue_status_id": 20},
    )
    attachment = SimpleNamespace(
        id=11,
        to_dict=lambda: {
            "id": 11,
            "ticket_id": 7,
            "origin_name": "error.log",
            "file_path": "tickets/error.log",
            "file_size": 42,
            "mime_type": "text/plain",
        },
    )

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return ["admin"]

    async def fake_access(current_ticket, current_user, role_names):
        return True

    async def fake_decorate(rows):
        return rows

    async def fake_get_issue(issue_id):
        return ticket

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api, "_can_access_ticket", fake_access)
    monkeypatch.setattr(issue_api, "_decorate_issue_rows", fake_decorate)
    monkeypatch.setattr(issue_api, "_ticket_attachment_file_exists", lambda item: True)
    monkeypatch.setattr(issue_api, "_get_issue_or_none", fake_get_issue)
    monkeypatch.setattr(issue_api.TicketAttachment, "filter", lambda **kwargs: AwaitableRows([attachment]))
    monkeypatch.setattr(issue_api.IssueJournal, "filter", lambda **kwargs: AwaitableRows([]))

    response = await issue_api.get_issue(issue_id=7)

    body = _response_body(response)
    assert body["data"]["attachment_count"] == 1
    assert body["data"]["attachments"] == [
        {
            "id": 11,
            "ticket_id": 7,
            "origin_name": "error.log",
            "file_path": "tickets/error.log",
            "file_size": 42,
            "mime_type": "text/plain",
            "file_exists": True,
        }
    ]


@pytest.mark.anyio
async def test_update_issue_api_records_notes_and_changes(monkeypatch):
    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueUpdateIn

    role = SimpleNamespace(id=5, name="研发")
    user = SimpleNamespace(id=3, is_superuser=False, roles=[role])
    ticket = SimpleNamespace(id=7)
    calls = []
    notifications = []

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return ["研发"]

    async def fake_access(current_ticket, current_user, role_names):
        return True

    async def fake_update_issue(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(to_dict=lambda: {"id": 7, "issue_status_id": 30})

    async def fake_get_issue(issue_id):
        return ticket

    async def fake_assignee_ids(current_user, role_names, current_ticket, status_id=None, tracker_id=None):
        return {3, 4}

    async def fake_notify(**kwargs):
        notifications.append(kwargs)

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api, "_can_access_ticket", fake_access)
    monkeypatch.setattr(issue_api, "_get_issue_or_none", fake_get_issue)
    monkeypatch.setattr(issue_api, "_issue_assignee_ids", fake_assignee_ids)
    monkeypatch.setattr(issue_api.issue_update_service, "update_issue", fake_update_issue)
    monkeypatch.setattr(issue_api.ticket_controller, "_notify_ticket_status_if_needed", fake_notify)
    monkeypatch.setattr(issue_api, "_decorate_issue_rows", lambda rows: rows)

    response = await issue_api.update_issue(
        IssueUpdateIn(
            issue_id=7,
            changes={"issue_status_id": 30, "assigned_to_id": 4},
            notes="推进处理",
        )
    )

    body = _response_body(response)
    assert body["data"] == {"id": 7, "issue_status_id": 30}
    assert calls == [
        {
            "issue_id": 7,
            "user_id": 3,
            "role_ids": [5],
            "changes": {"issue_status_id": 30, "assigned_to_id": 4},
            "notes": "推进处理",
            "private_notes": False,
            "bypass_workflow": False,
        }
    ]
    assert notifications[0]["operator_id"] == 3


@pytest.mark.anyio
async def test_update_issue_api_rejects_disallowed_assignee(monkeypatch):
    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueUpdateIn

    role = SimpleNamespace(id=9, name="渠道商")
    user = SimpleNamespace(id=3, is_superuser=False, roles=[role])
    ticket = SimpleNamespace(id=7, submitter_id=3, assigned_to_id=5)

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return ["渠道商"]

    async def fake_get_issue(issue_id):
        return ticket

    async def fake_assignee_ids(current_user, role_names, current_ticket, status_id=None, tracker_id=None):
        return {3, 5}

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api, "_get_issue_or_none", fake_get_issue)
    monkeypatch.setattr(issue_api, "_issue_assignee_ids", fake_assignee_ids)

    response = await issue_api.update_issue(IssueUpdateIn(issue_id=7, changes={"assigned_to_id": 99}))

    body = _response_body(response)
    assert body["code"] == 403
    assert body["msg"] == "您暂无权限指派给该用户"


@pytest.mark.anyio
async def test_update_issue_api_notifies_when_only_assignee_changes(monkeypatch):
    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueUpdateIn

    user = SimpleNamespace(id=3, is_superuser=True, roles=[])
    ticket = SimpleNamespace(id=7, issue_status_id=20, assigned_to_id=4)
    notifications = []

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return []

    async def fake_access(current_ticket, current_user, role_names):
        return True

    async def fake_get_issue(issue_id):
        return ticket

    async def fake_assignee_ids(*args, **kwargs):
        return {5}

    async def fake_update_issue(**kwargs):
        return SimpleNamespace(to_dict=lambda: {"id": 7, "assigned_to_id": 5})

    async def fake_notify(**kwargs):
        notifications.append(kwargs)

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api, "_can_access_ticket", fake_access)
    monkeypatch.setattr(issue_api, "_get_issue_or_none", fake_get_issue)
    monkeypatch.setattr(issue_api, "_issue_assignee_ids", fake_assignee_ids)
    monkeypatch.setattr(issue_api.issue_update_service, "update_issue", fake_update_issue)
    monkeypatch.setattr(issue_api.ticket_controller, "_notify_ticket_status_if_needed", fake_notify)
    monkeypatch.setattr(issue_api, "_decorate_issue_rows", lambda rows: rows)

    await issue_api.update_issue(IssueUpdateIn(issue_id=7, changes={"assigned_to_id": 5}))

    assert notifications[0]["operator_id"] == 3


@pytest.mark.anyio
async def test_update_issue_api_allows_submitter_role_when_issue_is_accessible(monkeypatch):
    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueUpdateIn

    role = SimpleNamespace(id=9, name="用户")
    user = SimpleNamespace(id=3, is_superuser=False, roles=[role])
    ticket = SimpleNamespace(id=7)
    calls = []
    notifications = []

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return ["用户"]

    async def fake_access(current_ticket, current_user, role_names):
        return True

    async def fake_update_issue(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(to_dict=lambda: {"id": 7})

    async def fake_get_issue(issue_id):
        return ticket

    async def fake_notify(**kwargs):
        notifications.append(kwargs)

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api, "_can_access_ticket", fake_access)
    monkeypatch.setattr(issue_api, "_get_issue_or_none", fake_get_issue)
    monkeypatch.setattr(issue_api.issue_update_service, "update_issue", fake_update_issue)
    monkeypatch.setattr(issue_api.ticket_controller, "_notify_ticket_status_if_needed", fake_notify)
    monkeypatch.setattr(issue_api, "_decorate_issue_rows", lambda rows: rows)

    response = await issue_api.update_issue(
        IssueUpdateIn(issue_id=7, changes={"issue_status_id": 30}, notes="尝试推进")
    )

    body = _response_body(response)
    assert body["data"] == {"id": 7}
    assert calls == [
        {
            "issue_id": 7,
            "user_id": 3,
            "role_ids": [9],
            "changes": {"issue_status_id": 30},
            "notes": "尝试推进",
            "private_notes": False,
            "bypass_workflow": False,
        }
    ]
    assert notifications[0]["operator_id"] == 3


@pytest.mark.anyio
async def test_create_issue_api_reuses_ticket_creation_and_current_user_defaults(monkeypatch):
    from app.api.v1.issues import issues as issue_api
    from app.schemas.issues import IssueCreateIn

    role = SimpleNamespace(id=5, name="用户")
    user = SimpleNamespace(
        id=3,
        is_superuser=False,
        roles=[role],
        alias="用户同学",
        username="user01",
        company_name="安得内部",
        email="user@example.com",
        phone="13800000000",
    )
    calls = []
    ticket = SimpleNamespace(
        id=9,
        to_dict=lambda: {"id": 9, "title": "内部Issue", "issue_status_id": 20},
    )

    async def fake_current_user():
        return user

    async def fake_role_names(current_user):
        return ["用户"]

    async def fake_create_ticket(**kwargs):
        calls.append(kwargs)
        return ticket

    async def fake_apply_defaults(current_ticket):
        current_ticket.defaulted = True
        return current_ticket

    async def fake_save_custom_values(*args, **kwargs):
        return []

    monkeypatch.setattr(issue_api, "_get_current_user", fake_current_user)
    monkeypatch.setattr(issue_api, "_get_user_role_names", fake_role_names)
    monkeypatch.setattr(issue_api.ticket_controller, "create_ticket", fake_create_ticket)
    monkeypatch.setattr(issue_api.issue_default_service, "apply_defaults", fake_apply_defaults)
    monkeypatch.setattr(issue_api, "_save_issue_custom_values", fake_save_custom_values)
    monkeypatch.setattr(issue_api, "_decorate_issue_rows", lambda rows: rows)

    response = await issue_api.create_issue(
        IssueCreateIn(
            title="内部Issue",
            company_name="安得内部",
            description="需要从Issue直接新建",
            project_phase="现网",
            issue_type="现网需求",
            category="需求",
            issue_priority_id=1,
        )
    )

    body = _response_body(response)
    assert body["data"]["id"] == 9
    assert calls[0]["submitter_id"] == 3
    assert calls[0]["notify_pending_review"] is False
    assert calls[0]["payload"]["company_name"] == "安得内部"
    assert calls[0]["payload"]["contact_name"] == "用户同学"
    assert calls[0]["payload"]["email"] == "user@example.com"
    assert calls[0]["payload"]["phone"] == "13800000000"
    assert calls[0]["payload"]["title"] == "内部Issue"
    assert calls[0]["payload"]["assigned_to_id"] == 3
