from fastapi import APIRouter

from app.core.dependency import DependPermission

from .apis import apis_router
from .auditlog import auditlog_router
from .base import base_router
from .depts import depts_router
from .menus import menus_router
from .monitor import monitor_router
from .notices import notices_router
from .partner import partner_router
from .rd_tasks import rd_tasks_router
from .roles import roles_router
from .settings import settings_router
from .skill_know import skill_know_router
from .terminal import terminal_public_router, terminal_router
from .tickets import tickets_router
from .users import users_router
from .webdav import webdav_public_router, webdav_router

v1_router = APIRouter()

v1_router.include_router(base_router, prefix="/base")
v1_router.include_router(partner_router, prefix="/partner")
v1_router.include_router(terminal_public_router, prefix="/public/terminal")
v1_router.include_router(webdav_public_router, prefix="/public/webdav")
v1_router.include_router(users_router, prefix="/user", dependencies=[DependPermission])
v1_router.include_router(roles_router, prefix="/role", dependencies=[DependPermission])
v1_router.include_router(menus_router, prefix="/menu", dependencies=[DependPermission])
v1_router.include_router(apis_router, prefix="/api", dependencies=[DependPermission])
v1_router.include_router(notices_router, prefix="/notice", dependencies=[DependPermission])
v1_router.include_router(depts_router, prefix="/dept", dependencies=[DependPermission])
v1_router.include_router(auditlog_router, prefix="/auditlog", dependencies=[DependPermission])
v1_router.include_router(tickets_router, prefix="/ticket", dependencies=[DependPermission])
v1_router.include_router(rd_tasks_router, prefix="/rd-task", dependencies=[DependPermission])
v1_router.include_router(settings_router, prefix="/settings", dependencies=[DependPermission])
v1_router.include_router(monitor_router, prefix="/monitor", dependencies=[DependPermission])
v1_router.include_router(webdav_router, prefix="/webdav", dependencies=[DependPermission])
v1_router.include_router(skill_know_router, prefix="/skill-know", dependencies=[DependPermission])
v1_router.include_router(terminal_router, prefix="/terminal", dependencies=[DependPermission])
