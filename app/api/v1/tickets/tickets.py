import asyncio
from datetime import datetime
import io
import json
import re
from time import perf_counter

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from tortoise.expressions import Q

from app.log import logger
from app.controllers.partner import partner_controller
from app.controllers.system_setting import system_setting_controller
from app.controllers.ticket import ticket_controller
from app.controllers.user import user_controller
from app.core.redis_client import execute_redis
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import Dept, DeptClosure, Ticket, TicketActionLog, TicketAttachment, User
from app.models.enums import ROLE_ADMIN, ROLE_AGENT, ROLE_CHANNEL, ROLE_CUSTOMER_SERVICE, ROLE_TECH, ROLE_USER, TicketActionType, TicketStatus
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.tickets import TicketAssignTechIn, TicketCloseIn, TicketCreate, TicketFieldVerificationIn, TicketRedmineSyncIn, TicketResubmitIn, TicketReviewIn, TicketTechActionIn, TicketUpdateIn
from app.services.human_challenge import human_challenge_service
from app.services.redmine_sync_service import redmine_sync_service
from app.settings import settings
from app.utils.company_name import company_name_search_q
from app.utils.http_headers import build_download_content_disposition
from app.utils.request import get_client_ip

router = APIRouter()
TICKET_EXPORT_MAX_ROWS = 5000


async def _get_current_user() -> User:
    user_id = CTX_USER_ID.get()
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="当前用户不存在")
    return user


async def _get_user_role_names(user: User) -> list[str]:
    roles = await user.roles
    return [role.name for role in roles]


async def _tech_related_submitter_ids(tech_id: int) -> list[int]:
    cache_key = f"ticket:tech_related_submitters:{tech_id}:v1"
    try:
        cached = await execute_redis("get", cache_key)
        if cached:
            return [int(item) for item in json.loads(cached)]
    except Exception as exc:
        logger.warning("[ticket.scope] cache_read_failed tech_id={} error={}", tech_id, str(exc))

    # ponytail: department table scan; split to a relation table if department count makes this hot.
    depts = await Dept.filter(is_deleted=False).all()
    dept_ids = [dept.id for dept in depts if int(tech_id) in {int(item or 0) for item in (dept.tech_ids or [])}]
    if not dept_ids:
        return []
    descendant_ids = await DeptClosure.filter(ancestor__in=dept_ids).values_list("descendant", flat=True)
    visible_dept_ids = set(dept_ids) | {int(item) for item in descendant_ids}
    submitter_ids = [int(item) for item in await User.filter(dept_id__in=visible_dept_ids).values_list("id", flat=True)]
    try:
        await execute_redis("setex", cache_key, 300, json.dumps(submitter_ids, ensure_ascii=False))
    except Exception as exc:
        logger.warning("[ticket.scope] cache_write_failed tech_id={} error={}", tech_id, str(exc))
    return submitter_ids


def _can_view_all_tickets(user: User, role_names: list[str]) -> bool:
    return bool(
        user.is_superuser
        or getattr(user, "username", "") == "admin"
        or {ROLE_ADMIN, ROLE_CUSTOMER_SERVICE}.intersection(role_names)
    )


async def _can_access_ticket(ticket: Ticket, user: User, role_names: list[str]) -> bool:
    if _can_view_all_tickets(user, role_names):
        return True
    if ROLE_TECH in role_names:
        if ticket.submitter_id == user.id or ticket.tech_id == user.id:
            return True
        return ticket.submitter_id in await _tech_related_submitter_ids(user.id)
    return ticket.submitter_id == user.id


def _build_ticket_search_sync(
    *,
    user: User,
    role_names: list[str],
    related_submitter_ids: list[int] | None = None,
    scope: str | None = None,
    status: TicketStatus | None = None,
    exclude_status: TicketStatus | None = None,
    project_phase: str | None = None,
    issue_type: str | None = None,
    impact_scope: str | None = None,
    category: str | None = None,
    root_cause: str | None = None,
    company_name: str | None = None,
    title: str | None = None,
    created_start: datetime | None = None,
    created_end: datetime | None = None,
    finished_start: datetime | None = None,
    finished_end: datetime | None = None,
) -> Q:
    q = Q()
    if status:
        q &= Q(status=status)
    elif exclude_status:
        q &= ~Q(status=exclude_status)
    if project_phase:
        q &= Q(project_phase=project_phase)
    if issue_type:
        q &= Q(issue_type=issue_type)
    if impact_scope:
        q &= Q(impact_scope=impact_scope)
    if category:
        q &= Q(category=category)
    if root_cause:
        q &= Q(root_cause=root_cause)
    if company_name:
        q &= company_name_search_q(company_name)
    if title:
        q &= Q(title__contains=title)
    if created_start:
        q &= Q(created_at__gte=created_start)
    if created_end:
        q &= Q(created_at__lt=created_end)
    if finished_start:
        q &= Q(finished_at__gte=finished_start)
    if finished_end:
        q &= Q(finished_at__lt=finished_end)

    if _can_view_all_tickets(user, role_names):
        return q
    if ROLE_TECH in role_names:
        tech_q = Q(submitter_id=user.id) | Q(submitter_id__in=related_submitter_ids or [])
        if scope != "mine":
            tech_q |= Q(tech_id=user.id)
        q &= tech_q
    else:
        q &= Q(submitter_id=user.id)
    return q


async def _build_ticket_search(**kwargs) -> Q:
    user = kwargs["user"]
    role_names = kwargs["role_names"]
    related_submitter_ids = await _tech_related_submitter_ids(user.id) if ROLE_TECH in role_names else []
    return _build_ticket_search_sync(**kwargs, related_submitter_ids=related_submitter_ids)


def _clean_export_text(value) -> str:
    text = str(value or "")
    image_sources = re.findall(r"<\s*img\b[^>]*\bsrc\s*=\s*([\"'])(.*?)\1", text, flags=re.I | re.S)
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    text = re.sub(r"</\s*(p|div|li|tr|h[1-6])\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    sources = [src.strip() for _, src in image_sources if src and src.strip()]
    if sources:
        text = "\n".join([item for item in [text, "图片：" + "；".join(sources)] if item])
    return text


def _resolve_ticket_issue_type(payload_issue_type: str | None, issue_types: list[str]) -> str:
    issue_type = str(payload_issue_type or "").strip()
    if not issue_type:
        issue_type = issue_types[0] if issue_types else "现网问题"
    return issue_type


def _resolve_ticket_impact_scope(payload_impact_scope: str | None, impact_scopes: list[str]) -> str:
    impact_scope = str(payload_impact_scope or "").strip()
    if not impact_scope:
        impact_scope = impact_scopes[0] if impact_scopes else "全部"
    return impact_scope


@router.post("/upload", summary="上传工单附件", dependencies=[DependAuth])
async def upload_ticket_attachment(file: UploadFile = File(...)):
    user_id = CTX_USER_ID.get()
    logger.info("[api.ticket.upload] request user_id={} filename={}", user_id, file.filename)
    attachment = await ticket_controller.upload_attachment(uploader_id=user_id, file=file)
    logger.info("[api.ticket.upload] success user_id={} attachment_id={} path={}", user_id, attachment.id, attachment.file_path)
    return Success(data=await attachment.to_dict())


@router.post("/create", summary="提交工单", dependencies=[DependAuth])
async def create_ticket(payload: TicketCreate, request: Request):
    user = await _get_current_user()
    logger.info("[api.ticket.create] request user_id={}", user.id)
    role_names = await _get_user_role_names(user)
    if not user.is_superuser and not any(
        role in role_names for role in [ROLE_USER, ROLE_CHANNEL, ROLE_AGENT, ROLE_TECH, ROLE_ADMIN]
    ):
        return Fail(code=403, msg="您当前账号暂无提交工单权限，请联系管理员")

    pending = await partner_controller.has_pending_registration(
        email=user.email,
        phone=user.phone,
        username=user.username,
        hardware_id=user.hardware_id,
    )
    if pending:
        return Fail(code=403, msg="您的注册申请仍在审核中，暂不可提交工单")

    config = await system_setting_controller.get_full_dict()
    valid, challenge_error = await human_challenge_service.verify(
        captcha_id=payload.captcha_id,
        captcha_code=payload.captcha_code,
        turnstile_token=payload.turnstile_token,
        client_ip=get_client_ip(request),
        config=config,
        log_context="api.ticket.create",
    )
    if not valid:
        logger.warning("[api.ticket.create] captcha_invalid user_id={}", user.id)
        return Fail(code=400, msg=challenge_error)

    project_phases = config.get("ticket_project_phases") or []
    issue_types = config.get("ticket_issue_types") or []
    impact_scopes = config.get("ticket_impact_scopes") or []
    categories = config.get("ticket_categories") or []
    issue_type = _resolve_ticket_issue_type(payload.issue_type, issue_types)
    impact_scope = _resolve_ticket_impact_scope(payload.impact_scope, impact_scopes)
    if project_phases and payload.project_phase not in project_phases:
        return Fail(code=400, msg="项目阶段已更新，请刷新页面后重新选择")
    if issue_types and issue_type not in issue_types:
        return Fail(code=400, msg="跟踪已更新，请刷新页面后重新选择")
    if impact_scopes and impact_scope not in impact_scopes:
        return Fail(code=400, msg="影响范围已更新，请刷新页面后重新选择")
    if categories and payload.category not in categories:
        return Fail(code=400, msg="问题分类已更新，请刷新页面后重新选择")
    version_error = redmine_sync_service.ticket_description_version_error(payload.description)
    if version_error:
        return Fail(code=400, msg=version_error)

    body = payload.model_dump(exclude={"captcha_id", "captcha_code", "turnstile_token"})
    body["issue_type"] = issue_type
    body["impact_scope"] = impact_scope
    ticket = await ticket_controller.create_ticket_with_optional_auto_review(submitter_id=user.id, payload=body)
    logger.info("[api.ticket.create] success user_id={} ticket_id={}", user.id, ticket.id)
    return Success(msg="提交成功", data=await ticket.to_dict())


@router.get("/prefill", summary="获取工单预填信息", dependencies=[DependAuth])
async def get_ticket_prefill():
    user = await _get_current_user()
    cache_key = f"ticket:prefill:user:{user.id}:v1"
    try:
        cached = await execute_redis("get", cache_key)
        if cached:
            return Success(data=json.loads(cached))
    except Exception as exc:
        logger.warning("[api.ticket.prefill] cache_read_failed key={} error={}", cache_key, str(exc))

    data = {
        "company_name": user.company_name or "",
        "contact_name": user.alias or user.username,
        "email": user.email or "",
        "phone": user.phone or "",
    }
    try:
        await execute_redis("setex", cache_key, 600, json.dumps(data, ensure_ascii=False))
    except Exception as exc:
        logger.warning("[api.ticket.prefill] cache_write_failed key={} error={}", cache_key, str(exc))
    return Success(data=data)


@router.get("/list", summary="工单列表", dependencies=[DependAuth])
async def list_ticket(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    status: TicketStatus | None = Query(None, description="状态"),
    exclude_status: TicketStatus | None = Query(None, description="排除状态"),
    project_phase: str | None = Query(None, description="项目阶段"),
    issue_type: str | None = Query(None, description="跟踪"),
    impact_scope: str | None = Query(None, description="影响范围"),
    category: str | None = Query(None, description="分类"),
    root_cause: str | None = Query(None, description="根因"),
    company_name: str | None = Query(None, description="项目名称"),
    title: str | None = Query(None, description="标题"),
    created_start: datetime | None = Query(None, description="创建开始时间"),
    created_end: datetime | None = Query(None, description="创建结束时间"),
    finished_start: datetime | None = Query(None, description="完成开始时间"),
    finished_end: datetime | None = Query(None, description="完成结束时间"),
    scope: str | None = Query(None, description="范围"),
):
    start_at = perf_counter()
    user = await _get_current_user()
    auth_cost_ms = int((perf_counter() - start_at) * 1000)

    filter_start_at = perf_counter()
    role_names = await _get_user_role_names(user)
    q = await _build_ticket_search(
        user=user,
        role_names=role_names,
        status=status,
        exclude_status=exclude_status,
        project_phase=project_phase,
        issue_type=issue_type,
        impact_scope=impact_scope,
        category=category,
        root_cause=root_cause,
        company_name=company_name,
        title=title,
        created_start=created_start,
        created_end=created_end,
        finished_start=finished_start,
        finished_end=finished_end,
        scope=scope,
    )
    filter_cost_ms = int((perf_counter() - filter_start_at) * 1000)

    query_start_at = perf_counter()
    summary_q = await _build_ticket_search(
        user=user,
        role_names=role_names,
        status=None,
        exclude_status=None,
        project_phase=project_phase,
        issue_type=issue_type,
        impact_scope=impact_scope,
        category=category,
        root_cause=root_cause,
        company_name=company_name,
        title=title,
        created_start=created_start,
        created_end=created_end,
        finished_start=finished_start,
        finished_end=finished_end,
        scope=scope,
    )
    (total, rows), status_summary = await asyncio.gather(
        ticket_controller.list_tickets(page=page, page_size=page_size, search=q),
        ticket_controller.status_summary(search=summary_q),
    )
    query_cost_ms = int((perf_counter() - query_start_at) * 1000)
    total_cost_ms = int((perf_counter() - start_at) * 1000)
    logger.info(
        "[api.ticket.list] user_id={} page={} page_size={} total={} rows={} auth_ms={} filter_ms={} query_ms={} total_ms={}",
        user.id,
        page,
        page_size,
        total,
        len(rows),
        auth_cost_ms,
        filter_cost_ms,
        query_cost_ms,
        total_cost_ms,
    )
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size, status_summary=status_summary)


@router.get("/export", summary="导出工单", dependencies=[DependAuth])
async def export_tickets(
    status: TicketStatus | None = Query(None, description="状态"),
    project_phase: str | None = Query(None, description="项目阶段"),
    issue_type: str | None = Query(None, description="跟踪"),
    impact_scope: str | None = Query(None, description="影响范围"),
    category: str | None = Query(None, description="分类"),
    root_cause: str | None = Query(None, description="根因"),
    company_name: str | None = Query(None, description="项目名称"),
    title: str | None = Query(None, description="标题"),
    created_start: datetime | None = Query(None, description="创建开始时间"),
    created_end: datetime | None = Query(None, description="创建结束时间"),
    finished_start: datetime | None = Query(None, description="完成开始时间"),
    finished_end: datetime | None = Query(None, description="完成结束时间"),
    scope: str | None = Query(None, description="范围"),
):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    q = await _build_ticket_search(
        user=user,
        role_names=role_names,
        status=status,
        project_phase=project_phase,
        issue_type=issue_type,
        impact_scope=impact_scope,
        category=category,
        root_cause=root_cause,
        company_name=company_name,
        title=title,
        created_start=created_start,
        created_end=created_end,
        finished_start=finished_start,
        finished_end=finished_end,
        scope=scope,
    )
    total = await Ticket.filter(q).count()
    if total > TICKET_EXPORT_MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"导出数据量过大，当前 {total} 条，请缩小筛选条件到 {TICKET_EXPORT_MAX_ROWS} 条以内",
        )

    tickets = await Ticket.filter(q).order_by("-id").limit(TICKET_EXPORT_MAX_ROWS)
    ticket_ids = [item.id for item in tickets]
    attachments, actions = [], []
    if ticket_ids:
        attachments, actions = await asyncio.gather(
            TicketAttachment.filter(ticket_id__in=ticket_ids).order_by("ticket_id", "id"),
            TicketActionLog.filter(ticket_id__in=ticket_ids).order_by("ticket_id", "id"),
        )

    attachment_map: dict[int, list] = {}
    for item in attachments:
        attachment_map.setdefault(item.ticket_id, []).append(item)
    action_map: dict[int, list] = {}
    for item in actions:
        action_map.setdefault(item.ticket_id, []).append(item)

    user_ids = {
        *(item.submitter_id for item in tickets if item.submitter_id),
        *(item.reviewer_id for item in tickets if item.reviewer_id),
        *(item.tech_id for item in tickets if item.tech_id),
        *(item.operator_id for item in actions if item.operator_id),
    }
    user_map: dict[int, str] = {}
    if user_ids:
        users = await User.filter(id__in=user_ids)
        user_map = {int(user.id): str(user.alias or user.username or "") for user in users}

    status_text = {
        TicketStatus.PENDING_REVIEW.value: "待客服审核",
        TicketStatus.CS_REJECTED.value: "客服驳回",
        TicketStatus.TECH_PROCESSING.value: "待技术处理",
        TicketStatus.FIELD_VERIFICATION.value: "现场验证",
        TicketStatus.PENDING_CLOSE.value: "待关闭",
        TicketStatus.TECH_REJECTED.value: "技术驳回",
        TicketStatus.DONE.value: "已关闭",
    }
    action_text = {
        TicketActionType.SUBMIT.value: "提交",
        TicketActionType.RESUBMIT.value: "重新提交",
        TicketActionType.CS_APPROVE.value: "客服通过",
        TicketActionType.CS_REJECT.value: "客服驳回",
        TicketActionType.TECH_START.value: "技术开始处理",
        TicketActionType.TECH_ASSIGN.value: "改派技术",
        TicketActionType.TECH_NOTE.value: "技术备注",
        TicketActionType.FIELD_VERIFY.value: "现场验证",
        TicketActionType.FIELD_REJECT.value: "现场验证驳回",
        TicketActionType.TECH_REJECT.value: "技术驳回",
        TicketActionType.FINISH.value: "处理完成",
        TicketActionType.CLOSE.value: "关闭",
    }

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "工单"
    headers = [
        "工单编号",
        "状态",
        "项目阶段",
        "跟踪",
        "影响范围",
        "分类",
        "根因",
        "标题",
        "项目名称",
        "联系人",
        "邮箱",
        "手机号",
        "提交人",
        "审核人",
        "技术处理人",
        "描述",
        "驳回原因",
        "附件",
        "操作日志",
        "创建时间",
        "更新时间",
        "完成时间",
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def fmt_dt(value):
        return value.strftime(settings.DATETIME_FORMAT) if isinstance(value, datetime) else ""

    for ticket in tickets:
        ticket_attachments = attachment_map.get(ticket.id, [])
        ticket_actions = action_map.get(ticket.id, [])
        attachment_text = "\n".join(
            f"{item.origin_name} ({item.file_size or 0} bytes)" for item in ticket_attachments
        )
        action_lines = []
        for action in ticket_actions:
            operator_name = user_map.get(action.operator_id, "") or str(action.operator_id or "-")
            action_lines.append(
                " | ".join(
                    part
                    for part in [
                        fmt_dt(action.created_at),
                        action_text.get(str(action.action), str(action.action)),
                        f"{status_text.get(str(action.from_status), str(action.from_status or '-'))} -> {status_text.get(str(action.to_status), str(action.to_status))}",
                        operator_name,
                        _clean_export_text(action.comment),
                    ]
                    if part
                )
            )
        sheet.append(
            [
                ticket.ticket_no,
                status_text.get(str(ticket.status), str(ticket.status)),
                ticket.project_phase,
                ticket.issue_type or "",
                ticket.impact_scope or "",
                ticket.category,
                ticket.root_cause or "",
                ticket.title,
                ticket.company_name,
                ticket.contact_name,
                ticket.email,
                ticket.phone,
                user_map.get(ticket.submitter_id, ""),
                user_map.get(ticket.reviewer_id or 0, ""),
                user_map.get(ticket.tech_id or 0, ""),
                _clean_export_text(ticket.description),
                _clean_export_text(ticket.reject_reason),
                attachment_text,
                "\n".join(action_lines),
                fmt_dt(ticket.created_at),
                fmt_dt(ticket.updated_at),
                fmt_dt(ticket.finished_at),
            ]
        )

    widths = [22, 14, 14, 14, 14, 16, 18, 30, 22, 14, 28, 18, 16, 16, 16, 56, 36, 36, 70, 20, 20, 20]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    filename = f"tickets_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    logger.info("[api.ticket.export] user_id={} total={}", user.id, total)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": build_download_content_disposition(filename)},
    )


@router.get("/get", summary="工单详情", dependencies=[DependAuth])
async def get_ticket(ticket_id: int = Query(..., description="工单ID")):
    start_at = perf_counter()
    user = await _get_current_user()
    auth_cost_ms = int((perf_counter() - start_at) * 1000)

    perm_start_at = perf_counter()
    role_names = await _get_user_role_names(user)
    ticket = await Ticket.get(id=ticket_id)
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限查看该工单")
    perm_cost_ms = int((perf_counter() - perm_start_at) * 1000)

    detail_start_at = perf_counter()
    detail = await ticket_controller.get_ticket_detail(ticket_id=ticket_id, ticket=ticket)
    detail_cost_ms = int((perf_counter() - detail_start_at) * 1000)

    total_cost_ms = int((perf_counter() - start_at) * 1000)
    logger.info(
        "[api.ticket.get] user_id={} ticket_id={} status={} auth_ms={} perm_ms={} detail_ms={} total_ms={}",
        user.id,
        ticket_id,
        ticket.status,
        auth_cost_ms,
        perm_cost_ms,
        detail_cost_ms,
        total_cost_ms,
    )
    return Success(data=detail)


@router.post("/review", summary="客服审核工单", dependencies=[DependAuth])
async def review_ticket(payload: TicketReviewIn):
    user = await _get_current_user()
    logger.info("[api.ticket.review] request user_id={} ticket_id={} approved={}", user.id, payload.ticket_id, payload.approved)
    role_names = await _get_user_role_names(user)
    if not user.is_superuser and ROLE_ADMIN not in role_names and ROLE_CUSTOMER_SERVICE not in role_names:
        return Fail(code=403, msg="仅客服或管理员可执行审核操作")
    current_ticket = await ticket_controller.get_ticket(payload.ticket_id)
    if not await _can_access_ticket(current_ticket, user, role_names):
        return Fail(code=403, msg="暂无权限操作该工单")

    ticket = await ticket_controller.set_customer_service_review(
        ticket_id=payload.ticket_id,
        reviewer_id=user.id,
        approved=payload.approved,
        comment=payload.comment,
        tech_id=payload.tech_id,
    )
    logger.info("[api.ticket.review] success user_id={} ticket_id={} status={}", user.id, ticket.id, ticket.status)
    return Success(msg="审核成功", data=await ticket.to_dict())


@router.post("/tech/action", summary="技术处理工单", dependencies=[DependAuth])
async def tech_action_ticket(payload: TicketTechActionIn):
    user = await _get_current_user()
    logger.info(
        "[api.ticket.tech_action] request user_id={} ticket_id={} action={}",
        user.id,
        payload.ticket_id,
        payload.action,
    )
    role_names = await _get_user_role_names(user)
    if not user.is_superuser and ROLE_ADMIN not in role_names and ROLE_TECH not in role_names:
        return Fail(code=403, msg="仅技术或管理员可处理工单")
    current_ticket = await ticket_controller.get_ticket(payload.ticket_id)
    if not await _can_access_ticket(current_ticket, user, role_names):
        return Fail(code=403, msg="暂无权限操作该工单")

    ticket = await ticket_controller.set_tech_action(
        ticket_id=payload.ticket_id,
        tech_id=user.id,
        action=payload.action,
        comment=payload.comment,
        root_cause=payload.root_cause,
    )

    logger.info("[api.ticket.tech_action] success user_id={} ticket_id={} status={}", user.id, ticket.id, ticket.status)
    return Success(msg="处理成功", data=await ticket.to_dict())




@router.post("/assign-tech", summary="改派技术处理人", dependencies=[DependAuth])
async def assign_ticket_tech(payload: TicketAssignTechIn):
    user = await _get_current_user()
    logger.info(
        "[api.ticket.assign_tech] request user_id={} ticket_id={} tech_id={}",
        user.id,
        payload.ticket_id,
        payload.tech_id,
    )
    role_names = await _get_user_role_names(user)
    is_admin = user.is_superuser or ROLE_ADMIN in role_names
    is_customer_service = ROLE_CUSTOMER_SERVICE in role_names
    is_tech = ROLE_TECH in role_names
    if not (is_admin or is_customer_service or is_tech):
        return Fail(code=403, msg="仅客服、技术或管理员可改派技术处理人")
    current_ticket = await ticket_controller.get_ticket(payload.ticket_id)
    if not await _can_access_ticket(current_ticket, user, role_names):
        return Fail(code=403, msg="暂无权限操作该工单")
    if is_tech and not (is_admin or is_customer_service):
        if current_ticket.tech_id != user.id:
            return Fail(code=403, msg="技术只能改派自己当前处理的工单")

    ticket = await ticket_controller.assign_tech(
        ticket_id=payload.ticket_id,
        operator_id=user.id,
        tech_id=payload.tech_id,
        comment=payload.comment,
    )
    logger.info("[api.ticket.assign_tech] success user_id={} ticket_id={} tech_id={}", user.id, ticket.id, ticket.tech_id)
    return Success(msg="改派成功", data=await ticket.to_dict())

@router.get("/attachment/download", summary="下载工单附件", dependencies=[DependAuth])
async def download_ticket_attachment(attachment_id: int = Query(..., description="附件ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    data = await ticket_controller.get_attachment_download(attachment_id=attachment_id, user=user, role_names=role_names)
    return FileResponse(data["abs_path"], media_type=data["media_type"], filename=None, headers=data["headers"])


@router.get("/attachment/preview-cache", summary="缓存工单附件用于预览", dependencies=[DependAuth])
async def cache_ticket_attachment_preview(attachment_id: int = Query(..., description="附件ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    data = await ticket_controller.cache_attachment_preview(attachment_id=attachment_id, user=user, role_names=role_names)
    return Success(data=data)


@router.post("/resubmit", summary="重提工单", dependencies=[DependAuth])
async def resubmit_ticket(payload: TicketResubmitIn, request: Request):
    user = await _get_current_user()
    logger.info("[api.ticket.resubmit] request user_id={} ticket_id={}", user.id, payload.ticket_id)
    pending = await partner_controller.has_pending_registration(
        email=user.email,
        phone=user.phone,
        username=user.username,
        hardware_id=user.hardware_id,
    )
    if pending:
        return Fail(code=403, msg="您的注册申请仍在审核中，暂不可提交工单")

    valid, challenge_error = await human_challenge_service.verify(
        captcha_id=payload.captcha_id,
        captcha_code=payload.captcha_code,
        turnstile_token=payload.turnstile_token,
        client_ip=get_client_ip(request),
        log_context="api.ticket.resubmit",
    )
    if not valid:
        logger.warning("[api.ticket.resubmit] captcha_invalid user_id={} ticket_id={}", user.id, payload.ticket_id)
        return Fail(code=400, msg=challenge_error)
    if payload.description:
        version_error = redmine_sync_service.ticket_description_version_error(payload.description)
        if version_error:
            return Fail(code=400, msg=version_error)

    ticket = await ticket_controller.resubmit_ticket(
        ticket_id=payload.ticket_id,
        submitter_id=user.id,
        description=payload.description,
        attachment_ids=payload.attachment_ids,
    )
    logger.info("[api.ticket.resubmit] success user_id={} ticket_id={} status={}", user.id, ticket.id, ticket.status)
    return Success(msg="重提成功", data=await ticket.to_dict())


@router.post("/update", summary="编辑工单", dependencies=[DependAuth])
async def update_ticket(payload: TicketUpdateIn, request: Request):
    user = await _get_current_user()
    logger.info(
        "[api.ticket.update] request user_id={} ticket_id={}",
        user.id,
        payload.ticket_id,
    )

    config = await system_setting_controller.get_full_dict()
    valid, challenge_error = await human_challenge_service.verify(
        captcha_id=payload.captcha_id,
        captcha_code=payload.captcha_code,
        turnstile_token=payload.turnstile_token,
        client_ip=get_client_ip(request),
        config=config,
        log_context="api.ticket.update",
    )
    if not valid:
        logger.warning("[api.ticket.update] captcha_invalid user_id={} ticket_id={}", user.id, payload.ticket_id)
        return Fail(code=400, msg=challenge_error)

    project_phases = config.get("ticket_project_phases") or []
    issue_types = config.get("ticket_issue_types") or []
    impact_scopes = config.get("ticket_impact_scopes") or []
    categories = config.get("ticket_categories") or []
    issue_type = _resolve_ticket_issue_type(payload.issue_type, issue_types)
    impact_scope = _resolve_ticket_impact_scope(payload.impact_scope, impact_scopes)
    if project_phases and payload.project_phase not in project_phases:
        return Fail(code=400, msg="项目阶段已更新，请刷新页面后重新选择")
    if issue_types and issue_type not in issue_types:
        return Fail(code=400, msg="跟踪已更新，请刷新页面后重新选择")
    if impact_scopes and impact_scope not in impact_scopes:
        return Fail(code=400, msg="影响范围已更新，请刷新页面后重新选择")
    if categories and payload.category not in categories:
        return Fail(code=400, msg="问题分类已更新，请刷新页面后重新选择")
    version_error = redmine_sync_service.ticket_description_version_error(payload.description)
    if version_error:
        return Fail(code=400, msg=version_error)

    body = payload.model_dump(exclude={"ticket_id", "attachment_ids", "captcha_id", "captcha_code", "turnstile_token"})
    if "issue_type" in payload.model_fields_set:
        body["issue_type"] = issue_type
    else:
        body.pop("issue_type", None)
    if "impact_scope" in payload.model_fields_set:
        body["impact_scope"] = impact_scope
    else:
        body.pop("impact_scope", None)
    ticket = await ticket_controller.update_ticket(
        ticket_id=payload.ticket_id,
        operator_id=user.id,
        role_names=await _get_user_role_names(user),
        payload=body,
        attachment_ids=payload.attachment_ids,
    )
    logger.info("[api.ticket.update] success user_id={} ticket_id={} status={}", user.id, ticket.id, ticket.status)
    return Success(msg="编辑成功", data=await ticket.to_dict())


@router.post("/close", summary="关闭工单", dependencies=[DependAuth])
async def close_ticket(payload: TicketCloseIn):
    user = await _get_current_user()
    ticket = await ticket_controller.close_ticket(
        ticket_id=payload.ticket_id,
        operator_id=user.id,
        role_names=await _get_user_role_names(user),
        comment=payload.comment,
    )
    logger.info("[api.ticket.close] success user_id={} ticket_id={} status={}", user.id, ticket.id, ticket.status)
    return Success(msg="关闭成功", data=await ticket.to_dict())


@router.post("/field-verification", summary="处理现场验证结果", dependencies=[DependAuth])
async def field_verification_ticket(payload: TicketFieldVerificationIn):
    user = await _get_current_user()
    ticket = await ticket_controller.set_field_verification_result(
        ticket_id=payload.ticket_id,
        operator_id=user.id,
        approved=payload.approved,
        comment=payload.comment,
    )
    logger.info(
        "[api.ticket.field_verification] success user_id={} ticket_id={} approved={} status={}",
        user.id,
        ticket.id,
        payload.approved,
        ticket.status,
    )
    return Success(msg="现场验证已处理", data=await ticket.to_dict())


@router.get("/actions", summary="工单操作日志", dependencies=[DependAuth])
async def ticket_actions(ticket_id: int = Query(..., description="工单ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    ticket = await Ticket.get(id=ticket_id)
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限查看该工单")
    logs = await TicketActionLog.filter(ticket_id=ticket_id).order_by("id")
    data = [await item.to_dict() for item in logs]
    return Success(data=data)


@router.post("/redmine/push", summary="同步工单到 Redmine", dependencies=[DependAuth])
async def push_ticket_to_redmine(payload: TicketRedmineSyncIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not user.is_superuser and ROLE_ADMIN not in role_names and ROLE_TECH not in role_names:
        return Fail(code=403, msg="仅技术或管理员可同步 Redmine")
    ticket = await ticket_controller.get_ticket(payload.ticket_id)
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="暂无权限操作该工单")
    data = await redmine_sync_service.push_ticket(
        ticket,
        operator_id=user.id,
        note=payload.note,
        project_id=payload.project_id,
        tracker_id=payload.tracker_id,
        priority_id=payload.priority_id,
        assigned_to_id=payload.assigned_to_id,
        project_phase=payload.project_phase,
        os_value=payload.os_value,
    )
    return Success(msg="Redmine 同步完成", data=data)


@router.post("/redmine/pull", summary="从 Redmine 拉取工单状态", dependencies=[DependAuth])
async def pull_ticket_from_redmine(payload: TicketRedmineSyncIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not user.is_superuser and ROLE_ADMIN not in role_names and ROLE_TECH not in role_names:
        return Fail(code=403, msg="仅技术或管理员可拉取 Redmine 状态")
    ticket = await ticket_controller.get_ticket(payload.ticket_id)
    if not await _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="暂无权限操作该工单")
    data = await redmine_sync_service.pull_ticket(ticket, operator_id=user.id)
    return Success(msg="Redmine 状态已更新", data=data)
