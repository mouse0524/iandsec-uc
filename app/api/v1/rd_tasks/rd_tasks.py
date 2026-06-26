from fastapi import APIRouter, Query

from app.controllers.rd_task import rd_task_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import User
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.rd_tasks import RdTaskCreateFromTicketIn, RdTaskLinkTicketIn, RdTaskTransitionIn
from app.models.enums import RdTaskStatus, RdTaskType

router = APIRouter()


async def _get_current_user() -> User:
    return await User.get(id=CTX_USER_ID.get())


async def _get_user_role_names(user: User) -> list[str]:
    return [role.name for role in await user.roles]


def _can_use_rd_task(role_names: list[str], user: User) -> bool:
    return user.is_superuser or any(role in role_names for role in ["管理员", "技术", "产品", "研发", "测试", "客服"])


@router.get("/list", summary="产研任务列表", dependencies=[DependAuth])
async def list_rd_tasks(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    status: RdTaskStatus | None = Query(None, description="状态"),
    task_type: RdTaskType | None = Query(None, description="类型"),
    keyword: str | None = Query(None, description="关键词"),
    owner_id: int | None = Query(None, description="负责人ID"),
):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not _can_use_rd_task(role_names, user):
        return Fail(code=403, msg="暂无产研任务权限")
    total, rows = await rd_task_controller.list_tasks(
        page=page,
        page_size=page_size,
        status=status,
        task_type=task_type,
        keyword=keyword,
        owner_id=owner_id,
    )
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size)


@router.get("/get", summary="产研任务详情", dependencies=[DependAuth])
async def get_rd_task(task_id: int = Query(..., description="产研任务ID")):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not _can_use_rd_task(role_names, user):
        return Fail(code=403, msg="暂无产研任务权限")
    return Success(data=await rd_task_controller.detail(task_id))


@router.post("/create-from-ticket", summary="工单转产研任务", dependencies=[DependAuth])
async def create_rd_task_from_ticket(payload: RdTaskCreateFromTicketIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not (user.is_superuser or any(role in role_names for role in ["管理员", "技术"])):
        return Fail(code=403, msg="仅技术或管理员可转产研任务")
    task = await rd_task_controller.create_from_ticket(
        ticket_id=payload.ticket_id,
        operator_id=user.id,
        task_type=payload.task_type,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        product_owner_id=payload.product_owner_id,
        dev_owner_id=payload.dev_owner_id,
        test_owner_id=payload.test_owner_id,
        planned_version=payload.planned_version,
    )
    return Success(msg="已转产研任务", data=await task.to_dict())


@router.post("/link-ticket", summary="关联工单到产研任务", dependencies=[DependAuth])
async def link_ticket_to_rd_task(payload: RdTaskLinkTicketIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not (user.is_superuser or any(role in role_names for role in ["管理员", "技术"])):
        return Fail(code=403, msg="仅技术或管理员可关联产研任务")
    link = await rd_task_controller.link_ticket(
        task_id=payload.task_id,
        ticket_id=payload.ticket_id,
        operator_id=user.id,
    )
    return Success(msg="关联成功", data=await link.to_dict())


@router.post("/transition", summary="产研任务流转", dependencies=[DependAuth])
async def transition_rd_task(payload: RdTaskTransitionIn):
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not _can_use_rd_task(role_names, user):
        return Fail(code=403, msg="暂无产研任务权限")
    result = await rd_task_controller.transition(
        task_id=payload.task_id,
        operator_id=user.id,
        action=payload.action,
        comment=payload.comment,
        role_names=role_names,
        is_superuser=user.is_superuser,
    )
    data = await result["task"].to_dict()
    data["followup_ticket_ids"] = result["followup_ticket_ids"]
    return Success(msg="流转成功", data=data)
