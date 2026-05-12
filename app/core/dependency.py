from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request

from app.core.ctx import CTX_USER_ID, CTX_USER_NAME
from app.log import logger
from app.models import Role, User
from app.settings import settings


TOKEN_VERSION_CLAIM = "token_version"


class AuthControl:
    @classmethod
    async def is_authed(cls, token: str = Header(..., description="token验证")) -> Optional["User"]:
        try:
            decode_data = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                issuer=settings.JWT_ISSUER,
                audience=settings.JWT_AUDIENCE,
                options={"require": ["exp", "iat", "iss", "aud", "jti"]},
            )
            user_id = decode_data.get("user_id")
            user = await User.filter(id=user_id).first()
            if not user:
                raise HTTPException(status_code=401, detail="Authentication failed")
            if not user.is_active:
                raise HTTPException(status_code=401, detail="账号已禁用")
            token_version = decode_data.get(TOKEN_VERSION_CLAIM)
            if token_version is not None and int(token_version) != int(getattr(user, "token_version", 0) or 0):
                raise HTTPException(status_code=401, detail="登录状态已失效")
            CTX_USER_ID.set(int(user_id))
            CTX_USER_NAME.set(user.username or "")
            return user
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="无效的Token")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="登录已过期")
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("[auth] token verification failed error={}", repr(exc))
            raise HTTPException(status_code=401, detail="认证失败")


class PermissionControl:
    @classmethod
    async def has_permission(cls, request: Request, current_user: User = Depends(AuthControl.is_authed)) -> None:
        if current_user.is_superuser:
            return
        method = request.method
        path = request.url.path
        roles: list[Role] = await current_user.roles
        if not roles:
            raise HTTPException(status_code=403, detail="The user is not bound to a role")
        apis = [await role.apis for role in roles]
        permission_apis = list(set((api.method, api.path) for api in sum(apis, [])))
        # path = "/api/v1/auth/userinfo"
        # method = "GET"
        if (method, path) not in permission_apis:
            raise HTTPException(status_code=403, detail=f"Permission denied method:{method} path:{path}")


DependAuth = Depends(AuthControl.is_authed)
DependPermission = Depends(PermissionControl.has_permission)
