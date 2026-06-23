from datetime import datetime, timedelta, timezone
import json
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from tortoise import Tortoise
from tortoise.expressions import Q

from app.log import logger
from app.core.redis_client import execute_redis
from app.controllers.login_security import login_security_controller
from app.controllers.user import user_controller
from app.controllers.captcha import captcha_controller
from app.controllers.mail import mail_controller
from app.controllers.system_setting import system_setting_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import (
    Api,
    AuditLog,
    Menu,
    PartnerRegistration,
    Role,
    SkillKnowConversation,
    SkillKnowDocument,
    SkillKnowDocumentChunk,
    SkillKnowMessage,
    TerminalAuthReport,
    Ticket,
    User,
    WebDavShareLink,
)
from app.models.enums import PartnerRegisterStatus, RegisterType, SkillKnowDocumentStatus, TicketStatus
from app.schemas.captcha import CaptchaOut
from app.schemas.mail import ResetPasswordByEmailIn, SendResetPasswordCodeIn, SendVerifyCodeIn
from app.schemas.base import Fail, Success
from app.schemas.login import CredentialsSchema, JWTPayload, JWTOut
from app.schemas.users import UpdatePassword
from app.services.human_challenge import human_challenge_service
from app.settings import settings
from app.utils.jwt_utils import create_access_token
from app.utils.password import get_password_hash, verify_password
from app.utils.request import get_client_ip

router = APIRouter()


def _format_lock_message(ttl_seconds: int) -> str:
    minutes = max(1, (ttl_seconds + 59) // 60)
    return f"登录失败次数过多，请 {minutes} 分钟后重试"


def _generic_login_error_message(config: dict) -> str:
    if not config.get("login_challenge_enabled", True):
        return "用户名或密码错误"
    challenge_type = str(config.get("login_challenge_type") or "captcha").strip().lower()
    if challenge_type == "turnstile":
        return "用户名、密码或安全校验错误"
    return "用户名、密码或验证码错误"


def _login_error_message(config: dict, fallback: str) -> str:
    if config.get("login_generic_error_enabled", True):
        return _generic_login_error_message(config)
    return fallback


def _login_auth_error_message(config: dict, fallback: str) -> str:
    if fallback == "用户已被禁用" or "已自动禁用" in fallback:
        return fallback
    return _login_error_message(config, fallback)


def _register_closed_message(register_type: RegisterType | None) -> str:
    if register_type == RegisterType.CHANNEL:
        return "当前暂未开放渠道商注册，如需开通请联系平台管理员"
    if register_type == RegisterType.USER:
        return "当前暂未开放用户注册，如需开通请联系平台管理员"
    return "当前暂未开放注册，如需开通请联系平台管理员"


def _is_register_type_enabled(config: dict, register_type: RegisterType | None) -> bool:
    legacy_enabled = config.get("allow_partner_register", True)
    if register_type == RegisterType.CHANNEL:
        return config.get("allow_channel_register", legacy_enabled)
    if register_type == RegisterType.USER:
        return config.get("allow_user_register", legacy_enabled)
    return legacy_enabled


@router.post("/access_token", summary="获取token")
async def login_access_token(credentials: CredentialsSchema, request: Request):
    logger.info("[api.login] start username={}", credentials.username)
    client_ip = get_client_ip(request)
    config = await system_setting_controller.get_full_dict()

    decision = await login_security_controller.check_lock(username=credentials.username, ip=client_ip)
    if decision.locked:
        logger.warning(
            "[api.login] locked username={} ip={} scope={} ttl_seconds={}",
            credentials.username,
            client_ip,
            decision.scope,
            decision.ttl_seconds,
        )
        return Fail(code=423, msg=_format_lock_message(decision.ttl_seconds))

    valid, challenge_error = await human_challenge_service.verify(
        captcha_id=credentials.captcha_id,
        captcha_code=credentials.captcha_code,
        turnstile_token=credentials.turnstile_token,
        client_ip=client_ip,
        config=config,
        log_context="api.login",
    )
    if not valid:
        fail_result = await login_security_controller.record_failure(username=credentials.username, ip=client_ip)
        if fail_result.locked:
            return Fail(code=423, msg=_format_lock_message(fail_result.ttl_seconds))
        return Fail(code=400, msg=_login_error_message(config, challenge_error))

    try:
        user: User = await user_controller.authenticate(credentials)
    except Exception as exc:
        fail_result = await login_security_controller.record_failure(username=credentials.username, ip=client_ip)
        if fail_result.locked:
            logger.warning(
                "[api.login] lock_triggered username={} ip={} scope={}",
                credentials.username,
                client_ip,
                fail_result.scope,
            )
            return Fail(code=423, msg=_format_lock_message(fail_result.ttl_seconds))
        return Fail(code=400, msg=_login_auth_error_message(config, str(getattr(exc, "detail", "登录失败"))))

    await login_security_controller.clear_success(username=credentials.username, ip=client_ip)
    await user_controller.update_last_login(user.id)
    token_expire_minutes = int(config.get("user_token_expire_minutes") or settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token_expire_minutes = min(30 * 24 * 60, max(1, token_expire_minutes))
    if credentials.remember_me:
        token_expire_minutes = 30 * 24 * 60
    access_token_expires = timedelta(minutes=token_expire_minutes)
    expire = datetime.now(timezone.utc) + access_token_expires

    data = JWTOut(
        access_token=create_access_token(
            data=JWTPayload(
                user_id=user.id,
                username=user.username,
                is_superuser=user.is_superuser,
                iss=settings.JWT_ISSUER,
                aud=settings.JWT_AUDIENCE,
                iat=datetime.now(timezone.utc),
                jti=uuid.uuid4(),
                token_version=getattr(user, "token_version", 0),
                exp=expire,
            )
        ),
        username=user.username,
    )
    logger.info(
        "[api.login] success username={} user_id={} remember_me={} expire_minutes={}",
        user.username,
        user.id,
        credentials.remember_me,
        token_expire_minutes,
    )
    return Success(data=data.model_dump())


@router.get("/captcha", summary="获取图形验证码")
async def get_captcha():
    captcha_id, image_base64 = await captcha_controller.create_captcha()
    data = CaptchaOut(captcha_id=captcha_id, image_base64=image_base64)
    return Success(data=data.model_dump())


@router.get("/public_config", summary="获取公共站点配置")
async def get_public_config():
    data = await system_setting_controller.get_public_config()
    return Success(data=data)


@router.get("/site_logo", summary="获取站点Logo")
async def get_site_logo():
    abs_path = await system_setting_controller.get_logo_abs_path()
    return FileResponse(abs_path)


@router.post("/send_email_code", summary="发送邮箱验证码")
async def send_email_code(payload: SendVerifyCodeIn, request: Request):
    config = await system_setting_controller.get_full_dict()
    if not _is_register_type_enabled(config, payload.register_type):
        return Fail(code=403, msg=_register_closed_message(payload.register_type))

    email = payload.email.strip().lower()
    logger.info("[api.send_email_code] start email={}", email)
    if await User.filter(email=email).exists():
        logger.warning("[api.send_email_code] email_exists email={}", email)
        return Fail(code=400, msg="该邮箱已完成注册，可直接登录")

    if await PartnerRegistration.filter(status=PartnerRegisterStatus.PENDING, email=email).exists():
        return Fail(code=400, msg="该邮箱已有待审核申请，请耐心等待审核结果")

    valid, challenge_error = await human_challenge_service.verify(
        captcha_id=payload.captcha_id,
        captcha_code=payload.captcha_code,
        turnstile_token=payload.turnstile_token,
        client_ip=get_client_ip(request),
        config=config,
        log_context="api.send_email_code",
    )
    if not valid:
        logger.warning("[api.send_email_code] captcha_invalid email={} captcha_id={}", email, payload.captcha_id)
        return Fail(code=400, msg=challenge_error)

    await mail_controller.send_partner_verify_code(email)
    logger.info("[api.send_email_code] success email={}", email)
    return Success(msg="验证码已发送，请查收邮箱")


@router.post("/send_reset_password_code", summary="发送找回密码验证码")
async def send_reset_password_code(payload: SendResetPasswordCodeIn, request: Request):
    email = payload.email.strip().lower()
    valid, challenge_error = await human_challenge_service.verify(
        captcha_id=payload.captcha_id,
        captcha_code=payload.captcha_code,
        turnstile_token=payload.turnstile_token,
        client_ip=get_client_ip(request),
        log_context="api.send_reset_password_code",
    )
    if not valid:
        return Fail(code=400, msg=challenge_error)

    user = await User.filter(email=email).first()
    if not user:
        return Fail(code=404, msg="该邮箱未注册")

    await mail_controller.send_reset_password_code(email)
    return Success(msg="验证码已发送，请查收邮箱")


@router.post("/reset_password_by_email", summary="邮箱验证码重置密码")
async def reset_password_by_email(payload: ResetPasswordByEmailIn):
    email = payload.email.strip().lower()
    user = await User.filter(email=email).first()
    if not user:
        return Fail(code=404, msg="该邮箱未注册")

    valid = await mail_controller.verify_email_code(email, payload.email_code)
    if not valid:
        return Fail(code=400, msg="邮箱验证码错误或已失效")

    await user_controller.validate_password_policy(payload.new_password)
    user.password = get_password_hash(payload.new_password)
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    await user.save()
    await user_controller.clear_auth_cache(user.id)
    return Success(msg="密码重置成功")


@router.get("/workbench_stats", summary="工作台统计", dependencies=[DependAuth])
async def get_workbench_stats():
    user_id = CTX_USER_ID.get()
    user = await user_controller.get(id=user_id)
    roles = await user.roles
    role_names = [role.name for role in roles]
    is_global = user.is_superuser or "管理员" in role_names or "客服" in role_names
    cache_key = "stats:workbench:global:v2" if is_global else f"stats:workbench:user:{user_id}:v2"
    try:
        cached = await execute_redis("get", cache_key)
        if cached:
            return Success(data=json.loads(cached))
    except json.JSONDecodeError as decode_exc:
        logger.warning("[api.workbench_stats] cache_read_json_failed key={} error={}", cache_key, str(decode_exc))
        try:
            await execute_redis("delete", cache_key)
        except Exception as clear_exc:
            logger.warning("[api.workbench_stats] cache_clear_failed key={} error={}", cache_key, str(clear_exc))
    except Exception as other_exc:
        logger.warning("[api.workbench_stats] cache_read_failed key={} error={}", cache_key, str(other_exc))

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    ticket_query = Ticket.all()
    if not is_global:
        if "技术" in role_names:
            ticket_query = Ticket.filter(tech_id=user_id)
        else:
            ticket_query = Ticket.filter(submitter_id=user_id)

    ticket_total = await ticket_query.count()
    ticket_pending_review = await ticket_query.filter(status=TicketStatus.PENDING_REVIEW).count()
    ticket_tech_processing = await ticket_query.filter(status=TicketStatus.TECH_PROCESSING).count()
    ticket_field_verification = await ticket_query.filter(status=TicketStatus.FIELD_VERIFICATION).count()
    ticket_pending_close = await ticket_query.filter(status=TicketStatus.PENDING_CLOSE).count()
    ticket_done = await ticket_query.filter(status=TicketStatus.DONE).count()
    ticket_rejected = await ticket_query.filter(status__in=[TicketStatus.CS_REJECTED, TicketStatus.TECH_REJECTED]).count()
    ticket_today_created = await ticket_query.filter(created_at__gte=today_start, created_at__lt=tomorrow_start).count()
    ticket_today_done = await ticket_query.filter(
        status=TicketStatus.DONE,
        finished_at__gte=today_start,
        finished_at__lt=tomorrow_start,
    ).count()
    ticket_active = ticket_pending_review + ticket_tech_processing + ticket_field_verification + ticket_pending_close
    ticket_today_completion_rate = round(ticket_today_done * 100 / ticket_today_created, 1) if ticket_today_created else 0
    register_pending = await PartnerRegistration.filter(status=PartnerRegisterStatus.PENDING).count() if is_global else 0
    register_approved = await PartnerRegistration.filter(status=PartnerRegisterStatus.APPROVED).count() if is_global else 0
    register_rejected = await PartnerRegistration.filter(status=PartnerRegisterStatus.REJECTED).count() if is_global else 0
    user_total = await User.all().count() if is_global else 0
    auditlog_today = await AuditLog.filter(created_at__gte=today_start, created_at__lt=tomorrow_start).count() if is_global else 0
    auditlog_failed_today = (
        await AuditLog.filter(created_at__gte=today_start, created_at__lt=tomorrow_start, status__gte=400).count()
        if is_global
        else 0
    )
    auditlog_archived = await AuditLog.filter(is_archived=True).count() if is_global else 0

    document_query = SkillKnowDocument.all() if is_global else SkillKnowDocument.filter(owner_id=user_id)
    document_total = await document_query.count()
    document_completed = await document_query.filter(status=SkillKnowDocumentStatus.COMPLETED).count()
    document_processing = await document_query.filter(
        status__in=[SkillKnowDocumentStatus.PENDING, SkillKnowDocumentStatus.PROCESSING]
    ).count()
    document_failed = await document_query.filter(status=SkillKnowDocumentStatus.FAILED).count()
    document_today = await document_query.filter(created_at__gte=today_start, created_at__lt=tomorrow_start).count()
    document_health_rate = round(document_completed * 100 / document_total, 1) if document_total else 100
    chunk_total = await SkillKnowDocumentChunk.all().count() if is_global else 0
    conversation_today = (
        await SkillKnowConversation.filter(created_at__gte=today_start, created_at__lt=tomorrow_start).count()
        if is_global
        else await SkillKnowConversation.filter(
            owner_id=user_id, created_at__gte=today_start, created_at__lt=tomorrow_start
        ).count()
    )
    message_today = await SkillKnowMessage.filter(created_at__gte=today_start, created_at__lt=tomorrow_start).count() if is_global else 0

    share_active = (
        await WebDavShareLink.filter(is_active=True, expire_time__gte=now).count()
        if is_global
        else await WebDavShareLink.filter(created_by=user_id, is_active=True, expire_time__gte=now).count()
    )
    share_expired = (
        await WebDavShareLink.filter(Q(is_active=False) | Q(expire_time__lt=now)).count()
        if is_global
        else await WebDavShareLink.filter(Q(created_by=user_id), Q(is_active=False) | Q(expire_time__lt=now)).count()
    )

    terminal_company_count = 0
    terminal_total = 0
    terminal_auth_expiring = 0
    terminal_maintain_expiring = 0
    terminal_latest_reported_at = None
    if is_global:
        expire_limit = now + timedelta(days=30)
        latest_rows = []
        try:
            conn = Tortoise.get_connection("mysql")
            latest_rows = await conn.execute_query_dict(
                """
                SELECT t.company_name, t.auth_expire_at, t.maintain_expire_at, t.terminal_stats, t.reported_at
                FROM terminal_auth_report t
                INNER JOIN (
                    SELECT company_name, MAX(reported_at) AS max_reported_at
                    FROM terminal_auth_report
                    GROUP BY company_name
                ) latest_time ON latest_time.company_name = t.company_name AND latest_time.max_reported_at = t.reported_at
                INNER JOIN (
                    SELECT company_name, reported_at, MAX(id) AS max_id
                    FROM terminal_auth_report
                    GROUP BY company_name, reported_at
                ) latest_id ON latest_id.company_name = t.company_name AND latest_id.reported_at = t.reported_at AND latest_id.max_id = t.id
                ORDER BY t.reported_at DESC
                """
            )
        except Exception as exc:
            logger.warning("[api.workbench_stats] terminal_latest_query_failed error={}", str(exc))
            latest_rows = []
        terminal_company_count = len(latest_rows)
        for report in latest_rows:
            stats_map = report.get("terminal_stats") or {}
            if isinstance(stats_map, str):
                try:
                    stats_map = json.loads(stats_map)
                except json.JSONDecodeError:
                    stats_map = {}
            terminal_total += sum(int(value or 0) for value in stats_map.values())
            auth_expire_at = report.get("auth_expire_at")
            maintain_expire_at = report.get("maintain_expire_at")
            if auth_expire_at and now <= auth_expire_at <= expire_limit:
                terminal_auth_expiring += 1
            if maintain_expire_at and now <= maintain_expire_at <= expire_limit:
                terminal_maintain_expiring += 1
        if latest_rows and latest_rows[0].get("reported_at"):
            terminal_latest_reported_at = latest_rows[0]["reported_at"].isoformat()

    data = {
        "ticket_total": ticket_total,
        "ticket_active": ticket_active,
        "ticket_pending_review": ticket_pending_review,
        "ticket_tech_processing": ticket_tech_processing,
        "ticket_field_verification": ticket_field_verification,
        "ticket_pending_close": ticket_pending_close,
        "ticket_done": ticket_done,
        "ticket_rejected": ticket_rejected,
        "ticket_today_created": ticket_today_created,
        "ticket_today_done": ticket_today_done,
        "ticket_today_completion_rate": ticket_today_completion_rate,
        "register_pending": register_pending,
        "register_approved": register_approved,
        "register_rejected": register_rejected,
        "user_total": user_total,
        "auditlog_today": auditlog_today,
        "auditlog_failed_today": auditlog_failed_today,
        "auditlog_archived": auditlog_archived,
        "document_total": document_total,
        "document_completed": document_completed,
        "document_processing": document_processing,
        "document_failed": document_failed,
        "document_today": document_today,
        "document_health_rate": document_health_rate,
        "chunk_total": chunk_total,
        "conversation_today": conversation_today,
        "message_today": message_today,
        "share_active": share_active,
        "share_expired": share_expired,
        "terminal_company_count": terminal_company_count,
        "terminal_total": terminal_total,
        "terminal_auth_expiring": terminal_auth_expiring,
        "terminal_maintain_expiring": terminal_maintain_expiring,
        "terminal_latest_reported_at": terminal_latest_reported_at,
    }
    try:
        await execute_redis("setex", cache_key, 120, json.dumps(data, ensure_ascii=False))
    except Exception as exc:
        logger.warning("[api.workbench_stats] cache_write_failed key={} error={}", cache_key, str(exc))
    return Success(data=data)


@router.get("/userinfo", summary="查看用户信息", dependencies=[DependAuth])
async def get_userinfo():
    user_id = CTX_USER_ID.get()
    user_obj = await user_controller.get(id=user_id)
    data = await user_obj.to_dict(m2m=True, exclude_fields=["password"])
    data["avatar"] = "https://avatars.githubusercontent.com/u/54677442?v=4"
    return Success(data=data)


@router.get("/usermenu", summary="查看用户菜单", dependencies=[DependAuth])
async def get_user_menu():
    user_id = CTX_USER_ID.get()
    cache_key = f"perm:menu:user:{user_id}:v2"
    try:
        cached = await execute_redis("get", cache_key)
        if cached:
            return Success(data=json.loads(cached))
    except Exception as exc:
        logger.warning("[api.user_menu] cache_read_failed key={} error={}", cache_key, str(exc))

    user_obj = await User.filter(id=user_id).first()
    menus: list[Menu] = []
    if user_obj.is_superuser:
        menus = await Menu.all()
    else:
        role_objs: list[Role] = await user_obj.roles
        for role_obj in role_objs:
            menu = await role_obj.menus
            menus.extend(menu)
        menus = list(set(menus))
    parent_menus: list[Menu] = []
    for menu in menus:
        if menu.parent_id == 0:
            parent_menus.append(menu)
    res = []
    for parent_menu in parent_menus:
        parent_menu_dict = await parent_menu.to_dict()
        parent_menu_dict["children"] = []
        for menu in menus:
            if menu.parent_id == parent_menu.id:
                parent_menu_dict["children"].append(await menu.to_dict())
        res.append(parent_menu_dict)
    try:
        await execute_redis("setex", cache_key, 600, json.dumps(res, ensure_ascii=False))
    except Exception as exc:
        logger.warning("[api.user_menu] cache_write_failed key={} error={}", cache_key, str(exc))
    return Success(data=res)


@router.get("/userapi", summary="查看用户API", dependencies=[DependAuth])
async def get_user_api():
    user_id = CTX_USER_ID.get()
    cache_key = f"perm:api:user:{user_id}:v2"
    try:
        cached = await execute_redis("get", cache_key)
        if cached:
            return Success(data=json.loads(cached))
    except Exception as exc:
        logger.warning("[api.user_api] cache_read_failed key={} error={}", cache_key, str(exc))

    user_obj = await User.filter(id=user_id).first()
    if user_obj.is_superuser:
        api_objs: list[Api] = await Api.all()
        apis = [api.method.lower() + api.path for api in api_objs]
        try:
            await execute_redis("setex", cache_key, 600, json.dumps(apis, ensure_ascii=False))
        except Exception as exc:
            logger.warning("[api.user_api] cache_write_failed key={} error={}", cache_key, str(exc))
        return Success(data=apis)
    role_objs: list[Role] = await user_obj.roles
    apis = []
    for role_obj in role_objs:
        api_objs: list[Api] = await role_obj.apis
        apis.extend([api.method.lower() + api.path for api in api_objs])
    apis = list(set(apis))
    try:
        await execute_redis("setex", cache_key, 600, json.dumps(apis, ensure_ascii=False))
    except Exception as exc:
        logger.warning("[api.user_api] cache_write_failed key={} error={}", cache_key, str(exc))
    return Success(data=apis)


@router.post("/update_password", summary="修改密码", dependencies=[DependAuth])
async def update_user_password(req_in: UpdatePassword):
    user_id = CTX_USER_ID.get()
    user = await user_controller.get(user_id)
    verified = verify_password(req_in.old_password, user.password)
    if not verified:
        return Fail(msg="旧密码验证错误！")
    await user_controller.validate_password_policy(req_in.new_password)
    user.password = get_password_hash(req_in.new_password)
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    await user.save()
    await user_controller.clear_auth_cache(user.id)
    return Success(msg="修改成功")
