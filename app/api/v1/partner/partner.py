from fastapi import APIRouter, HTTPException, Query
from tortoise.expressions import Q

from app.log import logger
from app.controllers.mail import mail_controller
from app.controllers.partner import partner_controller
from app.controllers.system_setting import system_setting_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import PartnerRegistration, User
from app.models.enums import PartnerRegisterStatus, RegisterType
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.partner import PartnerRegisterIn, PartnerReviewIn, UserRegisterIn

router = APIRouter()


async def _is_cs_or_admin(user_id: int) -> bool:
    user = await User.filter(id=user_id).first()
    if not user:
        return False
    if user.is_superuser:
        return True
    roles = await user.roles
    role_names = [role.name for role in roles]
    return "管理员" in role_names or "客服" in role_names


@router.post("/register", summary="渠道商/用户注册")
async def partner_register(payload: PartnerRegisterIn):
    logger.info(
        "[api.partner.register] request register_type={} email={} company_name={}",
        payload.register_type,
        payload.email,
        payload.company_name,
    )
    config = await system_setting_controller.get_public_config()
    if not config.get("allow_partner_register", True):
        return Fail(code=403, msg="当前暂未开放注册，如需开通请联系平台管理员")

    email_valid = await mail_controller.verify_email_code(payload.email, payload.email_code)
    if not email_valid:
        logger.warning("[api.partner.register] email_code_invalid email={}", payload.email)
        return Fail(code=400, msg="邮箱验证码错误或已失效，请重新获取后再提交")

    auto_approve = config.get("customer_service_auto_approve_register", False)
    try:
        register_obj = await partner_controller.register(payload)
        if auto_approve:
            register_obj = await partner_controller.review(
                register_id=register_obj.id,
                reviewer_id=0,
                approved=True,
                comment="客服自动审批",
            )
    except HTTPException as exc:
        return Fail(code=exc.status_code, msg=str(exc.detail))
    logger.info("[api.partner.register] success register_id={} email={}", register_obj.id, register_obj.email)
    msg = "注册成功，已自动审核通过" if auto_approve else "注册成功，请等待审核"
    return Success(msg=msg, data=await register_obj.to_dict(exclude_fields=["password_hash"]))


@router.post("/register/channel", summary="渠道商注册")
async def channel_register(payload: PartnerRegisterIn):
    payload.register_type = RegisterType.CHANNEL
    return await partner_register(payload)


@router.post("/register/user", summary="用户注册")
async def user_register(payload: UserRegisterIn):
    payload.register_type = RegisterType.USER
    return await partner_register(payload)


@router.get("/register/list", summary="注册申请列表", dependencies=[DependAuth])
async def partner_register_list(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    status: PartnerRegisterStatus | None = Query(None, description="审核状态"),
    register_type: RegisterType | None = Query(None, description="注册类型"),
    reviewed: bool | None = Query(None, description="是否已审核"),
    keyword: str | None = Query(None, description="关键词"),
):
    user_id = CTX_USER_ID.get()
    logger.info(
        "[api.partner.list] request user_id={} page={} page_size={} status={} register_type={} reviewed={}",
        user_id,
        page,
        page_size,
        status,
        register_type,
        reviewed,
    )
    if not await _is_cs_or_admin(user_id):
        return Fail(code=403, msg="您暂无权限查看注册申请列表")

    q = Q()
    if status:
        q &= Q(status=status)
    elif reviewed is True:
        q &= Q(status__in=[PartnerRegisterStatus.APPROVED, PartnerRegisterStatus.REJECTED])
    elif reviewed is False:
        q &= Q(status=PartnerRegisterStatus.PENDING)
    if register_type:
        q &= Q(register_type=register_type)
    if keyword:
        q &= (
            Q(company_name__contains=keyword)
            | Q(contact_name__contains=keyword)
            | Q(email__contains=keyword)
            | Q(phone__contains=keyword)
            | Q(hardware_id__contains=keyword)
        )

    query = PartnerRegistration.filter(q)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("-id")
    data = [await item.to_dict(exclude_fields=["password_hash"]) for item in rows]
    logger.info("[api.partner.list] success user_id={} total={} page={}", user_id, total, page)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.post("/register/review", summary="审核注册", dependencies=[DependAuth])
async def partner_register_review(payload: PartnerReviewIn):
    user_id = CTX_USER_ID.get()
    logger.info(
        "[api.partner.review] request reviewer_id={} register_id={} approved={}",
        user_id,
        payload.id,
        payload.approved,
    )
    if not await _is_cs_or_admin(user_id):
        return Fail(code=403, msg="您暂无权限执行审核操作")

    if not payload.approved and not (payload.comment or "").strip():
        return Fail(code=400, msg="请填写驳回理由后再提交")

    try:
        obj = await partner_controller.review(
            register_id=payload.id,
            reviewer_id=user_id,
            approved=payload.approved,
            comment=payload.comment,
        )
    except HTTPException as exc:
        return Fail(code=exc.status_code, msg=str(exc.detail))
    logger.info("[api.partner.review] success reviewer_id={} register_id={} status={}", user_id, obj.id, obj.status)
    return Success(msg="审核完成", data=await obj.to_dict(exclude_fields=["password_hash"]))
