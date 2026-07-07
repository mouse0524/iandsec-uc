from urllib.parse import quote, urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from tortoise.expressions import Q

from app.log import logger
from app.controllers.mail import mail_controller
from app.controllers.partner import partner_controller
from app.controllers.system_setting import system_setting_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import PartnerInvite, PartnerRegistration, User
from app.models.enums import PartnerRegisterStatus, RegisterType
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.partner import PartnerInviteCreateOut, PartnerRegisterIn, PartnerReviewIn, UserRegisterIn

router = APIRouter()


async def _get_current_user() -> User | None:
    user_id = CTX_USER_ID.get()
    return await User.filter(id=user_id).first()


async def _get_user_role_names(user: User | None) -> list[str]:
    if not user:
        return []
    roles = await user.roles
    return [role.name for role in roles]


def _can_manage_all_registers(user: User | None, role_names: list[str]) -> bool:
    return bool(user and (user.is_superuser or user.username == "admin" or "管理员" in role_names or "客服" in role_names))


def _can_review_registration(
    user: User | None, role_names: list[str], *, register_id: int, invited_registration_ids: list[int]
) -> bool:
    if _can_manage_all_registers(user, role_names):
        return True
    return "技术" in role_names and int(register_id) in {int(item) for item in invited_registration_ids}


def _build_register_list_query(
    *,
    user: User,
    role_names: list[str],
    invited_registration_ids: list[int],
    status: PartnerRegisterStatus | None = None,
    register_type: RegisterType | None = None,
    reviewed: bool | None = None,
    keyword: str | None = None,
) -> Q:
    q = Q()
    if not _can_manage_all_registers(user, role_names):
        q &= Q(id__in=invited_registration_ids)
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
    return q


async def _tech_invited_registration_ids(tech_id: int) -> list[int]:
    rows = await PartnerInvite.filter(created_by=tech_id).values_list("used_by", flat=True)
    return [int(item) for item in rows if item]


def _build_invite_link(request: Request, code: str) -> str:
    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    if not origin:
        referer = (request.headers.get("referer") or "").strip()
        parsed = urlsplit(referer)
        if parsed.scheme and parsed.netloc:
            origin = f"{parsed.scheme}://{parsed.netloc}"
    if not origin:
        origin = str(request.base_url).rstrip("/")
    return f"{origin}/login?invite_code={quote(code, safe='')}"


async def _is_tech(user_id: int) -> bool:
    user = await User.filter(id=user_id).first()
    if not user:
        return False
    roles = await user.roles
    role_names = [role.name for role in roles]
    return "技术" in role_names


def _register_closed_message(register_type: RegisterType) -> str:
    if register_type == RegisterType.CHANNEL:
        return "当前暂未开放渠道商注册，如需开通请联系平台管理员"
    if register_type == RegisterType.USER:
        return "当前暂未开放用户注册，如需开通请联系平台管理员"
    return "当前暂未开放注册，如需开通请联系平台管理员"


def _is_register_type_enabled(config: dict, register_type: RegisterType) -> bool:
    legacy_enabled = config.get("allow_partner_register", True)
    if register_type == RegisterType.CHANNEL:
        return config.get("allow_channel_register", legacy_enabled)
    if register_type == RegisterType.USER:
        return config.get("allow_user_register", legacy_enabled)
    return legacy_enabled


@router.post("/register", summary="渠道商/用户注册")
async def partner_register(payload: PartnerRegisterIn):
    logger.info(
        "[api.partner.register] request register_type={} email={} company_name={}",
        payload.register_type,
        payload.email,
        payload.company_name,
    )
    config = await system_setting_controller.get_public_config()
    if not _is_register_type_enabled(config, payload.register_type):
        return Fail(code=403, msg=_register_closed_message(payload.register_type))

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


@router.post("/invite/create", summary="创建注册邀请链接", dependencies=[DependAuth])
async def create_partner_invite(request: Request):
    user_id = CTX_USER_ID.get()
    if not await _is_tech(user_id):
        return Fail(code=403, msg="仅技术可以创建邀请链接")
    invite = await partner_controller.create_invite(tech_id=user_id)
    return Success(data=PartnerInviteCreateOut(code=invite.code, link=_build_invite_link(request, invite.code)).model_dump())


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
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    if not user or not (_can_manage_all_registers(user, role_names) or "技术" in role_names):
        return Fail(code=403, msg="您暂无权限查看注册申请列表")

    invited_registration_ids = await _tech_invited_registration_ids(user.id) if "技术" in role_names else []
    q = _build_register_list_query(
        user=user,
        role_names=role_names,
        invited_registration_ids=invited_registration_ids,
        status=status,
        register_type=register_type,
        reviewed=reviewed,
        keyword=keyword,
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
    user = await _get_current_user()
    role_names = await _get_user_role_names(user)
    invited_registration_ids = await _tech_invited_registration_ids(user.id) if user and "技术" in role_names else []
    if not _can_review_registration(user, role_names, register_id=payload.id, invited_registration_ids=invited_registration_ids):
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
