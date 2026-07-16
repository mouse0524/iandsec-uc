import pytest
from fastapi import HTTPException


def test_issue_core_models_are_importable():
    from app.models.admin import (
        IssueCustomField,
        IssueCustomValue,
        IssueJournal,
        IssueJournalDetail,
        IssuePriority,
        IssueQuery,
        IssueRelation,
        IssueStatus,
        IssueTimeEntry,
        IssueTracker,
        IssueWatcher,
        IssueWorkflowPermission,
        IssueWorkflowTransition,
        Ticket,
    )

    assert IssueTracker.Meta.table == "issue_tracker"
    assert IssueStatus.Meta.table == "issue_status"
    assert IssuePriority.Meta.table == "issue_priority"
    assert "active" in IssueStatus._meta.fields_map
    assert IssueWorkflowTransition.Meta.table == "issue_workflow_transition"
    assert IssueWorkflowPermission.Meta.table == "issue_workflow_permission"
    assert IssueWatcher.Meta.table == "issue_watcher"
    assert IssueRelation.Meta.table == "issue_relation"
    assert IssueTimeEntry.Meta.table == "issue_time_entry"
    assert IssueJournal.Meta.table == "issue_journal"
    assert IssueJournalDetail.Meta.table == "issue_journal_detail"
    assert IssueQuery.Meta.table == "issue_query"
    assert IssueCustomField.Meta.table == "issue_custom_field"
    assert IssueCustomValue.Meta.table == "issue_custom_value"
    assert Ticket._meta.fields_map["issue_tracker_id"].null is True


def test_issue_default_seed_configuration_matches_current_workflow():
    from app.core import init_app

    assert init_app.ISSUE_TRACKER_DEFAULT_STATUS == {"现网问题": "新建", "现网需求": "新建"}
    assert init_app.ISSUE_PRIORITY_SEEDS == [("高", False), ("中", True), ("低", False)]
    assert [name for name, is_closed, _is_default in init_app.ISSUE_STATUS_SEEDS if is_closed] == ["关闭"]

    workflow = {
        (role, tracker, old_status): tuple(new_statuses)
        for role, tracker, old_status, new_statuses in init_app.ISSUE_WORKFLOW_TRANSITION_SEEDS
    }
    assert [name for name, _is_closed, _is_default in init_app.ISSUE_STATUS_SEEDS] == [
        "新建",
        "商务审核",
        "技术处理",
        "测试过滤",
        "研发修改",
        "测试验证",
        "现场验证",
        "产品评估",
        "问题转需求",
        "关闭",
    ]
    assert workflow[("客服", "现网问题", "商务审核")] == ("新建", "技术处理")
    assert workflow[("客服", "现网需求", "商务审核")] == ("新建", "产品评估")
    assert workflow[("技术", "现网问题", "技术处理")] == ("新建", "测试过滤")
    assert workflow[("测试", "现网问题", "测试过滤")] == ("研发修改", "技术处理", "现场验证", "问题转需求")
    assert workflow[("测试", "现网问题", "测试验证")] == ("现场验证", "研发修改", "技术处理", "问题转需求")
    assert workflow[("研发", "现网问题", "研发修改")] == ("技术处理", "测试验证", "现场验证", "问题转需求")
    assert workflow[("产品", "现网问题", "问题转需求")] == ("研发修改", "测试验证", "现场验证")
    assert workflow[("产品", "现网需求", "产品评估")] == ("新建", "测试验证", "研发修改")
    assert workflow[("研发", "现网需求", "研发修改")] == ("产品评估", "测试验证")
    assert workflow[("测试", "现网需求", "测试验证")] == ("现场验证", "研发修改", "产品评估", "新建")
    for role in ("用户", "渠道商", "技术"):
        assert workflow[(role, "现网问题", "新建")] == ("商务审核",)
        assert workflow[(role, "现网需求", "新建")] == ("商务审核",)
        assert workflow[(role, "现网问题", "现场验证")] == ("技术处理", "测试验证", "关闭", "研发修改")
        assert workflow[(role, "现网需求", "现场验证")] == ("产品评估", "测试验证", "关闭", "研发修改")


@pytest.mark.anyio
async def test_ensure_named_row_does_not_overwrite_existing_admin_config():
    from app.core import init_app

    class ExistingRow:
        id = 1
        name = "中"
        position = 99
        is_default = False
        active = False
        saved = False

        async def save(self):
            self.saved = True

    existing = ExistingRow()

    class Model:
        @staticmethod
        async def get_or_create(name, defaults):
            return existing, False

    row = await init_app._ensure_named_row(
        Model,
        name="中",
        defaults={"position": 2, "is_default": True, "active": True},
    )

    assert row is existing
    assert existing.position == 99
    assert existing.is_default is False
    assert existing.active is False
    assert existing.saved is False


def test_system_ticket_settings_include_issue_metadata_defaults():
    from app.controllers.system_setting import (
        DEFAULT_TICKET_PRIORITIES,
        DEFAULT_TICKET_STATUSES,
        SystemSettingController,
    )

    ticket_defaults = SystemSettingController._DEFAULTS["ticket"]

    assert ticket_defaults["ticket_issue_types"] == ["现网问题", "现网需求"]
    assert ticket_defaults["ticket_statuses"] == DEFAULT_TICKET_STATUSES
    assert ticket_defaults["ticket_priorities"] == DEFAULT_TICKET_PRIORITIES
    assert "新建" in ticket_defaults["ticket_statuses"]
    assert "关闭" in ticket_defaults["ticket_statuses"]
    assert "中" in ticket_defaults["ticket_priorities"]


def test_ticket_status_settings_normalize_legacy_closed_label():
    from app.controllers.system_setting import SystemSettingController

    assert SystemSettingController._normalize_ticket_statuses(["新建", "已关闭", "关闭"]) == ["新建", "关闭"]
    assert SystemSettingController._normalize_ticket_statuses(["客服审核", "研发处理", "已解决"]) == [
        "商务审核",
        "研发修改",
        "现场验证",
    ]


@pytest.mark.anyio
async def test_sync_issue_metadata_does_not_overwrite_existing_status_flags(monkeypatch):
    from app.controllers.system_setting import SystemSettingController

    class Row:
        def __init__(self, name, **kwargs):
            self.name = name
            self.__dict__.update(kwargs)

        async def save(self):
            self.saved = True

    class Query:
        def __init__(self, model, predicate):
            self.model = model
            self.predicate = predicate

        async def update(self, **kwargs):
            for row in self.model.rows.values():
                if self.predicate(row):
                    row.__dict__.update(kwargs)

        async def first(self):
            return next((row for row in self.model.rows.values() if self.predicate(row)), None)

    class FakeStatus:
        rows = {
            "新建": Row("新建", position=9, is_closed=False, is_default=False, active=True),
            "QA关闭": Row("QA关闭", position=10, is_closed=True, is_default=False, active=True),
        }

        @classmethod
        async def get_or_create(cls, name, defaults):
            if name in cls.rows:
                return cls.rows[name], False
            cls.rows[name] = Row(name, **defaults)
            return cls.rows[name], True

        @classmethod
        def exclude(cls, **kwargs):
            if "name__in" in kwargs:
                names = set(kwargs["name__in"])
                return Query(cls, lambda row: row.name not in names)
            if "name" in kwargs:
                return Query(cls, lambda row: row.name != kwargs["name"])
            raise AssertionError(kwargs)

        @classmethod
        def filter(cls, **kwargs):
            return Query(
                cls,
                lambda row: all(getattr(row, key) == value for key, value in kwargs.items()),
            )

    class FakeOption:
        rows = {}

        @classmethod
        async def get_or_create(cls, name, defaults):
            cls.rows.setdefault(name, Row(name, **defaults))
            return cls.rows[name], name not in cls.rows

        @classmethod
        def filter(cls, **kwargs):
            return Query(cls, lambda row: row.name == kwargs.get("name"))

        @classmethod
        def exclude(cls, **kwargs):
            return Query(cls, lambda row: True)

    monkeypatch.setattr("app.controllers.system_setting.IssueStatus", FakeStatus)
    monkeypatch.setattr("app.controllers.system_setting.IssueTracker", FakeOption)
    monkeypatch.setattr("app.controllers.system_setting.IssuePriority", FakeOption)

    await SystemSettingController()._sync_issue_metadata(
        {"ticket_statuses": ["新建", "QA关闭"], "ticket_issue_types": ["现网问题"], "ticket_priorities": ["中"]}
    )

    assert FakeStatus.rows["QA关闭"].is_closed is True
    assert FakeStatus.rows["新建"].is_default is False


def test_issue_custom_value_format_round_trip():
    from app.api.v1.issues import issues as issue_api

    list_field = {"field_format": "list", "multiple": True}
    bool_field = {"field_format": "bool", "multiple": False}
    int_field = {"field_format": "int", "multiple": False}

    assert issue_api._custom_value_to_text(list_field, ["A", "B"]) == '["A", "B"]'
    assert issue_api._custom_text_to_api(list_field, '["A", "B"]') == ["A", "B"]
    assert issue_api._custom_value_to_text(bool_field, True) == "1"
    assert issue_api._custom_text_to_api(bool_field, "0") is False
    assert issue_api._custom_value_to_text(int_field, "0") == "0"
    assert issue_api._custom_text_to_api(int_field, "0") == 0


def test_issue_workflow_constraints_default_on():
    from app.schemas.issues import IssueAdminWorkflowSaveIn

    payload = IssueAdminWorkflowSaveIn(role_id=1, tracker_id=2, old_status_id=3, new_status_id=4)

    assert payload.assignee_required is True
    assert payload.author_allowed is True
    assert payload.assignee_allowed is True


def test_issue_workflow_save_allows_explicit_empty_targets_for_delete():
    from app.schemas.issues import IssueAdminWorkflowSaveIn

    payload = IssueAdminWorkflowSaveIn(role_id=1, tracker_id=2, old_status_id=3, new_status_ids=[])

    assert payload.new_status_ids == []


@pytest.mark.anyio
async def test_transition_options_follow_role_tracker_and_current_status():
    from app.controllers.issue import IssueWorkflowService

    transitions = [
        {"role_id": 1, "tracker_id": 10, "old_status_id": 20, "new_status_id": 30},
        {"role_id": 2, "tracker_id": 10, "old_status_id": 20, "new_status_id": 40},
        {"role_id": 1, "tracker_id": 11, "old_status_id": 20, "new_status_id": 50},
    ]

    service = IssueWorkflowService(transition_reader=lambda **kwargs: transitions)

    result = await service.allowed_status_ids(role_ids=[1], tracker_id=10, status_id=20)

    assert result == [30]


class FakeIssue:
    id = 7
    submitter_id = 3
    title = "旧标题"
    description = "旧描述"
    company_name = "旧项目"
    issue_type = "现网需求"
    issue_tracker_id = 10
    issue_status_id = 20
    issue_priority_id = None
    assigned_to_id = None
    root_cause = None
    priority_id = 1
    status = "tech_processing"
    closed_at = None
    lock_version = 0
    done_ratio = 0

    async def save(self):
        self.saved = True


@pytest.mark.anyio
async def test_update_issue_records_changed_fields_as_journal_details():
    from app.controllers.issue import IssueUpdateService

    issue = FakeIssue()
    journals = []
    details = []

    service = IssueUpdateService(
        issue_getter=lambda issue_id: issue,
        journal_writer=lambda **kwargs: journals.append(kwargs) or {"id": 99},
        detail_writer=lambda **kwargs: details.append(kwargs),
        workflow_service=None,
    )

    updated = await service.update_issue(
        issue_id=7,
        user_id=3,
        role_ids=[1],
        changes={"issue_status_id": 30, "assigned_to_id": 4, "company_name": "新项目"},
        notes="推进处理",
    )

    assert updated.issue_status_id == 30
    assert updated.assigned_to_id == 4
    assert updated.company_name == "新项目"
    assert updated.lock_version == 1
    assert journals[0]["notes"] == "推进处理"
    assert details == [
        {"journal_id": 99, "property": "attr", "prop_key": "issue_status_id", "old_value": "20", "value": "30"},
        {"journal_id": 99, "property": "attr", "prop_key": "assigned_to_id", "old_value": "", "value": "4"},
        {"journal_id": 99, "property": "attr", "prop_key": "company_name", "old_value": "旧项目", "value": "新项目"},
    ]


@pytest.mark.anyio
async def test_update_issue_allows_notes_only_journal():
    from app.controllers.issue import IssueUpdateService

    issue = FakeIssue()
    journals = []
    details = []

    service = IssueUpdateService(
        issue_getter=lambda issue_id: issue,
        journal_writer=lambda **kwargs: journals.append(kwargs) or {"id": 99},
        detail_writer=lambda **kwargs: details.append(kwargs),
        workflow_service=None,
    )

    updated = await service.update_issue(
        issue_id=7,
        user_id=3,
        role_ids=[1],
        changes={},
        notes="只补充说明",
    )

    assert updated is issue
    assert journals[0]["notes"] == "只补充说明"
    assert details == []


class DenyingWorkflow:
    async def allowed_transitions(self, **kwargs):
        return []


class OneTransitionWorkflow:
    def __init__(self, **transition):
        self.transition = {
            "role_id": 1,
            "tracker_id": 10,
            "old_status_id": 20,
            "new_status_id": 30,
            "assignee_required": True,
            "author_allowed": True,
            "assignee_allowed": True,
            **transition,
        }

    async def allowed_transitions(self, **kwargs):
        if kwargs.get("new_status_id") == self.transition["new_status_id"]:
            return [self.transition]
        return []


class FakeStatus:
    name = "关闭"
    is_closed = True


class FakeNewStatus:
    name = "新建"
    is_closed = False


@pytest.mark.anyio
async def test_update_issue_skips_workflow_check_when_status_is_unchanged():
    from app.controllers.issue import IssueUpdateService

    issue = FakeIssue()
    journals = []

    service = IssueUpdateService(
        issue_getter=lambda issue_id: issue,
        journal_writer=lambda **kwargs: journals.append(kwargs) or {"id": 100},
        detail_writer=lambda **kwargs: None,
        workflow_service=DenyingWorkflow(),
    )

    updated = await service.update_issue(
        issue_id=7,
        user_id=3,
        role_ids=[1],
        changes={"issue_status_id": 20, "assigned_to_id": 4},
    )

    assert updated.assigned_to_id == 4
    assert journals[0]["journalized_id"] == 7


@pytest.mark.anyio
async def test_update_issue_syncs_closed_status_side_effects():
    from app.controllers.issue import IssueUpdateService
    from app.models.enums import TicketStatus

    issue = FakeIssue()

    service = IssueUpdateService(
        issue_getter=lambda issue_id: issue,
        journal_writer=lambda **kwargs: {"id": 102},
        detail_writer=lambda **kwargs: None,
        status_reader=lambda status_id: FakeStatus(),
        workflow_service=None,
    )

    updated = await service.update_issue(
        issue_id=7,
        user_id=3,
        role_ids=[1],
        changes={"issue_status_id": 30, "assigned_to_id": 4, "root_cause": "代码缺陷"},
    )

    assert updated.status == TicketStatus.DONE
    assert updated.closed_at is not None


@pytest.mark.anyio
async def test_update_issue_marks_new_status_by_other_user_as_rejected():
    from app.controllers.issue import IssueUpdateService
    from app.models.enums import TicketStatus

    issue = FakeIssue()

    service = IssueUpdateService(
        issue_getter=lambda issue_id: issue,
        journal_writer=lambda **kwargs: {"id": 103},
        detail_writer=lambda **kwargs: None,
        status_reader=lambda status_id: FakeNewStatus(),
        workflow_service=None,
    )

    updated = await service.update_issue(
        issue_id=7,
        user_id=4,
        role_ids=[1],
        changes={"issue_status_id": 30},
    )

    assert updated.status == TicketStatus.CS_REJECTED


@pytest.mark.anyio
async def test_update_issue_requires_assignee_when_workflow_requires_it():
    from app.controllers.issue import IssueUpdateService

    service = IssueUpdateService(
        issue_getter=lambda issue_id: FakeIssue(),
        workflow_service=OneTransitionWorkflow(assignee_required=True),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_issue(
            issue_id=7,
            user_id=3,
            role_ids=[1],
            changes={"issue_status_id": 30},
        )

    assert exc_info.value.status_code == 400
    assert "指派人" in exc_info.value.detail


@pytest.mark.anyio
async def test_update_issue_respects_workflow_without_assignee_requirement():
    from app.controllers.issue import IssueUpdateService

    issue = FakeIssue()
    service = IssueUpdateService(
        issue_getter=lambda issue_id: issue,
        journal_writer=lambda **kwargs: {"id": 103},
        detail_writer=lambda **kwargs: None,
        workflow_service=OneTransitionWorkflow(assignee_required=False),
    )

    updated = await service.update_issue(
        issue_id=7,
        user_id=3,
        role_ids=[1],
        changes={"issue_status_id": 30},
    )

    assert updated.issue_status_id == 30


@pytest.mark.anyio
async def test_update_issue_rejects_author_when_workflow_disallows_author():
    from app.controllers.issue import IssueUpdateService

    service = IssueUpdateService(
        issue_getter=lambda issue_id: FakeIssue(),
        workflow_service=OneTransitionWorkflow(assignee_required=False, author_allowed=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_issue(
            issue_id=7,
            user_id=3,
            role_ids=[1],
            changes={"issue_status_id": 30},
        )

    assert exc_info.value.status_code == 400
    assert "当前用户" in exc_info.value.detail


@pytest.mark.anyio
async def test_update_issue_requires_root_cause_when_closing():
    from app.controllers.issue import IssueUpdateService

    service = IssueUpdateService(
        issue_getter=lambda issue_id: FakeIssue(),
        status_reader=lambda status_id: FakeStatus(),
        workflow_service=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_issue(
            issue_id=7,
            user_id=3,
            role_ids=[1],
            changes={"issue_status_id": 30, "assigned_to_id": 4},
        )

    assert exc_info.value.status_code == 400
    assert "问题根因" in exc_info.value.detail


@pytest.mark.anyio
async def test_update_issue_can_bypass_workflow_for_superuser():
    from app.controllers.issue import IssueUpdateService

    issue = FakeIssue()

    service = IssueUpdateService(
        issue_getter=lambda issue_id: issue,
        journal_writer=lambda **kwargs: {"id": 101},
        detail_writer=lambda **kwargs: None,
        workflow_service=DenyingWorkflow(),
    )

    updated = await service.update_issue(
        issue_id=7,
        user_id=1,
        role_ids=[],
        changes={"issue_status_id": 30, "assigned_to_id": 4},
        bypass_workflow=True,
    )

    assert updated.issue_status_id == 30


@pytest.mark.anyio
async def test_update_issue_rejects_invalid_done_ratio():
    from app.controllers.issue import IssueUpdateService

    service = IssueUpdateService(
        issue_getter=lambda issue_id: FakeIssue(),
        workflow_service=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_issue(
            issue_id=7,
            user_id=3,
            role_ids=[1],
            changes={"done_ratio": 101},
        )

    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_update_issue_rejects_non_issue_fields():
    from app.controllers.issue import IssueUpdateService

    service = IssueUpdateService(
        issue_getter=lambda issue_id: FakeIssue(),
        workflow_service=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_issue(
            issue_id=7,
            user_id=3,
            role_ids=[1],
            changes={"id": 8},
        )

    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_update_issue_required_field_errors_use_chinese_labels():
    from app.controllers.issue import IssueUpdateService

    service = IssueUpdateService(
        issue_getter=lambda issue_id: FakeIssue(),
        workflow_service=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_issue(
            issue_id=7,
            user_id=3,
            role_ids=[1],
            changes={"company_name": ""},
        )

    assert exc_info.value.detail == "项目名称不能为空"


@pytest.mark.anyio
async def test_update_issue_rejects_empty_required_issue_ids():
    from app.controllers.issue import IssueUpdateService

    service = IssueUpdateService(
        issue_getter=lambda issue_id: FakeIssue(),
        workflow_service=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_issue(
            issue_id=7,
            user_id=3,
            role_ids=[1],
            changes={"issue_tracker_id": None},
        )

    assert exc_info.value.detail == "跟踪不能为空"


@pytest.mark.anyio
async def test_update_issue_rejects_empty_rich_text_description():
    from app.controllers.issue import IssueUpdateService

    service = IssueUpdateService(
        issue_getter=lambda issue_id: FakeIssue(),
        workflow_service=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_issue(
            issue_id=7,
            user_id=3,
            role_ids=[1],
            changes={"description": "<p><br></p>"},
        )

    assert exc_info.value.detail == "描述不能为空"


class FakeTracker:
    id = 11
    name = "现网需求"
    default_status_id = 21


class FakeDefaultStatus:
    id = 21
    name = "商务审核"
    is_closed = False


class FakePriority:
    id = 5
    name = "中"


@pytest.mark.anyio
async def test_issue_defaults_are_applied_when_ticket_is_created():
    from app.controllers.issue import IssueDefaultService
    from app.models.enums import TicketStatus

    issue = FakeIssue()
    issue.issue_tracker_id = None
    issue.issue_status_id = None
    issue.status = TicketStatus.PENDING_REVIEW

    service = IssueDefaultService(
        tracker_reader=lambda current_issue: FakeTracker(),
        status_reader=lambda status_id=None, name=None: FakeDefaultStatus(),
        priority_reader=lambda: FakePriority(),
    )

    updated = await service.apply_defaults(issue)

    assert updated.issue_tracker_id == 11
    assert updated.issue_type == "现网需求"
    assert updated.issue_status_id == 21
    assert updated.issue_priority_id == 5
    assert updated.status == TicketStatus.PENDING_REVIEW
    assert updated.closed_at is None
    assert updated.saved is True
