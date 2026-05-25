from datetime import datetime, timedelta
import json
from typing import List, Optional

from fastapi.exceptions import HTTPException

from app.core.crud import CRUDBase
from app.core.redis_client import execute_redis
from app.log import logger
from app.controllers.mail import mail_controller
from app.models.admin import User
from app.schemas.login import CredentialsSchema
from app.schemas.users import UserCreate, UserUpdate
from app.utils.password import generate_strong_password, get_password_hash, is_password_strong, verify_password

from .role import role_controller
from .system_setting import system_setting_controller


class UserController(CRUDBase[User, UserCreate, UserUpdate]):
    USER_BASIC_CACHE_TTL_SECONDS = 600
    USER_AUTH_CACHE_TTL_SECONDS = 600
    def __init__(self):
        super().__init__(model=User)

    async def get_by_email(self, email: str) -> Optional[User]:
        return await self.model.filter(email=email).first()

    async def get_user_basic(self, user_id: int) -> dict:
        cache_key = f"user:basic:{user_id}"
        try:
            cached = await execute_redis("get", cache_key)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("[user.basic] cache_read_failed key={} error={}", cache_key, str(exc))

        user_obj = await self.get(id=user_id)
        roles = await user_obj.roles
        data = {
            "id": user_obj.id,
            "username": user_obj.username,
            "alias": user_obj.alias,
            "email": user_obj.email,
            "is_superuser": user_obj.is_superuser,
            "role_names": [role.name for role in roles],
        }
        try:
            await execute_redis("setex", cache_key, self.USER_BASIC_CACHE_TTL_SECONDS, json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            logger.warning("[user.basic] cache_write_failed key={} error={}", cache_key, str(exc))
        return data

    async def get_auth_user(self, user_id: int) -> User | None:
        cache_key = f"auth:user:{user_id}:v1"
        try:
            cached = await execute_redis("get", cache_key)
            if cached:
                data = json.loads(cached)
                user = await self.model.filter(id=user_id).first()
                if not user:
                    await execute_redis("delete", cache_key)
                    return None
                return user
        except Exception as exc:
            logger.warning("[user.auth_cache] read_failed key={} error={}", cache_key, str(exc))

        user = await self.model.filter(id=user_id).first()
        if not user:
            return None
        data = {
            "id": user.id,
            "username": user.username,
            "alias": user.alias,
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "token_version": int(getattr(user, "token_version", 0) or 0),
        }
        try:
            await execute_redis("setex", cache_key, self.USER_AUTH_CACHE_TTL_SECONDS, json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            logger.warning("[user.auth_cache] write_failed key={} error={}", cache_key, str(exc))
        return user

    async def get_by_username(self, username: str) -> Optional[User]:
        return await self.model.filter(username=username).first()

    async def create_user(self, obj_in: UserCreate) -> User:
        logger.info("[user.create] start username={} email={} dept_id={}", obj_in.username, obj_in.email, obj_in.dept_id)
        await self.validate_password_policy(obj_in.password)
        obj_in.password = get_password_hash(password=obj_in.password)
        obj = await self.create(obj_in)
        if obj_in.role_ids:
            await self.update_roles(obj, obj_in.role_ids)
        logger.info("[user.create] success user_id={} username={}", obj.id, obj.username)
        return obj

    async def create_user_with_hash(self, obj_in: UserCreate, password_hash: str, role_ids: list[int] | None = None) -> User:
        logger.info("[user.create_with_hash] start username={} email={} dept_id={}", obj_in.username, obj_in.email, obj_in.dept_id)
        obj_in.password = password_hash
        obj = await self.create(obj_in)
        if role_ids:
            await self.update_roles(obj, role_ids)
        logger.info("[user.create_with_hash] success user_id={} username={}", obj.id, obj.username)
        return obj

    async def update_last_login(self, id: int) -> None:
        user = await self.model.get(id=id)
        user.last_login = datetime.now()
        await user.save()
        logger.info("[user.login] update_last_login user_id={} username={}", user.id, user.username)

    @staticmethod
    def inactive_auto_disable_enabled(config: dict) -> bool:
        return bool(config.get("inactive_user_auto_disable_enabled", True))

    @staticmethod
    def inactive_auto_disable_days(config: dict) -> int:
        try:
            days = int(config.get("inactive_user_auto_disable_days", 30) or 30)
        except (TypeError, ValueError):
            days = 30
        return min(3650, max(1, days))

    @staticmethod
    def _login_inactivity_reference(user: User) -> datetime | None:
        return getattr(user, "last_login", None) or getattr(user, "created_at", None)

    def is_login_inactive(self, user: User, *, config: dict, now: datetime | None = None) -> bool:
        if not self.inactive_auto_disable_enabled(config):
            return False
        if not getattr(user, "is_active", True) or getattr(user, "is_superuser", False):
            return False

        reference = self._login_inactivity_reference(user)
        if reference is None:
            return False

        now = now or datetime.now(tz=reference.tzinfo)
        if reference.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=reference.tzinfo)
        elif reference.tzinfo is None and now.tzinfo is not None:
            reference = reference.replace(tzinfo=now.tzinfo)

        cutoff = now - timedelta(days=self.inactive_auto_disable_days(config))
        return reference < cutoff

    async def disable_if_login_inactive(
        self,
        user: User,
        *,
        config: dict,
        now: datetime | None = None,
    ) -> bool:
        if not self.is_login_inactive(user, config=config, now=now):
            return False

        user.is_active = False
        user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
        await user.save()
        await self.clear_auth_cache(user.id)
        logger.warning(
            "[user.inactive] auto_disabled user_id={} username={} days={}",
            user.id,
            user.username,
            self.inactive_auto_disable_days(config),
        )
        return True

    async def authenticate(self, credentials: CredentialsSchema) -> Optional["User"]:
        logger.info("[user.auth] start username={}", credentials.username)
        user = await self.model.filter(username=credentials.username).first()
        if not user:
            logger.warning("[user.auth] user_not_found username={}", credentials.username)
            raise HTTPException(status_code=400, detail="无效的用户名")
        verified = verify_password(credentials.password, user.password)
        if not verified:
            logger.warning("[user.auth] wrong_password username={} user_id={}", credentials.username, user.id)
            raise HTTPException(status_code=400, detail="密码错误!")
        if not user.is_active:
            logger.warning("[user.auth] disabled username={} user_id={}", user.username, user.id)
            raise HTTPException(status_code=400, detail="用户已被禁用")
        config = await system_setting_controller.get_public_config()
        if await self.disable_if_login_inactive(user, config=config):
            days = self.inactive_auto_disable_days(config)
            raise HTTPException(status_code=400, detail=f"用户超过{days}天未登录，已自动禁用")
        logger.info("[user.auth] success username={} user_id={}", user.username, user.id)
        return user

    async def update_roles(self, user: User, role_ids: List[int]) -> None:
        logger.info("[user.role] update start user_id={} role_ids={}", user.id, role_ids)
        await user.roles.clear()
        for role_id in role_ids:
            role_obj = await role_controller.get(id=role_id)
            await user.roles.add(role_obj)
        logger.info("[user.role] update success user_id={} role_count={}", user.id, len(role_ids))
        await self.clear_permission_cache(user.id)
        await self.clear_admin_flag_cache(user.id)

    async def reset_password(self, user_id: int) -> str:
        logger.info("[user.reset_password] start user_id={}", user_id)
        user_obj = await self.get(id=user_id)
        if user_obj.is_superuser:
            logger.warning("[user.reset_password] deny_superuser user_id={}", user_id)
            raise HTTPException(status_code=403, detail="不允许重置超级管理员密码")
        if not user_obj.email:
            raise HTTPException(status_code=400, detail="该用户未配置邮箱，无法发送重置通知")
        config = await system_setting_controller.get_public_config()
        min_length = int(config.get("password_min_length", 8) or 8)
        min_categories = len(config.get("password_required_categories") or ["letter", "digit"])
        temp_password = generate_strong_password(min_length=max(min_length, 10), min_categories=min_categories)
        user_obj.password = get_password_hash(password=temp_password)
        user_obj.token_version = int(getattr(user_obj, "token_version", 0) or 0) + 1
        await user_obj.save()
        await self.clear_auth_cache(user_obj.id)
        await mail_controller.send_admin_reset_password_notice(to_user=user_obj, temp_password=temp_password)
        logger.info("[user.reset_password] success user_id={} username={}", user_obj.id, user_obj.username)
        return temp_password

    async def validate_password_policy(self, raw_password: str) -> None:
        config = await system_setting_controller.get_public_config()
        min_length = int(config.get("password_min_length", 8) or 8)
        min_categories = len(config.get("password_required_categories") or ["letter", "digit"])
        ok, message = is_password_strong(raw_password, min_length=min_length, min_categories=min_categories)
        if not ok:
            raise HTTPException(status_code=400, detail=message)

    @staticmethod
    async def clear_permission_cache(user_id: int) -> None:
        keys = [
            f"perm:menu:user:{user_id}:v1",
            f"perm:api:user:{user_id}:v1",
            f"perm:menu:user:{user_id}:v2",
            f"perm:api:user:{user_id}:v2",
        ]
        try:
            await execute_redis("delete", *keys)
        except Exception as exc:
            logger.warning("[user.cache] clear_perm_failed user_id={} error={}", user_id, str(exc))

    @staticmethod
    async def clear_admin_flag_cache(user_id: int) -> None:
        try:
            await execute_redis("delete", f"perm:is_admin:user:{user_id}:v1")
        except Exception as exc:
            logger.warning("[user.cache] clear_admin_failed user_id={} error={}", user_id, str(exc))

    @staticmethod
    async def clear_user_basic_cache(user_id: int) -> None:
        try:
            await execute_redis("delete", f"user:basic:{user_id}", f"ticket:prefill:user:{user_id}:v1")
        except Exception as exc:
            logger.warning("[user.cache] clear_basic_failed user_id={} error={}", user_id, str(exc))

    @staticmethod
    async def clear_auth_cache(user_id: int) -> None:
        try:
            await execute_redis("delete", f"auth:user:{user_id}:v1")
        except Exception as exc:
            logger.warning("[user.cache] clear_auth_failed user_id={} error={}", user_id, str(exc))

    @staticmethod
    async def clear_all_permission_cache() -> None:
        try:
            keys: set[str] = set()
            for pattern in ("perm:menu:user:*", "perm:api:user:*"):
                cursor = 0
                while True:
                    cursor, batch = await execute_redis("scan", cursor=cursor, match=pattern, count=500)
                    keys.update(batch or [])
                    if int(cursor or 0) == 0:
                        break
            if keys:
                await execute_redis("delete", *keys)
        except Exception as exc:
            logger.warning("[user.cache] clear_all_perm_failed error={}", str(exc))


user_controller = UserController()
