import inspect
from collections.abc import Callable, Iterable
from datetime import datetime
from html import unescape
import re
from typing import Any

from fastapi import HTTPException

from app.models.admin import (
    IssueJournal,
    IssueJournalDetail,
    IssuePriority,
    IssueStatus,
    IssueTracker,
    IssueWorkflowTransition,
    Ticket,
)
from app.models.enums import TicketStatus


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def _get_value(item: Any, key: str):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _row_id(item: Any) -> int:
    value = _get_value(item, "id")
    if value is None:
        raise HTTPException(status_code=500, detail="Journal创建失败")
    return int(value)


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _plain_text(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", unescape(str(value or "")))).strip()


ISSUE_UPDATE_FIELDS = frozenset(
    {
        "issue_project_id",
        "issue_tracker_id",
        "issue_status_id",
        "issue_priority_id",
        "issue_category_id",
        "issue_fixed_version_id",
        "parent_issue_id",
        "root_issue_id",
        "assigned_to_id",
        "start_date",
        "due_date",
        "done_ratio",
        "estimated_hours",
        "closed_at",
        "is_private",
        "company_name",
        "project_phase",
        "issue_type",
        "impact_scope",
        "category",
        "root_cause",
        "title",
        "description",
    }
)
ISSUE_REQUIRED_TEXT_FIELDS = frozenset(
    {"company_name", "project_phase", "issue_type", "impact_scope", "category", "title", "description"}
)
ISSUE_REQUIRED_ID_FIELDS = frozenset({"issue_tracker_id", "issue_status_id", "issue_priority_id"})
ISSUE_FIELD_LABELS = {
    "company_name": "项目名称",
    "project_phase": "项目阶段",
    "issue_type": "跟踪",
    "impact_scope": "影响范围",
    "category": "问题分类",
    "title": "标题",
    "description": "描述",
    "issue_tracker_id": "跟踪",
    "issue_status_id": "状态",
    "issue_priority_id": "优先级",
}

ISSUE_STATUS_TO_TICKET_STATUS = {
    "客服审核": TicketStatus.PENDING_REVIEW,
    "客服驳回": TicketStatus.CS_REJECTED,
    "技术处理": TicketStatus.TECH_PROCESSING,
    "测试过滤": TicketStatus.TEST_FILTERING,
    "产品评估": TicketStatus.PRODUCT_EVALUATION,
    "研发处理": TicketStatus.RD_PROCESSING,
    "测试验证": TicketStatus.TEST_VERIFICATION,
    "现场验证": TicketStatus.FIELD_VERIFICATION,
    "已解决": TicketStatus.PENDING_CLOSE,
    "关闭": TicketStatus.DONE,
    "不采纳": TicketStatus.DONE,
}
LEGACY_TICKET_STATUS_TO_ISSUE_STATUS = {
    TicketStatus.PENDING_REVIEW: "客服审核",
    TicketStatus.CS_REJECTED: "客服驳回",
    TicketStatus.TECH_PROCESSING: "技术处理",
    TicketStatus.TEST_FILTERING: "测试过滤",
    TicketStatus.PRODUCT_EVALUATION: "产品评估",
    TicketStatus.RD_PROCESSING: "研发处理",
    TicketStatus.TEST_VERIFICATION: "测试验证",
    TicketStatus.FIELD_VERIFICATION: "现场验证",
    TicketStatus.PENDING_CLOSE: "已解决",
    TicketStatus.TECH_REJECTED: "技术处理",
    TicketStatus.DONE: "关闭",
}


class IssueDefaultService:
    def __init__(
        self,
        *,
        tracker_reader: Callable[..., Any] | None = None,
        status_reader: Callable[..., Any] | None = None,
        priority_reader: Callable[..., Any] | None = None,
    ):
        self.tracker_reader = tracker_reader
        self.status_reader = status_reader
        self.priority_reader = priority_reader

    async def _read_tracker(self, issue):
        if self.tracker_reader:
            return await _maybe_await(self.tracker_reader(issue))
        tracker_id = int(getattr(issue, "issue_tracker_id", None) or 0)
        if tracker_id:
            tracker = await IssueTracker.filter(id=tracker_id, is_active=True).first()
            if tracker:
                return tracker
        issue_type = str(getattr(issue, "issue_type", "") or "").strip()
        if issue_type:
            tracker = await IssueTracker.filter(name=issue_type, is_active=True).first()
            if tracker:
                return tracker
        return await IssueTracker.filter(is_active=True).order_by("position", "id").first()

    async def _read_status(self, status_id: int | None = None, name: str | None = None):
        if self.status_reader:
            return await _maybe_await(self.status_reader(status_id=status_id, name=name))
        if status_id:
            return await IssueStatus.filter(id=status_id).first()
        if name:
            return await IssueStatus.filter(name=name, active=True).first()
        return (
            await IssueStatus.filter(active=True, is_default=True).order_by("position", "id").first()
            or await IssueStatus.filter(active=True).order_by("position", "id").first()
        )

    async def _read_priority(self):
        if self.priority_reader:
            return await _maybe_await(self.priority_reader())
        return (
            await IssuePriority.filter(active=True, is_default=True).order_by("position", "id").first()
            or await IssuePriority.filter(active=True).order_by("position", "id").first()
        )

    async def _default_status_for_issue(self, issue, tracker):
        default_status_id = int(_get_value(tracker, "default_status_id") or 0) if tracker else 0
        status = await self._read_status(status_id=default_status_id or None)
        if status:
            return status
        legacy_name = LEGACY_TICKET_STATUS_TO_ISSUE_STATUS.get(getattr(issue, "status", None))
        return await self._read_status(name=legacy_name) if legacy_name else None

    async def apply_defaults(self, issue):
        changed = False
        tracker = await self._read_tracker(issue)
        if tracker:
            tracker_id = int(_get_value(tracker, "id"))
            tracker_name = str(_get_value(tracker, "name") or "")
            if getattr(issue, "issue_tracker_id", None) != tracker_id:
                issue.issue_tracker_id = tracker_id
                changed = True
            if tracker_name and getattr(issue, "issue_type", None) != tracker_name:
                issue.issue_type = tracker_name
                changed = True

        priority_id = int(getattr(issue, "issue_priority_id", None) or 0)
        if not priority_id:
            priority = await self._read_priority()
            if priority:
                issue.issue_priority_id = int(_get_value(priority, "id"))
                changed = True

        status_id = int(getattr(issue, "issue_status_id", None) or 0)
        status = (
            await self._read_status(status_id=status_id)
            if status_id
            else await self._default_status_for_issue(issue, tracker)
        )
        if status:
            new_status_id = int(_get_value(status, "id"))
            if getattr(issue, "issue_status_id", None) != new_status_id:
                issue.issue_status_id = new_status_id
                changed = True
            status_name = str(_get_value(status, "name") or "")
            legacy_status = ISSUE_STATUS_TO_TICKET_STATUS.get(status_name)
            if legacy_status and hasattr(issue, "status") and getattr(issue, "status", None) != legacy_status:
                issue.status = legacy_status
                changed = True
            if hasattr(issue, "closed_at"):
                closed_at = datetime.now() if bool(_get_value(status, "is_closed")) else None
                if bool(getattr(issue, "closed_at", None)) != bool(closed_at):
                    issue.closed_at = closed_at
                    changed = True

        if changed:
            await _maybe_await(issue.save())
        return issue


issue_default_service = IssueDefaultService()


class IssueWorkflowService:
    def __init__(self, transition_reader: Callable[..., Any] | None = None):
        self.transition_reader = transition_reader

    async def _read_transitions(self, *, role_ids: list[int], tracker_id: int, status_id: int):
        if self.transition_reader:
            return await _maybe_await(
                self.transition_reader(role_ids=role_ids, tracker_id=tracker_id, status_id=status_id)
            )
        return await IssueWorkflowTransition.filter(
            role_id__in=role_ids,
            tracker_id=tracker_id,
            old_status_id=status_id,
        ).order_by("id")

    async def allowed_transitions(
        self,
        *,
        role_ids: Iterable[int],
        tracker_id: int,
        status_id: int,
        new_status_id: int | None = None,
    ) -> list[Any]:
        allowed_role_ids = {int(role_id) for role_id in role_ids}
        rows = await self._read_transitions(
            role_ids=list(allowed_role_ids),
            tracker_id=int(tracker_id),
            status_id=int(status_id),
        )
        result = []
        seen: set[tuple[int, int, int, int]] = set()
        for row in rows or []:
            role_id = int(_get_value(row, "role_id") or 0)
            row_tracker_id = int(_get_value(row, "tracker_id") or 0)
            old_status_id = int(_get_value(row, "old_status_id") or 0)
            next_status_id = int(_get_value(row, "new_status_id") or 0)
            if role_id not in allowed_role_ids:
                continue
            if row_tracker_id != int(tracker_id) or old_status_id != int(status_id):
                continue
            if new_status_id is not None and next_status_id != int(new_status_id):
                continue
            key = (role_id, row_tracker_id, old_status_id, next_status_id)
            if not next_status_id or key in seen:
                continue
            seen.add(key)
            result.append(row)
        return result

    async def allowed_status_ids(self, *, role_ids: Iterable[int], tracker_id: int, status_id: int) -> list[int]:
        rows = await self.allowed_transitions(role_ids=role_ids, tracker_id=tracker_id, status_id=status_id)
        result: list[int] = []
        seen: set[int] = set()
        for row in rows:
            next_status_id = int(_get_value(row, "new_status_id") or 0)
            if not next_status_id or next_status_id in seen:
                continue
            seen.add(next_status_id)
            result.append(next_status_id)
        return result


issue_workflow_service = IssueWorkflowService()


class IssueUpdateService:
    def __init__(
        self,
        *,
        issue_getter: Callable[..., Any] | None = None,
        journal_writer: Callable[..., Any] | None = None,
        detail_writer: Callable[..., Any] | None = None,
        status_reader: Callable[..., Any] | None = None,
        workflow_service: IssueWorkflowService | None = issue_workflow_service,
    ):
        self.issue_getter = issue_getter
        self.journal_writer = journal_writer
        self.detail_writer = detail_writer
        self.status_reader = status_reader
        self.workflow_service = workflow_service

    async def _get_issue(self, issue_id: int):
        if self.issue_getter:
            return await _maybe_await(self.issue_getter(issue_id))
        return await Ticket.filter(id=issue_id).first()

    async def _write_journal(self, **kwargs):
        if self.journal_writer:
            return await _maybe_await(self.journal_writer(**kwargs))
        return await IssueJournal.create(**kwargs)

    async def _write_detail(self, **kwargs):
        if self.detail_writer:
            return await _maybe_await(self.detail_writer(**kwargs))
        return await IssueJournalDetail.create(**kwargs)

    async def _read_status(self, status_id: int):
        if not self.status_reader:
            return None
        return await _maybe_await(self.status_reader(status_id))

    @staticmethod
    def _transition_allows_user(transition, *, issue, user_id: int) -> bool:
        is_author = _int_value(getattr(issue, "submitter_id", None)) == int(user_id)
        is_assignee = _int_value(getattr(issue, "assigned_to_id", None)) == int(user_id)
        if is_author and bool(_get_value(transition, "author_allowed")):
            return True
        if is_assignee and bool(_get_value(transition, "assignee_allowed")):
            return True
        return not is_author and not is_assignee

    async def _assert_status_transition(
        self,
        *,
        issue,
        user_id: int,
        role_ids: list[int],
        new_status_id: int,
        changes: dict[str, Any],
        bypass: bool,
    ) -> None:
        if bypass or not self.workflow_service:
            return
        old_status_id = int(getattr(issue, "issue_status_id") or 0)
        tracker_id = int(getattr(issue, "issue_tracker_id") or 0)
        if not old_status_id or not tracker_id:
            return
        transitions = await self.workflow_service.allowed_transitions(
            role_ids=role_ids,
            tracker_id=tracker_id,
            status_id=old_status_id,
            new_status_id=new_status_id,
        )
        if not transitions:
            raise HTTPException(status_code=400, detail="当前角色不可执行该状态流转")
        allowed_transitions = [
            transition
            for transition in transitions
            if self._transition_allows_user(transition, issue=issue, user_id=user_id)
        ]
        if not allowed_transitions:
            raise HTTPException(status_code=400, detail="当前用户不可执行该状态流转")
        if any(bool(_get_value(transition, "assignee_required")) for transition in allowed_transitions):
            assignee_id = _int_value(changes.get("assigned_to_id", getattr(issue, "assigned_to_id", None)))
            if not assignee_id:
                raise HTTPException(status_code=400, detail="状态变更时必须指定当前指派人")

    async def _apply_status_side_effects(self, *, issue, status_id: int) -> None:
        status = await self._read_status(status_id)
        if not status:
            return
        status_name = str(_get_value(status, "name") or "")
        legacy_status = ISSUE_STATUS_TO_TICKET_STATUS.get(status_name)
        if legacy_status and hasattr(issue, "status"):
            issue.status = legacy_status
        if hasattr(issue, "closed_at"):
            issue.closed_at = datetime.now() if bool(_get_value(status, "is_closed")) else None

    @staticmethod
    def _validate_field(field: str, value: Any) -> None:
        if field in ISSUE_REQUIRED_TEXT_FIELDS and not _plain_text(value):
            raise HTTPException(status_code=400, detail=f"{ISSUE_FIELD_LABELS[field]}不能为空")
        if field in ISSUE_REQUIRED_ID_FIELDS and not _int_value(value):
            raise HTTPException(status_code=400, detail=f"{ISSUE_FIELD_LABELS[field]}不能为空")
        if field == "done_ratio":
            try:
                ratio = int(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="完成率必须在0到100之间") from None
            if not 0 <= ratio <= 100:
                raise HTTPException(status_code=400, detail="完成率必须在0到100之间")
        if field == "estimated_hours" and value is not None:
            try:
                hours = float(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="预估工时不能小于0") from None
            if hours < 0:
                raise HTTPException(status_code=400, detail="预估工时不能小于0")

    async def update_issue(
        self,
        *,
        issue_id: int,
        user_id: int,
        role_ids: Iterable[int],
        changes: dict[str, Any],
        notes: str | None = None,
        private_notes: bool = False,
        bypass_workflow: bool = False,
    ):
        issue = await self._get_issue(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue不存在")

        changed: list[tuple[str, str, str]] = []
        role_id_list = [int(role_id) for role_id in role_ids]
        for field, new_value in changes.items():
            if field not in ISSUE_UPDATE_FIELDS or not hasattr(issue, field):
                raise HTTPException(status_code=400, detail=f"不支持更新字段: {field}")
            self._validate_field(field, new_value)

        old_status_id = _int_value(getattr(issue, "issue_status_id", None))
        next_status_id = _int_value(changes.get("issue_status_id", old_status_id))
        status_changed = "issue_status_id" in changes and next_status_id != old_status_id
        next_status = await self._read_status(next_status_id) if next_status_id else None
        if next_status and bool(_get_value(next_status, "is_closed")):
            root_cause = changes.get("root_cause", getattr(issue, "root_cause", None))
            if not str(root_cause or "").strip():
                raise HTTPException(status_code=400, detail="关闭工单时必须填写问题根因")

        for field, new_value in changes.items():
            old_value = getattr(issue, field)
            if old_value == new_value:
                continue
            if field == "issue_status_id":
                await self._assert_status_transition(
                    issue=issue,
                    user_id=user_id,
                    role_ids=role_id_list,
                    new_status_id=int(new_value),
                    changes=changes,
                    bypass=bypass_workflow,
                )
                await self._apply_status_side_effects(issue=issue, status_id=int(new_value))
            setattr(issue, field, new_value)
            changed.append((field, _string_value(old_value), _string_value(new_value)))

        if not changed and not (notes or "").strip():
            return issue

        if changed and hasattr(issue, "lock_version"):
            issue.lock_version = int(getattr(issue, "lock_version") or 0) + 1
        await _maybe_await(issue.save())
        journal = await self._write_journal(
            journalized_type="Issue",
            journalized_id=issue.id,
            user_id=user_id,
            notes=(notes or "").strip() or None,
            private_notes=private_notes,
        )
        journal_id = _row_id(journal)
        for field, old_value, new_value in changed:
            await self._write_detail(
                journal_id=journal_id,
                property="attr",
                prop_key=field,
                old_value=old_value,
                value=new_value,
            )
        return issue


async def _read_issue_status(status_id: int):
    return await IssueStatus.filter(id=status_id).first()


issue_update_service = IssueUpdateService(status_reader=_read_issue_status)
