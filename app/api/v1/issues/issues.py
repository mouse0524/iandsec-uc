import inspect
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from tortoise.expressions import Q

from app.api.v1.tickets.tickets import _get_current_user, _get_user_role_names, _tech_related_submitter_ids
from app.controllers.issue import (
    ISSUE_FIELD_LABELS,
    _int_value,
    _plain_text,
    issue_default_service,
    issue_update_service,
    issue_workflow_service,
)
from app.controllers.ticket import ticket_controller
from app.core.dependency import DependAuth
from app.models.admin import (
    IssueCategory,
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
    IssueVersion,
    IssueWatcher,
    IssueWorkflowTransition,
    Project,
    Role,
    Ticket,
    TicketAttachment,
    User,
)
from app.models.enums import (
    IssueCustomFieldFormat,
    ROLE_ADMIN,
    ROLE_CUSTOMER_SERVICE,
    ROLE_PRODUCT,
    ROLE_RD,
    ROLE_TECH,
    ROLE_TEST,
    ROLE_USER,
    ROLE_CHANNEL,
    ROLE_AGENT,
    IssueRelationType,
)
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.issues import (
    IssueAdminCustomFieldSaveIn,
    IssueAdminPrioritySaveIn,
    IssueAdminStatusSaveIn,
    IssueAdminTrackerSaveIn,
    IssueAdminWorkflowSaveIn,
    IssueCreateIn,
    IssueQueryCreateIn,
    IssueQueryUpdateIn,
    IssueRelationCreateIn,
    IssueTimeEntryCreateIn,
    IssueUpdateIn,
    IssueWatcherIn,
)
from app.settings import settings

router = APIRouter()

ISSUE_CUSTOM_FIELD_FORMAT_OPTIONS = [
    {"label": "单行文本", "value": IssueCustomFieldFormat.STRING.value},
    {"label": "多行文本", "value": IssueCustomFieldFormat.TEXT.value},
    {"label": "日期", "value": IssueCustomFieldFormat.DATE.value},
    {"label": "列表", "value": IssueCustomFieldFormat.LIST.value},
]

ISSUE_LIST_FIELDS = [
    "id",
    "ticket_no",
    "title",
    "description",
    "status",
    "issue_type",
    "project_phase",
    "company_name",
    "submitter_id",
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
    "created_at",
    "updated_at",
]
ISSUE_UPDATE_ROLES = {
    ROLE_ADMIN,
    ROLE_CUSTOMER_SERVICE,
    ROLE_TECH,
    ROLE_PRODUCT,
    ROLE_TEST,
    ROLE_RD,
    ROLE_USER,
    ROLE_CHANNEL,
    ROLE_AGENT,
}
ISSUE_CREATE_ROLES = ISSUE_UPDATE_ROLES
ISSUE_QUERY_FILTER_FIELDS = {
    "issue_project_id",
    "issue_tracker_id",
    "issue_status_id",
    "issue_priority_id",
    "assigned_to_id",
    "submitter_id",
}
ISSUE_SORT_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "issue_project_id",
    "issue_tracker_id",
    "issue_status_id",
    "issue_priority_id",
    "assigned_to_id",
    "due_date",
    "done_ratio",
}


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _daily_trend(rows: list[dict], field: str, today: date) -> list[dict[str, Any]]:
    start = today - timedelta(days=6)
    counts = Counter(
        dt.date()
        for row in rows
        if (dt := _as_datetime(row.get(field))) and start <= dt.date() <= today
    )
    return [
        {"date": day.isoformat(), "count": counts.get(day, 0)}
        for day in (start + timedelta(days=index) for index in range(7))
    ]


def _weekly_trend(rows: list[dict], field: str, today: date) -> list[dict[str, Any]]:
    week_start = today - timedelta(days=today.weekday())
    starts = [week_start - timedelta(weeks=index) for index in range(6, -1, -1)]
    counts = Counter(
        dt.date() - timedelta(days=dt.date().weekday())
        for row in rows
        if (dt := _as_datetime(row.get(field))) and starts[0] <= dt.date() <= today
    )
    return [
        {
            "week": f"{start.isocalendar().year}-W{start.isocalendar().week:02d}",
            "count": counts.get(start, 0),
        }
        for start in starts
    ]


def _issue_dashboard_data(rows: list[dict], statuses: list[dict]) -> dict[str, Any]:
    today = datetime.now().date()
    stale_before = datetime.now() - timedelta(days=7)
    status_map = {int(row["id"]): row for row in statuses if row.get("id") is not None}
    status_counts = Counter(_coerce_int(row.get("issue_status_id")) for row in rows)
    project_counts = Counter((str(row.get("company_name") or "").strip() or "未填写项目") for row in rows)
    stale_rows = [
        row
        for row in rows
        if not status_map.get(_coerce_int(row.get("issue_status_id")) or 0, {}).get("is_closed")
        and (updated_at := _as_datetime(row.get("updated_at")))
        and updated_at < stale_before
    ]
    return {
        "total": len(rows),
        "status_counts": [
            {
                "status_id": status_id,
                "name": status_map.get(status_id, {}).get("name") or "未设置",
                "is_closed": bool(status_map.get(status_id, {}).get("is_closed")),
                "count": count,
            }
            for status_id, count in status_counts.most_common()
        ],
        "top_projects": [
            {"project_name": name, "count": count} for name, count in project_counts.most_common(10)
        ],
        "created_trend": {
            "daily": _daily_trend(rows, "created_at", today),
            "weekly": _weekly_trend(rows, "created_at", today),
        },
        "closed_trend": {
            "daily": _daily_trend(rows, "closed_at", today),
            "weekly": _weekly_trend(rows, "closed_at", today),
        },
        "stale_issues": [
            {
                "id": row.get("id"),
                "title": row.get("title") or "-",
                "project_name": row.get("company_name") or "未填写项目",
                "updated_at": _json_value(row.get("updated_at")),
                "days": (today - updated_at.date()).days if (updated_at := _as_datetime(row.get("updated_at"))) else 0,
            }
            for row in sorted(stale_rows, key=lambda item: _as_datetime(item.get("updated_at")) or datetime.max)[:10]
        ],
    }
ISSUE_VIEW_ALL_ROLES = {ROLE_ADMIN, ROLE_CUSTOMER_SERVICE, ROLE_PRODUCT, ROLE_TEST, ROLE_RD}


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def _json_value(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _json_row(row: dict) -> dict:
    return {key: _json_value(value) for key, value in row.items()}


def _display_user(user: User) -> str:
    return str(user.alias or user.username or user.id)


def _detail_ids(details: list[IssueJournalDetail], prop_key: str) -> set[int]:
    ids = set()
    for detail in details:
        if detail.prop_key != prop_key:
            continue
        for value in (detail.old_value, detail.value):
            item_id = _int_value(value)
            if item_id:
                ids.add(item_id)
    return ids


async def _role_ids(user: User) -> list[int]:
    roles = await _maybe_await(user.roles)
    return [int(role.id) for role in roles or [] if getattr(role, "id", None)]


async def _model_dict(model) -> dict:
    return _json_row(await _maybe_await(model.to_dict()))


def _ticket_attachment_file_exists(attachment: TicketAttachment) -> bool:
    abs_path = os.path.normcase(os.path.realpath(os.path.join(settings.UPLOAD_DIR, attachment.file_path or "")))
    upload_root = os.path.normcase(os.path.realpath(settings.UPLOAD_DIR))
    try:
        if os.path.commonpath([abs_path, upload_root]) != upload_root:
            return False
    except ValueError:
        return False
    return os.path.exists(abs_path)


async def _rows_by_id(model, ids: set[int], *fields: str) -> dict[int, dict]:
    if not ids:
        return {}
    rows = await model.filter(id__in=list(ids)).values("id", *fields)
    return {int(row["id"]): _json_row(row) for row in rows}


def _custom_value_is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set)):
        return not [item for item in value if not _custom_value_is_empty(item)]
    return False


def _custom_value_to_text(field: dict, value: Any) -> str:
    field_format = str(field.get("field_format") or IssueCustomFieldFormat.STRING)
    if _custom_value_is_empty(value):
        return ""
    if bool(field.get("multiple")):
        values = value if isinstance(value, list) else [value]
        return json.dumps([str(item) for item in values if not _custom_value_is_empty(item)], ensure_ascii=False)
    if field_format == IssueCustomFieldFormat.BOOL:
        if isinstance(value, str):
            return "1" if value.strip().lower() in {"1", "true", "yes", "on", "是"} else "0"
        return "1" if bool(value) else "0"
    if field_format in {IssueCustomFieldFormat.INT, IssueCustomFieldFormat.USER, IssueCustomFieldFormat.VERSION}:
        return str(int(value))
    if field_format == IssueCustomFieldFormat.FLOAT:
        return str(float(value))
    return str(value).strip()


def _custom_text_to_api(field: dict, value: Any):
    field_format = str(field.get("field_format") or IssueCustomFieldFormat.STRING)
    if value in (None, ""):
        return [] if bool(field.get("multiple")) else None
    if bool(field.get("multiple")):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            parsed = [value]
        return parsed if isinstance(parsed, list) else [parsed]
    if field_format == IssueCustomFieldFormat.BOOL:
        return str(value) == "1"
    if field_format in {IssueCustomFieldFormat.INT, IssueCustomFieldFormat.USER, IssueCustomFieldFormat.VERSION}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if field_format == IssueCustomFieldFormat.FLOAT:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


async def _visible_custom_fields() -> list[dict]:
    rows = (
        await IssueCustomField.filter(type="issue", visible=True)
        .order_by("position", "id")
        .values(
            "id",
            "name",
            "field_format",
            "possible_values",
            "default_value",
            "is_required",
            "is_filter",
            "searchable",
            "multiple",
            "position",
        )
    )
    return [_json_row(row) for row in rows]


async def _custom_values_by_issue(issue_ids: list[int], fields: list[dict] | None = None) -> dict[int, dict[str, Any]]:
    if not issue_ids:
        return {}
    fields = fields if fields is not None else await _visible_custom_fields()
    field_map = {int(field["id"]): field for field in fields}
    rows = await IssueCustomValue.filter(customized_type="Issue", customized_id__in=issue_ids).values(
        "customized_id",
        "custom_field_id",
        "value",
    )
    result: dict[int, dict[str, Any]] = {int(issue_id): {} for issue_id in issue_ids}
    for row in rows:
        field = field_map.get(int(row["custom_field_id"]))
        if field:
            result[int(row["customized_id"])][str(row["custom_field_id"])] = _custom_text_to_api(field, row["value"])
    return result


async def _save_issue_custom_values(
    issue_id: int, values: dict[str, Any] | None, *, validate_required: bool = False
) -> list[dict]:
    fields = await _visible_custom_fields()
    if not fields:
        return []
    submitted = values or {}
    field_ids = [int(field["id"]) for field in fields]
    existing_rows = await IssueCustomValue.filter(
        customized_type="Issue",
        customized_id=issue_id,
        custom_field_id__in=field_ids,
    ).order_by("id")
    existing: dict[int, IssueCustomValue] = {}
    for row in existing_rows:
        field_id = int(row.custom_field_id)
        if field_id in existing:
            await row.delete()
        else:
            existing[field_id] = row

    details: list[dict] = []
    for field in fields:
        field_id = int(field["id"])
        key = str(field_id)
        has_value = key in submitted or field_id in submitted
        raw_value = submitted.get(key, submitted.get(field_id))
        if not has_value and validate_required:
            raw_value = field.get("default_value")
        if validate_required and field.get("is_required") and _custom_value_is_empty(raw_value):
            raise HTTPException(status_code=400, detail=f"请填写自定义字段：{field['name']}")
        if not has_value and not validate_required:
            continue
        try:
            new_value = _custom_value_to_text(field, raw_value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"自定义字段格式不正确：{field['name']}") from None
        old_row = existing.get(field_id)
        old_value = old_row.value if old_row else None
        if (old_value or "") == new_value:
            continue
        if new_value:
            if old_row:
                old_row.value = new_value
                await old_row.save()
            else:
                await IssueCustomValue.create(
                    customized_type="Issue",
                    customized_id=issue_id,
                    custom_field_id=field_id,
                    value=new_value,
                )
        elif old_row:
            await old_row.delete()
        details.append({"property": "cf", "prop_key": key, "old_value": old_value, "value": new_value or None})
    return details


async def _metadata_lists() -> dict[str, list[dict]]:
    trackers = (
        await IssueTracker.filter(is_active=True)
        .order_by("position", "id")
        .values("id", "name", "description", "default_status_id", "is_in_roadmap")
    )
    statuses = (
        await IssueStatus.filter(active=True).order_by("position", "id").values("id", "name", "is_closed", "is_default")
    )
    priorities = await IssuePriority.filter(active=True).order_by("position", "id").values("id", "name", "is_default")
    categories = (
        await IssueCategory.all().order_by("project_id", "name").values("id", "project_id", "name", "assigned_to_id")
    )
    versions = (
        await IssueVersion.all()
        .order_by("project_id", "name")
        .values("id", "project_id", "name", "status", "effective_date")
    )
    custom_fields = await _visible_custom_fields()
    return {
        "trackers": [_json_row(row) for row in trackers],
        "statuses": [_json_row(row) for row in statuses],
        "priorities": [_json_row(row) for row in priorities],
        "categories": [_json_row(row) for row in categories],
        "versions": [_json_row(row) for row in versions],
        "custom_fields": custom_fields,
        "relation_types": [{"label": item.value, "value": item.value} for item in IssueRelationType],
    }


async def _admin_metadata_lists() -> dict[str, list[dict]]:
    trackers = (
        await IssueTracker.all()
        .order_by("position", "id")
        .values(
            "id",
            "name",
            "description",
            "position",
            "default_status_id",
            "is_in_roadmap",
            "copy_workflow_from_id",
            "is_active",
        )
    )
    statuses = (
        await IssueStatus.all()
        .order_by("position", "id")
        .values("id", "name", "position", "is_closed", "is_default", "active")
    )
    priorities = (
        await IssuePriority.all().order_by("position", "id").values("id", "name", "position", "is_default", "active")
    )
    custom_fields = (
        await IssueCustomField.all()
        .order_by("position", "id")
        .values(
            "id",
            "type",
            "name",
            "field_format",
            "possible_values",
            "default_value",
            "is_required",
            "is_filter",
            "searchable",
            "multiple",
            "visible",
            "position",
        )
    )
    workflows = (
        await IssueWorkflowTransition.all()
        .order_by("role_id", "tracker_id", "old_status_id", "new_status_id")
        .values(
            "id",
            "role_id",
            "tracker_id",
            "old_status_id",
            "new_status_id",
            "assignee_required",
            "author_allowed",
            "assignee_allowed",
        )
    )
    roles = await Role.all().order_by("id").values("id", "name")
    return {
        "trackers": [_json_row(row) for row in trackers],
        "statuses": [_json_row(row) for row in statuses],
        "priorities": [_json_row(row) for row in priorities],
        "custom_fields": [_json_row(row) for row in custom_fields],
        "workflows": [_json_row(row) for row in workflows],
        "roles": [_json_row(row) for row in roles],
        "field_formats": ISSUE_CUSTOM_FIELD_FORMAT_OPTIONS,
    }


async def _decorate_issue_rows(rows: list[dict]) -> list[dict]:
    tracker_map = await _rows_by_id(
        IssueTracker, {int(row["issue_tracker_id"]) for row in rows if row.get("issue_tracker_id")}, "name"
    )
    status_map = await _rows_by_id(
        IssueStatus, {int(row["issue_status_id"]) for row in rows if row.get("issue_status_id")}, "name", "is_closed"
    )
    priority_map = await _rows_by_id(
        IssuePriority, {int(row["issue_priority_id"]) for row in rows if row.get("issue_priority_id")}, "name"
    )
    user_ids = {int(value) for row in rows for value in (row.get("assigned_to_id"), row.get("submitter_id")) if value}
    users = await User.filter(id__in=list(user_ids)) if user_ids else []
    user_map = {int(user.id): _display_user(user) for user in users}
    custom_fields = await _visible_custom_fields()
    custom_values = await _custom_values_by_issue([int(row["id"]) for row in rows if row.get("id")], custom_fields)
    for row in rows:
        row["tracker_name"] = tracker_map.get(int(row.get("issue_tracker_id") or 0), {}).get("name") or row.get(
            "issue_type"
        )
        row["status_name"] = status_map.get(int(row.get("issue_status_id") or 0), {}).get("name")
        row["status_is_closed"] = bool(status_map.get(int(row.get("issue_status_id") or 0), {}).get("is_closed"))
        row["priority_name"] = priority_map.get(int(row.get("issue_priority_id") or 0), {}).get("name")
        row["assigned_to_name"] = user_map.get(int(row.get("assigned_to_id") or 0))
        row["submitter_name"] = user_map.get(int(row.get("submitter_id") or 0))
        row["custom_values"] = custom_values.get(int(row.get("id") or 0), {})
    return rows


def _can_write_issue(user: User, role_names: list[str]) -> bool:
    return bool(user.is_superuser or ISSUE_UPDATE_ROLES.intersection(role_names))


def _can_admin_issue_config(user: User, role_names: list[str]) -> bool:
    return bool(user.is_superuser or ROLE_ADMIN in role_names)


async def _require_issue_admin():
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not _can_admin_issue_config(user, role_names):
        return None, Fail(code=403, msg="您暂无权限维护Issue配置")
    return user, None


async def _save_issue_config(model, payload):
    data = payload.model_dump(exclude={"id"})
    if payload.id:
        obj = await model.filter(id=payload.id).first()
        if not obj:
            return None
        for key, value in data.items():
            setattr(obj, key, value)
        await obj.save()
        return obj
    return await model.create(**data)


def _can_view_all_issues(user: User, role_names: list[str]) -> bool:
    return bool(user.is_superuser or getattr(user, "username", "") == "admin" or ISSUE_VIEW_ALL_ROLES.intersection(role_names))


def _issue_assignee_q(
    user: User,
    role_names: list[str],
    ticket: Ticket | None = None,
    target_role_ids: set[int] | None = None,
) -> Q:
    if target_role_ids:
        return Q(roles__id__in=sorted(target_role_ids))
    if _can_view_all_issues(user, role_names):
        return Q()
    user_ids = {int(user.id)}
    assigned_to_id = _coerce_int(getattr(ticket, "assigned_to_id", None))
    if assigned_to_id:
        user_ids.add(assigned_to_id)
    return Q(id__in=sorted(user_ids))


async def _target_assignee_role_ids(status_id: int | None, tracker_id: int | None) -> set[int]:
    status_id = _coerce_int(status_id)
    tracker_id = _coerce_int(tracker_id)
    if not status_id or not tracker_id:
        return set()
    rows = await IssueWorkflowTransition.filter(
        old_status_id=status_id,
        tracker_id=tracker_id,
    ).values("role_id")
    return {int(row["role_id"]) for row in rows if row.get("role_id")}


async def _is_initial_issue_status(status_id: int | None) -> bool:
    status_id = _coerce_int(status_id)
    if not status_id:
        return False
    status = await IssueStatus.filter(id=status_id).first()
    return bool(status and (status.is_default or status.name == "新建"))


async def _is_field_verification_status(status_id: int | None) -> bool:
    status_id = _coerce_int(status_id)
    if not status_id:
        return False
    status = await IssueStatus.filter(id=status_id).first()
    return bool(status and status.name == "现场验证")


async def _issue_assignee_ids(
    user: User,
    role_names: list[str],
    ticket: Ticket | None = None,
    status_id: int | None = None,
    tracker_id: int | None = None,
) -> set[int]:
    target_role_ids = await _target_assignee_role_ids(status_id, tracker_id or getattr(ticket, "issue_tracker_id", None))
    rows = (
        await User.filter(
            _issue_assignee_q(user, role_names, ticket, target_role_ids),
            is_active=True,
        )
        .distinct()
        .values("id")
    )
    return {int(row["id"]) for row in rows}


async def _issue_visibility_q(user: User, role_names: list[str], scope: str | None) -> Q:
    if _can_view_all_issues(user, role_names):
        return Q(assigned_to_id=user.id) if scope == "mine" else Q()
    own_q = Q(submitter_id=user.id) | Q(assigned_to_id=user.id)
    if ROLE_TECH in role_names:
        related_submitter_ids = await _tech_related_submitter_ids(user.id)
        return own_q | Q(submitter_id__in=related_submitter_ids)
    return own_q


async def _can_access_ticket(ticket: Ticket, user: User, role_names: list[str]) -> bool:
    if _can_view_all_issues(user, role_names):
        return True
    if getattr(ticket, "assigned_to_id", None) == user.id:
        return True
    if ROLE_TECH in role_names:
        if ticket.submitter_id == user.id:
            return True
        return int(ticket.submitter_id or 0) in await _tech_related_submitter_ids(user.id)
    return ticket.submitter_id == user.id


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _ids_by_contains(model, text: Any, fields: tuple[str, ...]) -> list[int]:
    value = str(text or "").strip()
    if not value or not fields:
        return []
    q = Q(**{f"{fields[0]}__contains": value})
    for field in fields[1:]:
        q |= Q(**{f"{field}__contains": value})
    return [int(row["id"]) for row in await model.filter(q).values("id")]


async def _issue_name_filter_q(filters: dict[str, Any]) -> Q:
    q = Q()
    project_name = str(filters.get("issue_project_name") or "").strip()
    if project_name:
        project_ids = await _ids_by_contains(Project, project_name, ("project_name",))
        project_q = Q(company_name__contains=project_name)
        if project_ids:
            project_q |= Q(issue_project_id__in=project_ids)
        q &= project_q

    status_name = str(filters.get("issue_status_name") or "").strip()
    if status_name:
        status_ids = await _ids_by_contains(IssueStatus, status_name, ("name",))
        if status_ids:
            q &= Q(issue_status_id__in=status_ids)

    assignee_name = str(filters.get("assigned_to_name") or "").strip()
    if assignee_name:
        user_ids = await _ids_by_contains(User, assignee_name, ("alias", "username", "email"))
        if user_ids:
            q &= Q(assigned_to_id__in=user_ids)

    submitter_name = str(filters.get("submitter_name") or "").strip()
    if submitter_name:
        user_ids = await _ids_by_contains(User, submitter_name, ("alias", "username", "email"))
        if user_ids:
            q &= Q(submitter_id__in=user_ids)
    return q


def _apply_query_filters(q: Q, filters: dict[str, Any]) -> Q:
    title = str(filters.get("title") or "").strip()
    if title:
        q &= Q(title__contains=title)
    for field in ISSUE_QUERY_FILTER_FIELDS:
        value = _coerce_int(filters.get(field))
        if value is not None:
            q &= Q(**{field: value})
    return q


def _sort_order(sort_criteria: list[Any] | None) -> list[str]:
    result: list[str] = []
    for item in sort_criteria or []:
        if isinstance(item, dict):
            field = str(item.get("field") or "").strip()
            direction = str(item.get("direction") or "asc").strip().lower()
        elif isinstance(item, (list, tuple)) and item:
            field = str(item[0] or "").strip()
            direction = str(item[1] if len(item) > 1 else "asc").strip().lower()
        else:
            continue
        if field in ISSUE_SORT_FIELDS:
            result.append(f"-{field}" if direction == "desc" else field)
    return result or ["-id"]


async def _get_visible_query(query_id: int, user: User, role_names: list[str]):
    query = await IssueQuery.filter(id=query_id).first()
    if not query:
        return None
    if user.is_superuser or ROLE_ADMIN in role_names or query.visibility == "public" or query.user_id == user.id:
        return query
    return None


async def _get_issue_or_none(issue_id: int):
    return await _maybe_await(Ticket.filter(id=issue_id).first())


def _issue_not_found():
    return Fail(code=404, msg="Issue不存在")


async def _write_issue_journal(
    issue_id: int, user_id: int, notes: str | None, details: list[dict] | None = None
) -> None:
    journal = await IssueJournal.create(
        journalized_type="Issue",
        journalized_id=issue_id,
        user_id=user_id,
        notes=(notes or "").strip() or None,
        private_notes=False,
    )
    for detail in details or []:
        await IssueJournalDetail.create(journal_id=journal.id, **detail)


async def _issue_project_name(project_id: int | None) -> str | None:
    if not project_id:
        return None
    project = await Project.filter(id=project_id).first()
    return project.project_name if project else None


def _create_issue_payload(payload: IssueCreateIn, user: User) -> dict:
    allowed_fields = {
        "title",
        "description",
        "company_name",
        "contact_name",
        "email",
        "phone",
        "project_phase",
        "issue_type",
        "impact_scope",
        "category",
        "issue_project_id",
        "issue_tracker_id",
        "issue_priority_id",
        "issue_category_id",
        "issue_fixed_version_id",
        "parent_issue_id",
        "root_issue_id",
        "start_date",
        "due_date",
        "estimated_hours",
        "attachment_ids",
    }
    data = payload.model_dump(include=allowed_fields, exclude_none=True)
    data["assigned_to_id"] = user.id
    data["contact_name"] = (
        data.get("contact_name") or getattr(user, "alias", None) or getattr(user, "username", None) or "内部用户"
    )
    data["email"] = data.get("email") or getattr(user, "email", None) or f"user-{user.id}@local.invalid"
    data["phone"] = data.get("phone") or getattr(user, "phone", None) or "-"
    return data


def _validate_create_issue(payload: IssueCreateIn) -> None:
    for field in ("company_name", "project_phase", "issue_type", "impact_scope", "category", "title", "description"):
        if not _plain_text(getattr(payload, field, None)):
            raise HTTPException(status_code=400, detail=f"{ISSUE_FIELD_LABELS[field]}不能为空")
    if not _int_value(payload.issue_priority_id):
        raise HTTPException(status_code=400, detail=f"{ISSUE_FIELD_LABELS['issue_priority_id']}不能为空")


@router.get("/list", summary="Issue列表", dependencies=[DependAuth])
async def list_issues(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    issue_project_id: int | None = Query(None, description="项目ID"),
    issue_tracker_id: int | None = Query(None, description="Tracker ID"),
    issue_status_id: int | None = Query(None, description="状态ID"),
    issue_priority_id: int | None = Query(None, description="优先级ID"),
    assigned_to_id: int | None = Query(None, description="指派人ID"),
    submitter_id: int | None = Query(None, description="提交者ID"),
    issue_project_name: str | None = Query(None, description="项目名称"),
    issue_status_name: str | None = Query(None, description="状态"),
    assigned_to_name: str | None = Query(None, description="用户名称"),
    submitter_name: str | None = Query(None, description="提交者"),
    title: str | None = Query(None, description="标题"),
    custom_values: str | None = Query(None, description="自定义字段筛选JSON"),
    scope: str | None = Query(None, description="范围"),
    query_id: int | None = Query(None, description="保存查询ID"),
):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    saved_filters: dict[str, Any] = {}
    saved_sort: list[Any] = []
    if query_id:
        query = await _get_visible_query(query_id, user, role_names)
        if not query:
            return Fail(code=404, msg="查询不存在或无权访问")
        saved_filters = query.filters or {}
        saved_sort = query.sort_criteria or []

    title = title if title is not None else saved_filters.get("title")
    scope = scope if scope is not None else saved_filters.get("scope")
    q = await _issue_visibility_q(user, role_names, scope)
    issue_filters = {
        "issue_project_id": issue_project_id if issue_project_id is not None else saved_filters.get("issue_project_id"),
        "issue_tracker_id": issue_tracker_id if issue_tracker_id is not None else saved_filters.get("issue_tracker_id"),
        "issue_status_id": issue_status_id if issue_status_id is not None else saved_filters.get("issue_status_id"),
        "issue_priority_id": (
            issue_priority_id if issue_priority_id is not None else saved_filters.get("issue_priority_id")
        ),
        "assigned_to_id": assigned_to_id if assigned_to_id is not None else saved_filters.get("assigned_to_id"),
        "submitter_id": submitter_id if submitter_id is not None else saved_filters.get("submitter_id"),
        "issue_project_name": (
            issue_project_name if issue_project_name is not None else saved_filters.get("issue_project_name")
        ),
        "issue_status_name": (
            issue_status_name if issue_status_name is not None else saved_filters.get("issue_status_name")
        ),
        "assigned_to_name": assigned_to_name if assigned_to_name is not None else saved_filters.get("assigned_to_name"),
        "submitter_name": submitter_name if submitter_name is not None else saved_filters.get("submitter_name"),
    }
    for field, value in {key: issue_filters[key] for key in ISSUE_QUERY_FILTER_FIELDS}.items():
        int_value = _coerce_int(value)
        if int_value is not None:
            q &= Q(**{field: int_value})
    q &= await _issue_name_filter_q(issue_filters)
    if title:
        q &= Q(title__contains=title)
    raw_custom_filters = custom_values if custom_values is not None else saved_filters.get("custom_values")
    if raw_custom_filters:
        try:
            custom_filters = (
                json.loads(raw_custom_filters) if isinstance(raw_custom_filters, str) else raw_custom_filters
            )
        except ValueError:
            return Fail(code=400, msg="自定义字段筛选格式不正确")
        if isinstance(custom_filters, dict):
            custom_field_map = {int(field["id"]): field for field in await _visible_custom_fields()}
            for field_id, value in custom_filters.items():
                if _custom_value_is_empty(value):
                    continue
                custom_field_id = _coerce_int(field_id)
                field = custom_field_map.get(custom_field_id or 0)
                if custom_field_id is None or not field:
                    continue
                try:
                    query_value = _custom_value_to_text(field, value)
                except (TypeError, ValueError):
                    continue
                ticket_ids = await IssueCustomValue.filter(
                    customized_type="Issue",
                    custom_field_id=custom_field_id,
                    value__contains=query_value,
                ).values_list("customized_id", flat=True)
                q &= Q(id__in=[int(item) for item in ticket_ids])

    query = Ticket.filter(q)
    total = await query.count()
    rows = (
        await query.order_by(*_sort_order(saved_sort))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .values(*ISSUE_LIST_FIELDS)
    )
    return SuccessExtra(
        data=await _decorate_issue_rows([_json_row(row) for row in rows]),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/dashboard", summary="Issue数据展板", dependencies=[DependAuth])
async def issue_dashboard():
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    q = await _issue_visibility_q(user, role_names, None)
    rows = await Ticket.filter(q).values(
        "id",
        "title",
        "issue_status_id",
        "company_name",
        "created_at",
        "updated_at",
        "closed_at",
    )
    statuses = await IssueStatus.all().values("id", "name", "is_closed")
    return Success(data=_issue_dashboard_data([_json_row(row) for row in rows], [_json_row(row) for row in statuses]))


@router.get("/metadata", summary="Issue元数据", dependencies=[DependAuth])
async def get_issue_metadata():
    return Success(data=await _metadata_lists())


@router.get("/admin/config", summary="Issue配置", dependencies=[DependAuth])
async def get_issue_admin_config():
    _, error = await _require_issue_admin()
    if error:
        return error
    return Success(data=await _admin_metadata_lists())


@router.post("/admin/tracker/save", summary="保存Issue Tracker配置", dependencies=[DependAuth])
async def save_issue_tracker(payload: IssueAdminTrackerSaveIn):
    _, error = await _require_issue_admin()
    if error:
        return error
    default_status = await IssueStatus.filter(name="新建", active=True).first()
    if default_status:
        payload = payload.model_copy(update={"default_status_id": default_status.id})
    tracker = await _save_issue_config(IssueTracker, payload)
    if not tracker:
        return Fail(code=404, msg="Tracker不存在")
    return Success(msg="保存成功", data=await _model_dict(tracker))


@router.post("/admin/status/save", summary="保存Issue状态配置", dependencies=[DependAuth])
async def save_issue_status(payload: IssueAdminStatusSaveIn):
    _, error = await _require_issue_admin()
    if error:
        return error
    name = payload.name.strip()
    payload = payload.model_copy(
        update={
            "is_closed": name == "关闭",
            "is_default": name == "新建",
            "active": payload.active if payload.id else True,
        }
    )
    status = await _save_issue_config(IssueStatus, payload)
    if not status:
        return Fail(code=404, msg="状态不存在")
    if status.is_default:
        await IssueStatus.exclude(id=status.id).update(is_default=False)
    return Success(msg="保存成功", data=await _model_dict(status))


@router.post("/admin/priority/save", summary="保存Issue优先级配置", dependencies=[DependAuth])
async def save_issue_priority(payload: IssueAdminPrioritySaveIn):
    _, error = await _require_issue_admin()
    if error:
        return error
    if not payload.id:
        payload = payload.model_copy(update={"active": True})
    priority = await _save_issue_config(IssuePriority, payload)
    if not priority:
        return Fail(code=404, msg="优先级不存在")
    if priority.is_default:
        await IssuePriority.exclude(id=priority.id).update(is_default=False)
    return Success(msg="保存成功", data=await _model_dict(priority))


@router.post("/admin/workflow/save", summary="保存Issue工作流配置", dependencies=[DependAuth])
async def save_issue_workflow(payload: IssueAdminWorkflowSaveIn):
    _, error = await _require_issue_admin()
    if error:
        return error
    data = payload.model_dump(exclude={"id", "new_status_ids"})
    if "new_status_ids" in payload.model_fields_set:
        stale_workflows = IssueWorkflowTransition.filter(
            role_id=payload.role_id,
            tracker_id=payload.tracker_id,
            old_status_id=payload.old_status_id,
        )
        if payload.new_status_ids:
            stale_workflows = stale_workflows.exclude(new_status_id__in=payload.new_status_ids)
        await stale_workflows.delete()
        workflows = []
        for new_status_id in payload.new_status_ids:
            workflow, _ = await IssueWorkflowTransition.get_or_create(
                role_id=payload.role_id,
                tracker_id=payload.tracker_id,
                old_status_id=payload.old_status_id,
                new_status_id=new_status_id,
            )
            workflow.assignee_required = payload.assignee_required
            workflow.author_allowed = payload.author_allowed
            workflow.assignee_allowed = payload.assignee_allowed
            await workflow.save()
            workflows.append(await _model_dict(workflow))
        return Success(msg="保存成功", data=workflows)

    if payload.id:
        workflow = await IssueWorkflowTransition.filter(id=payload.id).first()
        if not workflow:
            return Fail(code=404, msg="工作流不存在")
        for key, value in data.items():
            setattr(workflow, key, value)
        await workflow.save()
    else:
        workflow, _ = await IssueWorkflowTransition.get_or_create(
            role_id=payload.role_id,
            tracker_id=payload.tracker_id,
            old_status_id=payload.old_status_id,
            new_status_id=payload.new_status_id,
            defaults={
                "assignee_required": payload.assignee_required,
                "author_allowed": payload.author_allowed,
                "assignee_allowed": payload.assignee_allowed,
            },
        )
        workflow.assignee_required = payload.assignee_required
        workflow.author_allowed = payload.author_allowed
        workflow.assignee_allowed = payload.assignee_allowed
        await workflow.save()
    return Success(msg="保存成功", data=await _model_dict(workflow))


@router.post("/admin/custom-field/save", summary="保存Issue自定义字段配置", dependencies=[DependAuth])
async def save_issue_custom_field(payload: IssueAdminCustomFieldSaveIn):
    _, error = await _require_issue_admin()
    if error:
        return error
    custom_field = await _save_issue_config(IssueCustomField, payload)
    if not custom_field:
        return Fail(code=404, msg="自定义字段不存在")
    return Success(msg="保存成功", data=await _model_dict(custom_field))


@router.post("/create", summary="新建Issue", dependencies=[DependAuth])
async def create_issue(payload: IssueCreateIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not (user.is_superuser or ISSUE_CREATE_ROLES.intersection(role_names)):
        return Fail(code=403, msg="您暂无权限新建Issue")
    _validate_create_issue(payload)
    body = _create_issue_payload(payload, user)
    if not payload.company_name and body.get("issue_project_id"):
        body["company_name"] = await _issue_project_name(body.get("issue_project_id")) or "内部"
    ticket = await ticket_controller.create_ticket(submitter_id=user.id, payload=body)
    ticket = await issue_default_service.apply_defaults(ticket)
    await _save_issue_custom_values(ticket.id, payload.custom_values, validate_required=True)
    if payload.notes:
        await _write_issue_journal(ticket.id, user.id, payload.notes)
    decorated = await _maybe_await(_decorate_issue_rows([await _model_dict(ticket)]))
    return Success(msg="创建成功", data=decorated[0])


@router.get("/get", summary="Issue详情", dependencies=[DependAuth])
async def get_issue(issue_id: int = Query(..., description="Issue ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    ticket = await _get_issue_or_none(issue_id)
    if not ticket:
        return _issue_not_found()
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限查看该Issue")

    data = (await _decorate_issue_rows([await _model_dict(ticket)]))[0]
    attachment_rows = await TicketAttachment.filter(ticket_id=issue_id).order_by("id")
    data["attachments"] = []
    for item in attachment_rows:
        row = await _model_dict(item)
        row["file_exists"] = _ticket_attachment_file_exists(item)
        data["attachments"].append(row)
    data["attachment_count"] = len(data["attachments"])
    can_view_private = bool(
        user.is_superuser
        or {ROLE_ADMIN, ROLE_CUSTOMER_SERVICE, ROLE_TECH, ROLE_PRODUCT, ROLE_TEST, ROLE_RD}.intersection(role_names)
    )
    journal_query = IssueJournal.filter(journalized_type="Issue", journalized_id=issue_id)
    if not can_view_private:
        journal_query = journal_query.filter(private_notes=False)
    journals = await journal_query.order_by("id")
    journal_ids = [item.id for item in journals]
    details = await IssueJournalDetail.filter(journal_id__in=journal_ids).order_by("id") if journal_ids else []
    journal_user_ids = {int(item.user_id) for item in journals if item.user_id}
    history_user_ids = journal_user_ids | _detail_ids(details, "assigned_to_id")
    users = await User.filter(id__in=list(history_user_ids)) if history_user_ids else []
    user_map = {int(item.id): _display_user(item) for item in users}
    details_by_journal: dict[int, list[dict]] = {}
    for detail in details:
        details_by_journal.setdefault(detail.journal_id, []).append(await _model_dict(detail))
    data["history_maps"] = {
        "trackers": await _rows_by_id(IssueTracker, _detail_ids(details, "issue_tracker_id"), "name"),
        "statuses": await _rows_by_id(IssueStatus, _detail_ids(details, "issue_status_id"), "name"),
        "priorities": await _rows_by_id(IssuePriority, _detail_ids(details, "issue_priority_id"), "name"),
        "users": user_map,
    }
    data["journals"] = [
        {
            **await _model_dict(journal),
            "user_name": user_map.get(int(journal.user_id)),
            "details": details_by_journal.get(journal.id, []),
        }
        for journal in journals
    ]
    return Success(data=data)


@router.get("/status-options", summary="Issue可流转状态", dependencies=[DependAuth])
async def get_issue_status_options(issue_id: int = Query(..., description="Issue ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    ticket = await _get_issue_or_none(issue_id)
    if not ticket:
        return _issue_not_found()
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限查看该Issue")

    current_status_id = int(ticket.issue_status_id or 0)
    if user.is_superuser or ROLE_ADMIN in role_names:
        status_ids = [int(row["id"]) for row in await IssueStatus.filter(active=True).values("id")]
    elif current_status_id and ticket.issue_tracker_id:
        status_ids = await issue_workflow_service.allowed_status_ids(
            role_ids=await _role_ids(user),
            tracker_id=int(ticket.issue_tracker_id),
            status_id=current_status_id,
        )
    else:
        status_ids = []
    visible_ids = sorted({current_status_id, *status_ids} - {0})
    rows = await IssueStatus.filter(id__in=visible_ids).order_by("position", "id").values("id", "name", "is_closed")
    return Success(data={"current_status_id": current_status_id or None, "statuses": [_json_row(row) for row in rows]})


@router.get("/assignees", summary="Issue可指派人", dependencies=[DependAuth])
async def get_issue_assignees(
    issue_id: int | None = Query(None, description="Issue ID"),
    status_id: int | None = Query(None, description="目标状态ID"),
    tracker_id: int | None = Query(None, description="目标跟踪ID"),
):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    ticket = await _get_issue_or_none(issue_id) if issue_id else None
    if issue_id and not ticket:
        return _issue_not_found()
    if ticket and not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限查看该Issue")
    if ticket and await _is_initial_issue_status(status_id):
        submitter_id = _coerce_int(getattr(ticket, "submitter_id", None))
        rows = await User.filter(id__in=[submitter_id] if submitter_id else [], is_active=True).values(
            "id", "username", "alias", "email"
        )
        return Success(data=[_json_row(row) for row in rows])
    if ticket and await _is_field_verification_status(status_id):
        submitter_id = _coerce_int(getattr(ticket, "submitter_id", None))
        tech_role = await Role.filter(name=ROLE_TECH).first()
        q = Q(id__in=[submitter_id] if submitter_id else [])
        if tech_role:
            q |= Q(roles__id=tech_role.id)
        rows = (
            await User.filter(q, is_active=True)
            .distinct()
            .order_by("id")
            .values("id", "username", "alias", "email")
        )
        return Success(data=[_json_row(row) for row in rows])
    target_role_ids = await _target_assignee_role_ids(
        status_id,
        tracker_id or getattr(ticket, "issue_tracker_id", None),
    )
    rows = (
        await User.filter(
            _issue_assignee_q(user, role_names, ticket, target_role_ids),
            is_active=True,
        )
        .distinct()
        .order_by("id")
        .values("id", "username", "alias", "email")
    )
    return Success(data=[_json_row(row) for row in rows])


@router.post("/update", summary="更新Issue", dependencies=[DependAuth])
async def update_issue(payload: IssueUpdateIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not user.is_superuser and not ISSUE_UPDATE_ROLES.intersection(role_names):
        return Fail(code=403, msg="您暂无权限操作该Issue")
    ticket = await _get_issue_or_none(payload.issue_id)
    if not ticket:
        return _issue_not_found()
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限操作该Issue")
    assigned_to_id = _coerce_int((payload.changes or {}).get("assigned_to_id"))
    target_status_id = _coerce_int((payload.changes or {}).get("issue_status_id")) or _coerce_int(
        getattr(ticket, "issue_status_id", None)
    )
    target_tracker_id = _coerce_int((payload.changes or {}).get("issue_tracker_id")) or _coerce_int(
        getattr(ticket, "issue_tracker_id", None)
    )
    if assigned_to_id and assigned_to_id not in await _issue_assignee_ids(
        user, role_names, ticket, target_status_id, target_tracker_id
    ):
        return Fail(code=403, msg="您暂无权限指派给该用户")

    issue = await issue_update_service.update_issue(
        issue_id=payload.issue_id,
        user_id=user.id,
        role_ids=await _role_ids(user),
        changes=payload.changes,
        notes=payload.notes,
        private_notes=payload.private_notes,
        bypass_workflow=bool(user.is_superuser or ROLE_ADMIN in role_names),
    )
    custom_details = (
        await _save_issue_custom_values(payload.issue_id, payload.custom_values) if payload.custom_values else []
    )
    if custom_details:
        await _write_issue_journal(payload.issue_id, user.id, None, custom_details)
    decorated = await _maybe_await(_decorate_issue_rows([await _model_dict(issue)]))
    return Success(msg="更新成功", data=decorated[0])


@router.get("/watchers", summary="Issue关注者", dependencies=[DependAuth])
async def list_issue_watchers(issue_id: int = Query(..., description="Issue ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    ticket = await _get_issue_or_none(issue_id)
    if not ticket:
        return _issue_not_found()
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限查看该Issue")
    watchers = await IssueWatcher.filter(watchable_type="Issue", watchable_id=issue_id).order_by("id")
    user_ids = [int(item.user_id) for item in watchers if item.user_id]
    users = await User.filter(id__in=user_ids) if user_ids else []
    user_map = {int(item.id): _display_user(item) for item in users}
    data = [await _model_dict(item) for item in watchers]
    for item in data:
        item["user_name"] = user_map.get(int(item.get("user_id") or 0))
    return Success(data=data)


@router.post("/watcher/add", summary="添加Issue关注者", dependencies=[DependAuth])
async def add_issue_watcher(payload: IssueWatcherIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    ticket = await _get_issue_or_none(payload.issue_id)
    if not ticket:
        return _issue_not_found()
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限操作该Issue")
    target_user_id = payload.user_id or user.id
    if target_user_id != user.id and not _can_write_issue(user, role_names):
        return Fail(code=403, msg="您暂无权限为他人添加关注")
    watcher, _ = await IssueWatcher.get_or_create(
        watchable_type="Issue",
        watchable_id=payload.issue_id,
        user_id=target_user_id,
    )
    return Success(msg="关注成功", data=await _model_dict(watcher))


@router.post("/watcher/delete", summary="删除Issue关注者", dependencies=[DependAuth])
async def delete_issue_watcher(payload: IssueWatcherIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    ticket = await _get_issue_or_none(payload.issue_id)
    if not ticket:
        return _issue_not_found()
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限操作该Issue")
    target_user_id = payload.user_id or user.id
    if target_user_id != user.id and not _can_write_issue(user, role_names):
        return Fail(code=403, msg="您暂无权限删除他人关注")
    await IssueWatcher.filter(watchable_type="Issue", watchable_id=payload.issue_id, user_id=target_user_id).delete()
    return Success(msg="取消关注成功")


@router.get("/relations", summary="Issue关联列表", dependencies=[DependAuth])
async def list_issue_relations(issue_id: int = Query(..., description="Issue ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    ticket = await _get_issue_or_none(issue_id)
    if not ticket:
        return _issue_not_found()
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限查看该Issue")
    relations = await IssueRelation.filter(Q(issue_from_id=issue_id) | Q(issue_to_id=issue_id)).order_by("id")
    related_ids = {
        int(item.issue_to_id if item.issue_from_id == issue_id else item.issue_from_id) for item in relations
    }
    related = await _rows_by_id(Ticket, related_ids, "ticket_no", "title", "issue_status_id")
    data = []
    for item in relations:
        row = await _model_dict(item)
        other_id = int(item.issue_to_id if item.issue_from_id == issue_id else item.issue_from_id)
        row["related_issue"] = related.get(other_id) or {"id": other_id}
        data.append(row)
    return Success(data=data)


@router.post("/relation/create", summary="创建Issue关联", dependencies=[DependAuth])
async def create_issue_relation(payload: IssueRelationCreateIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not _can_write_issue(user, role_names):
        return Fail(code=403, msg="您暂无权限操作该Issue")
    if payload.issue_id == payload.related_issue_id:
        return Fail(code=400, msg="不能关联自身")
    for issue_id in [payload.issue_id, payload.related_issue_id]:
        ticket = await _get_issue_or_none(issue_id)
        if not ticket:
            return _issue_not_found()
        if not await _can_access_ticket(ticket, user, role_names):
            return Fail(code=403, msg="您暂无权限操作关联Issue")
    relation, created = await IssueRelation.get_or_create(
        issue_from_id=payload.issue_id,
        issue_to_id=payload.related_issue_id,
        relation_type=payload.relation_type,
        defaults={"delay": payload.delay},
    )
    if not created and relation.delay != payload.delay:
        relation.delay = payload.delay
        await relation.save()
    await _write_issue_journal(
        payload.issue_id,
        user.id,
        f"关联Issue #{payload.related_issue_id}",
        [
            {
                "property": "relation",
                "prop_key": str(payload.relation_type),
                "old_value": None,
                "value": str(payload.related_issue_id),
            }
        ],
    )
    return Success(msg="关联成功", data=await _model_dict(relation))


@router.delete("/relation/delete", summary="删除Issue关联", dependencies=[DependAuth])
async def delete_issue_relation(relation_id: int = Query(..., description="关联ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not _can_write_issue(user, role_names):
        return Fail(code=403, msg="您暂无权限操作该Issue")
    relation = await IssueRelation.filter(id=relation_id).first()
    if not relation:
        return Fail(code=404, msg="关联不存在")
    ticket = await _get_issue_or_none(relation.issue_from_id)
    if not ticket:
        return _issue_not_found()
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限操作该Issue")
    await relation.delete()
    await _write_issue_journal(
        relation.issue_from_id,
        user.id,
        f"删除Issue关联 #{relation.issue_to_id}",
        [
            {
                "property": "relation",
                "prop_key": str(relation.relation_type),
                "old_value": str(relation.issue_to_id),
                "value": None,
            }
        ],
    )
    return Success(msg="删除成功")


@router.get("/time-entries", summary="Issue耗时列表", dependencies=[DependAuth])
async def list_issue_time_entries(issue_id: int = Query(..., description="Issue ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    ticket = await _get_issue_or_none(issue_id)
    if not ticket:
        return _issue_not_found()
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限查看该Issue")
    rows = await IssueTimeEntry.filter(issue_id=issue_id).order_by("-spent_on", "-id")
    user_ids = [int(item.user_id) for item in rows if item.user_id]
    users = await User.filter(id__in=user_ids) if user_ids else []
    user_map = {int(item.id): _display_user(item) for item in users}
    data = [await _model_dict(item) for item in rows]
    for item in data:
        item["user_name"] = user_map.get(int(item.get("user_id") or 0))
    return Success(data=data)


@router.post("/time-entry/create", summary="登记Issue耗时", dependencies=[DependAuth])
async def create_issue_time_entry(payload: IssueTimeEntryCreateIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not _can_write_issue(user, role_names):
        return Fail(code=403, msg="您暂无权限操作该Issue")
    ticket = await _get_issue_or_none(payload.issue_id)
    if not ticket:
        return _issue_not_found()
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限操作该Issue")
    entry = await IssueTimeEntry.create(
        project_id=ticket.issue_project_id or 0,
        issue_id=payload.issue_id,
        user_id=user.id,
        activity_id=payload.activity_id,
        hours=payload.hours,
        comments=payload.comments,
        spent_on=payload.spent_on or date.today(),
    )
    await _write_issue_journal(
        payload.issue_id,
        user.id,
        payload.comments or f"登记耗时 {payload.hours}h",
        [{"property": "time_entry", "prop_key": "hours", "old_value": None, "value": str(payload.hours)}],
    )
    return Success(msg="登记成功", data=await _model_dict(entry))


@router.delete("/time-entry/delete", summary="删除Issue耗时", dependencies=[DependAuth])
async def delete_issue_time_entry(time_entry_id: int = Query(..., description="耗时ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    entry = await IssueTimeEntry.filter(id=time_entry_id).first()
    if not entry:
        return Fail(code=404, msg="耗时不存在")
    ticket = await _get_issue_or_none(entry.issue_id)
    if not ticket:
        return _issue_not_found()
    if entry.user_id != user.id and not _can_write_issue(user, role_names):
        return Fail(code=403, msg="您暂无权限删除该耗时")
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限操作该Issue")
    await entry.delete()
    await _write_issue_journal(
        entry.issue_id,
        user.id,
        f"删除耗时 {entry.hours}h",
        [{"property": "time_entry", "prop_key": "hours", "old_value": str(entry.hours), "value": None}],
    )
    return Success(msg="删除成功")


@router.get("/queries", summary="Issue保存查询", dependencies=[DependAuth])
async def list_issue_queries():
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    q = Q()
    if not (user.is_superuser or ROLE_ADMIN in role_names):
        q = Q(visibility="public") | Q(user_id=user.id)
    rows = await IssueQuery.filter(q).order_by("visibility", "name")
    return Success(data=[await _model_dict(item) for item in rows])


@router.post("/query/create", summary="创建Issue查询", dependencies=[DependAuth])
async def create_issue_query(payload: IssueQueryCreateIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if payload.visibility == "public" and not (user.is_superuser or ROLE_ADMIN in role_names):
        return Fail(code=403, msg="仅管理员可创建公共查询")
    query = await IssueQuery.create(
        name=payload.name,
        user_id=None if payload.visibility == "public" else user.id,
        project_id=payload.project_id,
        visibility=payload.visibility,
        filters=payload.filters,
        columns=payload.columns,
        sort_criteria=payload.sort_criteria,
    )
    return Success(msg="保存成功", data=await _model_dict(query))


@router.post("/query/update", summary="更新Issue查询", dependencies=[DependAuth])
async def update_issue_query(payload: IssueQueryUpdateIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    query = await _get_visible_query(payload.query_id, user, role_names)
    if not query:
        return Fail(code=404, msg="查询不存在或无权访问")
    if query.visibility == "public" and not (user.is_superuser or ROLE_ADMIN in role_names):
        return Fail(code=403, msg="仅管理员可更新公共查询")
    if payload.visibility == "public" and not (user.is_superuser or ROLE_ADMIN in role_names):
        return Fail(code=403, msg="仅管理员可设为公共查询")
    query.name = payload.name
    query.user_id = None if payload.visibility == "public" else user.id
    query.project_id = payload.project_id
    query.visibility = payload.visibility
    query.filters = payload.filters
    query.columns = payload.columns
    query.sort_criteria = payload.sort_criteria
    await query.save()
    return Success(msg="更新成功", data=await _model_dict(query))


@router.delete("/query/delete", summary="删除Issue查询", dependencies=[DependAuth])
async def delete_issue_query(query_id: int = Query(..., description="查询ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    query = await _get_visible_query(query_id, user, role_names)
    if not query:
        return Fail(code=404, msg="查询不存在或无权访问")
    if query.visibility == "public" and not (user.is_superuser or ROLE_ADMIN in role_names):
        return Fail(code=403, msg="仅管理员可删除公共查询")
    await query.delete()
    return Success(msg="删除成功")
