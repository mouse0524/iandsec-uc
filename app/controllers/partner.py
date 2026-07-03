from datetime import datetime

from fastapi import HTTPException
from tortoise.expressions import Q
from tortoise.transactions import atomic

from app.log import logger
from app.models.admin import PartnerRegistration, Role, User
from app.models.enums import PartnerLevel, PartnerRegisterStatus, RegisterType
from app.controllers.dept import dept_controller
from app.controllers.mail import mail_controller
from app.controllers.user import user_controller
from app.schemas.partner import PartnerRegisterIn
from app.schemas.users import UserCreate
from app.utils.password import get_password_hash


class PartnerController:
    @staticmethod
    async def _check_uniqueness(
        *,
        email: str,
        username: str,
        phone: str,
        hardware_id: str | None = None,
        exclude_registration_id: int | None = None,
    ) -> None:
        if await User.filter(email=email).exists():
            raise HTTPException(status_code=400, detail="邮箱已被注册")
        if await User.filter(username=username).exists():
            raise HTTPException(status_code=400, detail="用户名已存在")
        if await User.filter(phone=phone).exists():
            raise HTTPException(status_code=400, detail="手机号已被注册")
        if hardware_id and await User.filter(hardware_id=hardware_id).exists():
            raise HTTPException(status_code=400, detail="产品硬件ID已被注册")

        pending_q = Q(status=PartnerRegisterStatus.PENDING)
        if exclude_registration_id:
            pending_q &= ~Q(id=exclude_registration_id)

        if await PartnerRegistration.filter(pending_q & Q(email=email)).exists():
            raise HTTPException(status_code=400, detail="该邮箱已有待审核申请")
        if await PartnerRegistration.filter(pending_q & Q(username=username)).exists():
            raise HTTPException(status_code=400, detail="该用户名已有待审核申请")
        if await PartnerRegistration.filter(pending_q & Q(phone=phone)).exists():
            raise HTTPException(status_code=400, detail="该手机号已有待审核申请")
        if hardware_id and await PartnerRegistration.filter(
            pending_q & Q(hardware_id=hardware_id)
        ).exists():
            raise HTTPException(status_code=400, detail="该产品硬件ID已有待审核申请")

    @staticmethod
    async def has_pending_registration(
        *,
        email: str | None = None,
        phone: str | None = None,
        username: str | None = None,
        hardware_id: str | None = None,
    ) -> bool:
        q = Q(status=PartnerRegisterStatus.PENDING)
        condition = Q()
        has_any = False
        if email:
            condition |= Q(email=email.strip().lower())
            has_any = True
        if phone:
            condition |= Q(phone=phone.strip())
            has_any = True
        if username:
            condition |= Q(username=username.strip())
            has_any = True
        if hardware_id:
            condition |= Q(hardware_id=hardware_id.strip())
            has_any = True
        if not has_any:
            return False
        return await PartnerRegistration.filter(q & condition).exists()

    async def register(self, payload: PartnerRegisterIn) -> PartnerRegistration:
        email = payload.email.strip().lower()
        username = email
        phone = payload.phone.strip()
        register_type = payload.register_type
        hardware_id = (payload.hardware_id or "").strip() or None

        if register_type == RegisterType.USER and not hardware_id:
            raise HTTPException(status_code=400, detail="用户注册必须填写产品硬件ID")

        await self._check_uniqueness(
            email=email, username=username, phone=phone, hardware_id=hardware_id
        )

        await user_controller.validate_password_policy(payload.password)

        password_hash = get_password_hash(payload.password)
        return await PartnerRegistration.create(
            register_type=register_type,
            company_name=payload.company_name,
            contact_name=payload.contact_name,
            email=email,
            phone=phone,
            username=username,
            hardware_id=hardware_id,
            password_hash=password_hash,
        )

    @atomic()
    async def _review_approve(self, register_obj: PartnerRegistration) -> None:
        username = register_obj.username or register_obj.email.strip().lower()
        register_obj.username = username

        role_name = "渠道商" if register_obj.register_type == RegisterType.CHANNEL else "用户"
        role = await Role.filter(name=role_name).first()
        if not role and role_name == "渠道商":
            role = await Role.filter(name="代理商").first()
        if not role:
            raise HTTPException(status_code=500, detail=f"{role_name}角色不存在")

        await self._check_uniqueness(
            email=register_obj.email,
            username=username,
            phone=register_obj.phone,
            hardware_id=register_obj.hardware_id,
            exclude_registration_id=register_obj.id,
        )

        parent_name = "渠道部门" if register_obj.register_type == RegisterType.CHANNEL else "用户部门"
        parent_dept = await dept_controller.get_or_create(name=parent_name, parent_id=0, desc="注册审核自动创建")

        child_name = (register_obj.company_name or "").strip() or register_obj.contact_name
        child_desc = f"{'渠道商' if register_obj.register_type == RegisterType.CHANNEL else '用户'}注册自动创建"
        child_dept = await dept_controller.get_or_create(
            name=child_name,
            parent_id=parent_dept.id,
            desc=child_desc,
            channel_level=PartnerLevel.UNSIGNED if register_obj.register_type == RegisterType.CHANNEL else None,
        )
        logger.info(
            "[partner.review] dept_ready register_id={} dept_id={} dept_name={}",
            register_obj.id,
            child_dept.id,
            child_dept.name,
        )

        user_create = UserCreate(
            username=username,
            email=register_obj.email,
            alias=register_obj.contact_name,
            company_name=register_obj.company_name,
            phone=register_obj.phone,
            hardware_id=register_obj.hardware_id,
            password="placeholder",
            is_active=True,
            is_superuser=False,
            dept_id=child_dept.id,
        )
        user = await user_controller.create_user_with_hash(
            obj_in=user_create,
            password_hash=register_obj.password_hash,
            role_ids=[role.id],
        )
        logger.info("[partner.review] user_created user_id={} username={}", user.id, user.username)
        register_obj.status = PartnerRegisterStatus.APPROVED

    async def review(
        self, *, register_id: int, reviewer_id: int, approved: bool, comment: str | None
    ) -> PartnerRegistration:
        logger.info(
            "[partner.review] start register_id={} reviewer_id={} approved={} comment={}",
            register_id,
            reviewer_id,
            approved,
            comment,
        )
        register_obj = await PartnerRegistration.get(id=register_id)
        if register_obj.status != PartnerRegisterStatus.PENDING:
            raise HTTPException(status_code=400, detail="该申请已审核")

        register_obj.reviewer_id = reviewer_id
        register_obj.review_comment = comment
        register_obj.reviewed_at = datetime.now()

        if approved:
            await self._review_approve(register_obj)
        else:
            register_obj.status = PartnerRegisterStatus.REJECTED

        await register_obj.save()

        try:
            await mail_controller.send_register_review_notice(
                to_email=register_obj.email,
                contact_name=register_obj.contact_name,
                register_type=register_obj.register_type,
                approved=approved,
                reason=comment,
            )
        except Exception:
            logger.warning(
                "[partner.review] email_send_failed register_id={} email={}",
                register_obj.id,
                register_obj.email,
                exc_info=True,
            )

        logger.info(
            "[partner.review] success register_id={} status={} reviewer_id={}",
            register_obj.id,
            register_obj.status,
            reviewer_id,
        )

        return register_obj


partner_controller = PartnerController()
