from datetime import datetime
import json
from time import perf_counter

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from tortoise.expressions import Q

from app.log import logger
from app.controllers.captcha import captcha_controller
from app.controllers.partner import partner_controller
from app.controllers.system_setting import system_setting_controller
from app.controllers.ticket import ticket_controller
from app.core.redis_client import execute_redis
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import Ticket, TicketActionLog, User
from app.models.enums import TicketActionType, TicketStatus
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.tickets import TicketCreate, TicketResubmitIn, TicketReviewIn, TicketTechActionIn, TicketUpdateIn

router = APIRouter()


async def _get_current_user() -> User:
    user_id = CTX_USER_ID.get()
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="当前用户不存在")
    return user


async def _get_user_role_names(user: User) -> list[str]:
    roles = await user.roles
    return [role.name for role in roles]


def _can_access_ticket(ticket: Ticket, user: User, role_names: list[str]) -> bool:
    if user.is_superuser or "管理员" in role_names or "客服" in role_names:
        return True
    if "技术" in role_names:
        return ticket.submitter_id == user.id or ticket.tech_id == user.id
    return ticket.submitter_id == user.id


@router.post("/upload", summary="上传工单附件", dependencies=[DependAuth])
async def upload_ticket_attachment(file: UploadFile = File(...)):
    user_id = CTX_USER_ID.get()
    logger.info("[api.ticket.upload] request user_id={} filename={}", user_id, file.filename)
    attachment = await ticket_controller.upload_attachment(uploader_id=user_id, file=file)
    logger.info("[api.ticket.upload] success user_id={} attachment_id={} path={}", user_id, attachment.id, attachment.file_path)
    return Success(data=await attachment.to_dict())


@router.post("/create", summary="提交工单", dependencies=[DependAuth])
async def create_ticket(payload: TicketCreate):
    user = await _get_current_user()
    logger.info("[api.ticket.create] request user_id={}", user.id)
    role_names = await _get_user_role_names(user)
    if not user.is_superuser and not any(role in role_names for role in ["用户", "渠道商", "代理商", "技术", "管理员"]):
        return Fail(code=403, msg="您当前账号暂无提交工单权限，请联系管理员")

    pending = await partner_controller.has_pending_registration(
        email=user.email,
        phone=user.phone,
        username=user.username,
        hardware_id=user.hardware_id,
    )
    if pending:
        return Fail(code=403, msg="您的注册申请仍在审核中，暂不可提交工单")

    valid = await captcha_controller.verify_captcha(payload.captcha_id, payload.captcha_code)
    if not valid:
        logger.warning("[api.ticket.create] captcha_invalid user_id={}", user.id)
        return Fail(code=400, msg="验证码错误或已失效，请重试")

    config = await system_setting_controller.get_public_config()
    project_phases = config.get("ticket_project_phases") or []
    categories = config.get("ticket_categories") or []
    if project_phases and payload.project_phase not in project_phases:
        return Fail(code=400, msg="项目阶段已更新，请刷新页面后重新选择")
    if categories and payload.category not in categories:
        return Fail(code=400, msg="问题分类已更新，请刷新页面后重新选择")

    body = payload.model_dump(exclude={"captcha_id", "captcha_code"})
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
    project_phase: str | None = Query(None, description="项目阶段"),
    category: str | None = Query(None, description="分类"),
    root_cause: str | None = Query(None, description="问题根因"),
    title: str | None = Query(None, description="标题"),
    created_start: datetime | None = Query(None, description="创建时间开始"),
    created_end: datetime | None = Query(None, description="创建时间结束"),
    finished_start: datetime | None = Query(None, description="完成时间开始"),
    finished_end: datetime | None = Query(None, description="完成时间结束"),
):
    start_at = perf_counter()
    user = await _get_current_user()
    auth_cost_ms = int((perf_counter() - start_at) * 1000)

    filter_start_at = perf_counter()
    role_names = await _get_user_role_names(user)

    q = Q()
    if status:
        q &= Q(status=status)
    if project_phase:
        q &= Q(project_phase=project_phase)
    if category:
        q &= Q(category=category)
    if root_cause:
        q &= Q(root_cause=root_cause)
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

    if not user.is_superuser and "管理员" not in role_names and "客服" not in role_names:
        if "技术" in role_names:
            q &= Q(tech_id=user.id)
        else:
            q &= Q(submitter_id=user.id)
    filter_cost_ms = int((perf_counter() - filter_start_at) * 1000)

    query_start_at = perf_counter()
    total, rows = await ticket_controller.list_tickets(page=page, page_size=page_size, search=q)
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
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size)


@router.get("/get", summary="工单详情", dependencies=[DependAuth])
async def get_ticket(ticket_id: int = Query(..., description="工单ID")):
    start_at = perf_counter()
    user = await _get_current_user()
    auth_cost_ms = int((perf_counter() - start_at) * 1000)

    perm_start_at = perf_counter()
    role_names = await _get_user_role_names(user)
    ticket = await Ticket.get(id=ticket_id)
    if not _can_access_ticket(ticket, user, role_names):
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
    if not user.is_superuser and "管理员" not in role_names and "客服" not in role_names:
        return Fail(code=403, msg="仅客服或管理员可执行审核操作")

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
    if not user.is_superuser and "管理员" not in role_names and "技术" not in role_names:
        return Fail(code=403, msg="仅技术或管理员可处理工单")

    ticket = await ticket_controller.set_tech_action(
        ticket_id=payload.ticket_id,
        tech_id=user.id,
        action=payload.action,
        comment=payload.comment,
        root_cause=payload.root_cause,
    )

    logger.info("[api.ticket.tech_action] success user_id={} ticket_id={} status={}", user.id, ticket.id, ticket.status)
    return Success(msg="处理成功", data=await ticket.to_dict())


@router.get("/attachment/download", summary="下载工单附件", dependencies=[DependAuth])
async def download_ticket_attachment(attachment_id: int = Query(..., description="附件ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    data = await ticket_controller.get_attachment_download(attachment_id=attachment_id, user=user, role_names=role_names)
    return FileResponse(data["abs_path"], media_type=data["media_type"], filename=None, headers=data["headers"])


@router.post("/resubmit", summary="重提工单", dependencies=[DependAuth])
async def resubmit_ticket(payload: TicketResubmitIn):
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

    valid = await captcha_controller.verify_captcha(payload.captcha_id, payload.captcha_code)
    if not valid:
        logger.warning("[api.ticket.resubmit] captcha_invalid user_id={} ticket_id={}", user.id, payload.ticket_id)
        return Fail(code=400, msg="验证码错误或已失效，请重试")

    ticket = await ticket_controller.resubmit_ticket(
        ticket_id=payload.ticket_id,
        submitter_id=user.id,
        description=payload.description,
        attachment_ids=payload.attachment_ids,
    )
    logger.info("[api.ticket.resubmit] success user_id={} ticket_id={} status={}", user.id, ticket.id, ticket.status)
    return Success(msg="重提成功", data=await ticket.to_dict())


@router.post("/update", summary="编辑工单", dependencies=[DependAuth])
async def update_ticket(payload: TicketUpdateIn):
    user = await _get_current_user()
    logger.info(
        "[api.ticket.update] request user_id={} ticket_id={}",
        user.id,
        payload.ticket_id,
    )

    valid = await captcha_controller.verify_captcha(payload.captcha_id, payload.captcha_code)
    if not valid:
        logger.warning("[api.ticket.update] captcha_invalid user_id={} ticket_id={}", user.id, payload.ticket_id)
        return Fail(code=400, msg="验证码错误或已失效，请重试")

    config = await system_setting_controller.get_public_config()
    project_phases = config.get("ticket_project_phases") or []
    categories = config.get("ticket_categories") or []
    if project_phases and payload.project_phase not in project_phases:
        return Fail(code=400, msg="项目阶段已更新，请刷新页面后重新选择")
    if categories and payload.category not in categories:
        return Fail(code=400, msg="问题分类已更新，请刷新页面后重新选择")

    body = payload.model_dump(exclude={"ticket_id", "attachment_ids", "captcha_id", "captcha_code"})
    ticket = await ticket_controller.update_ticket(
        ticket_id=payload.ticket_id,
        submitter_id=user.id,
        payload=body,
        attachment_ids=payload.attachment_ids,
    )
    logger.info("[api.ticket.update] success user_id={} ticket_id={} status={}", user.id, ticket.id, ticket.status)
    return Success(msg="编辑成功", data=await ticket.to_dict())


@router.get("/actions", summary="工单操作日志", dependencies=[DependAuth])
async def ticket_actions(ticket_id: int = Query(..., description="工单ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    ticket = await Ticket.get(id=ticket_id)
    if not _can_access_ticket(ticket, user, role_names):
        return Fail(code=403, msg="您暂无权限查看该工单")
    logs = await TicketActionLog.filter(ticket_id=ticket_id).order_by("id")
    data = [await item.to_dict() for item in logs]
    return Success(data=data)
