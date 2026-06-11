from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.api import api_router
from app.controllers.api import api_controller
from app.controllers.user import UserCreate, user_controller
from app.core.exceptions import (
    DoesNotExist,
    DoesNotExistHandle,
    HTTPException,
    HttpExcHandle,
    IntegrityError,
    IntegrityHandle,
    RequestValidationError,
    RequestValidationHandle,
    ResponseValidationError,
    ResponseValidationHandle,
)
from app.log import logger
from app.models.admin import Api, Menu, Role, SkillKnowSystemConfig
from app.schemas.menus import MenuType
from app.settings.config import settings

from .middlewares import BackGroundTaskMiddleware, HttpAuditLogMiddleware


def _default_basic_api_filter():
    return Q(tags="基础模块") | Q(path__in=_default_basic_api_paths())


def _default_basic_api_paths() -> list[str]:
    return [
        "/api/v1/base/update_password",
        "/api/v1/base/workbench_stats",
    ]


def _monitor_api_paths() -> list[str]:
    return [
        "/api/v1/monitor/overview",
        "/api/v1/monitor/resources",
        "/api/v1/monitor/mysql",
        "/api/v1/monitor/redis",
        "/api/v1/monitor/redis/clear",
    ]


def _terminal_api_paths() -> list[str]:
    return [
        "/api/v1/terminal/auth/list",
        "/api/v1/terminal/auth/latest",
        "/api/v1/terminal/upgrade/config",
    ]


def _webdav_password_api_paths() -> list[str]:
    return [
        "/api/v1/webdav/ops-password",
        "/api/v1/webdav/replace-decrypt-password",
    ]


def _ticket_redmine_api_paths() -> list[str]:
    return [
        "/api/v1/ticket/redmine/push",
        "/api/v1/ticket/redmine/pull",
        "/api/v1/settings/redmine/metadata",
    ]


def make_middlewares():
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=settings.CORS_ALLOW_METHODS,
            allow_headers=settings.CORS_ALLOW_HEADERS,
        ),
        Middleware(BackGroundTaskMiddleware),
        Middleware(
            HttpAuditLogMiddleware,
            methods=["GET", "POST", "PUT", "DELETE"],
            exclude_paths=[
                "/api/v1/base/access_token",
                "/docs",
                "/openapi.json",
            ],
        ),
    ]
    return middleware


def register_exceptions(app: FastAPI):
    app.add_exception_handler(DoesNotExist, DoesNotExistHandle)
    app.add_exception_handler(HTTPException, HttpExcHandle)
    app.add_exception_handler(IntegrityError, IntegrityHandle)
    app.add_exception_handler(RequestValidationError, RequestValidationHandle)
    app.add_exception_handler(ResponseValidationError, ResponseValidationHandle)


def register_routers(app: FastAPI, prefix: str = "/api"):
    app.include_router(api_router, prefix=prefix)


async def init_superuser():
    user = await user_controller.model.exists()
    if not user:
        if not settings.INITIAL_ADMIN_PASSWORD:
            raise RuntimeError("INITIAL_ADMIN_PASSWORD must be set before initializing the first superuser")
        await user_controller.create_user(
            UserCreate(
                username=settings.INITIAL_ADMIN_USERNAME,
                email=settings.INITIAL_ADMIN_EMAIL,
                password=settings.INITIAL_ADMIN_PASSWORD,
                is_active=True,
                is_superuser=True,
            )
        )


async def init_menus():
    menus = await Menu.exists()
    if not menus:
        parent_menu = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="系统管理",
            path="/system",
            order=1,
            parent_id=0,
            icon="carbon:gui-management",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/system/user",
        )
        children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="用户管理",
                path="user",
                order=1,
                parent_id=parent_menu.id,
                icon="material-symbols:person-outline-rounded",
                is_hidden=False,
                component="/system/user",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="角色管理",
                path="role",
                order=2,
                parent_id=parent_menu.id,
                icon="carbon:user-role",
                is_hidden=False,
                component="/system/role",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="菜单管理",
                path="menu",
                order=3,
                parent_id=parent_menu.id,
                icon="material-symbols:list-alt-outline",
                is_hidden=False,
                component="/system/menu",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="API管理",
                path="api",
                order=4,
                parent_id=parent_menu.id,
                icon="ant-design:api-outlined",
                is_hidden=False,
                component="/system/api",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="部门管理",
                path="dept",
                order=5,
                parent_id=parent_menu.id,
                icon="mingcute:department-line",
                is_hidden=False,
                component="/system/dept",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="审计日志",
                path="auditlog",
                order=6,
                parent_id=parent_menu.id,
                icon="ph:clipboard-text-bold",
                is_hidden=False,
                component="/system/auditlog",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="系统设置",
                path="settings",
                order=7,
                parent_id=parent_menu.id,
                icon="material-symbols:settings-outline",
                is_hidden=False,
                component="/system/settings",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="全局通知",
                path="notice",
                order=8,
                parent_id=parent_menu.id,
                icon="material-symbols:notifications-active-outline-rounded",
                is_hidden=False,
                component="/system/notice",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="系统监控",
                path="monitor",
                order=9,
                parent_id=parent_menu.id,
                icon="material-symbols:monitor-heart-outline-rounded",
                is_hidden=False,
                component="/system/monitor",
                keepalive=False,
            ),
        ]
        await Menu.bulk_create(children_menu)
        await Menu.create(
            menu_type=MenuType.MENU,
            name="一级菜单",
            path="/top-menu",
            order=2,
            parent_id=0,
            icon="material-symbols:featured-play-list-outline",
            is_hidden=False,
            component="/top-menu",
            keepalive=False,
            redirect="",
        )

    ticket_parent = await Menu.filter(path="/ticket").first()
    if not ticket_parent:
        ticket_parent = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="工单中心",
            path="/ticket",
            order=3,
            parent_id=0,
            icon="tabler:ticket",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/ticket/submit",
        )

    ticket_children = [
        {
            "name": "提交工单",
            "path": "submit",
            "order": 1,
            "icon": "material-symbols:upload-file-outline",
            "component": "/ticket/submit",
        },
        {
            "name": "我的工单",
            "path": "my",
            "order": 2,
            "icon": "mdi:ticket-account",
            "component": "/ticket/my",
        },
        {
            "name": "工单审核",
            "path": "review",
            "order": 3,
            "icon": "material-symbols:checklist",
            "component": "/ticket/review",
        },
        {
            "name": "技术处理",
            "path": "tech",
            "order": 4,
            "icon": "mdi:tools",
            "component": "/ticket/tech",
        },
    ]
    for child in ticket_children:
        exists = await Menu.filter(parent_id=ticket_parent.id, path=child["path"]).exists()
        if not exists:
            await Menu.create(
                menu_type=MenuType.MENU,
                parent_id=ticket_parent.id,
                is_hidden=False,
                keepalive=False,
                redirect="",
                **child,
            )

    partner_parent = await Menu.filter(path="/partner").first()
    if not partner_parent:
        partner_parent = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="代理商中心",
            path="/partner",
            order=4,
            parent_id=0,
            icon="mdi:account-group-outline",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/partner/review",
        )

    if not await Menu.filter(parent_id=partner_parent.id, path="review").exists():
        await Menu.create(
            menu_type=MenuType.MENU,
            name="注册审核",
            path="review",
            order=1,
            parent_id=partner_parent.id,
            icon="mdi:file-document-edit-outline",
            is_hidden=False,
            component="/partner/review",
            keepalive=False,
            redirect="",
        )

    if not await Menu.filter(component="/system/settings").exists():
        system_parent = await Menu.filter(path="/system").first()
        if system_parent:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="系统设置",
                path="settings",
                order=7,
                parent_id=system_parent.id,
                icon="material-symbols:settings-outline",
                is_hidden=False,
                component="/system/settings",
                keepalive=False,
                redirect="",
            )

    if not await Menu.filter(component="/system/notice").exists():
        system_parent = await Menu.filter(path="/system").first()
        if system_parent:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="全局通知",
                path="notice",
                order=8,
                parent_id=system_parent.id,
                icon="material-symbols:notifications-active-outline-rounded",
                is_hidden=False,
                component="/system/notice",
                keepalive=False,
                redirect="",
            )

    monitor_menu = await Menu.filter(Q(component="/system/monitor") | Q(path="monitor")).first()
    system_parent = await Menu.filter(path="/system").first()
    if system_parent:
        if monitor_menu:
            monitor_menu.menu_type = MenuType.MENU
            monitor_menu.name = "系统监控"
            monitor_menu.path = "monitor"
            monitor_menu.order = 9
            monitor_menu.parent_id = system_parent.id
            monitor_menu.icon = "material-symbols:monitor-heart-outline-rounded"
            monitor_menu.is_hidden = False
            monitor_menu.component = "/system/monitor"
            monitor_menu.keepalive = False
            monitor_menu.redirect = ""
            await monitor_menu.save()
        else:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="系统监控",
                path="monitor",
                order=9,
                parent_id=system_parent.id,
                icon="material-symbols:monitor-heart-outline-rounded",
                is_hidden=False,
                component="/system/monitor",
                keepalive=False,
                redirect="",
            )

    outbound_parent = await Menu.filter(path="/outbound").first()
    if not outbound_parent:
        outbound_parent = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="外发管理",
            path="/outbound",
            order=5,
            parent_id=0,
            icon="material-symbols:outbox-outline",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/outbound/webdav",
        )
    else:
        outbound_parent.menu_type = MenuType.CATALOG
        outbound_parent.name = "外发管理"
        outbound_parent.order = 5
        outbound_parent.parent_id = 0
        outbound_parent.icon = "material-symbols:outbox-outline"
        outbound_parent.is_hidden = False
        outbound_parent.component = "Layout"
        outbound_parent.keepalive = False
        outbound_parent.redirect = "/outbound/webdav"
        await outbound_parent.save()

    webdav_menu = await Menu.filter(
        Q(component="/system/webdav") | Q(path="webdav", parent_id=outbound_parent.id) | Q(name="外发网盘")
    ).first()
    if webdav_menu:
        webdav_menu.name = "外发网盘"
        webdav_menu.path = "webdav"
        webdav_menu.order = 1
        webdav_menu.parent_id = outbound_parent.id
        webdav_menu.icon = "material-symbols:cloud-sync-outline"
        webdav_menu.is_hidden = False
        webdav_menu.keepalive = False
        webdav_menu.redirect = ""
        await webdav_menu.save()
    else:
        await Menu.create(
            menu_type=MenuType.MENU,
            name="外发网盘",
            path="webdav",
            order=1,
            parent_id=outbound_parent.id,
            icon="material-symbols:cloud-sync-outline",
            is_hidden=False,
            component="/system/webdav",
            keepalive=False,
            redirect="",
        )

    share_menu = await Menu.filter(
        Q(component="/system/webdav-share") | Q(path="webdav-share", parent_id=outbound_parent.id) | Q(name="分享记录")
    ).first()
    if share_menu:
        share_menu.name = "分享记录"
        share_menu.path = "webdav-share"
        share_menu.order = 2
        share_menu.parent_id = outbound_parent.id
        share_menu.icon = "material-symbols:link-rounded"
        share_menu.is_hidden = False
        share_menu.keepalive = False
        share_menu.redirect = ""
        await share_menu.save()
    else:
        await Menu.create(
            menu_type=MenuType.MENU,
            name="分享记录",
            path="webdav-share",
            order=2,
            parent_id=outbound_parent.id,
            icon="material-symbols:link-rounded",
            is_hidden=False,
            component="/system/webdav-share",
            keepalive=False,
            redirect="",
        )

    password_menu = await Menu.filter(
        Q(component="/system/webdav-password") | Q(path="webdav-password", parent_id=outbound_parent.id) | Q(name="密码获取")
    ).first()
    if password_menu:
        password_menu.name = "密码获取"
        password_menu.path = "webdav-password"
        password_menu.order = 3
        password_menu.parent_id = outbound_parent.id
        password_menu.icon = "material-symbols:key-outline-rounded"
        password_menu.is_hidden = False
        password_menu.keepalive = False
        password_menu.redirect = ""
        await password_menu.save()
    else:
        await Menu.create(
            menu_type=MenuType.MENU,
            name="密码获取",
            path="webdav-password",
            order=3,
            parent_id=outbound_parent.id,
            icon="material-symbols:key-outline-rounded",
            is_hidden=False,
            component="/system/webdav-password",
            keepalive=False,
            redirect="",
        )

    skill_know_parent = await Menu.filter(path="/skill-know").first()
    if not skill_know_parent:
        skill_know_parent = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="AI知识库",
            path="/skill-know",
            order=6,
            parent_id=0,
            icon="carbon:machine-learning-model",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/skill-know/chat",
        )
    else:
        skill_know_parent.menu_type = MenuType.CATALOG
        skill_know_parent.name = "AI知识库"
        skill_know_parent.order = 6
        skill_know_parent.parent_id = 0
        skill_know_parent.icon = "carbon:machine-learning-model"
        skill_know_parent.is_hidden = False
        skill_know_parent.component = "Layout"
        skill_know_parent.keepalive = False
        skill_know_parent.redirect = "/skill-know/chat"
        await skill_know_parent.save()

    skill_know_children = [
        {
            "name": "智能对话",
            "path": "chat",
            "order": 1,
            "icon": "material-symbols:chat-outline-rounded",
            "component": "/skill-know/chat",
        },
        {
            "name": "文档管理",
            "path": "documents",
            "order": 2,
            "icon": "material-symbols:docs-outline-rounded",
            "component": "/skill-know/documents",
        },
        {
            "name": "LLM设置",
            "path": "llm-settings",
            "order": 3,
            "icon": "material-symbols:tune-rounded",
            "component": "/skill-know/llm-settings",
        },
        {
            "name": "对话历史",
            "path": "conversations",
            "order": 4,
            "icon": "material-symbols:rate-review-outline-rounded",
            "component": "/skill-know/conversations",
        },
        {
            "name": "自进化报告",
            "path": "evolution",
            "order": 5,
            "icon": "material-symbols:model-training-outline-rounded",
            "component": "/skill-know/evolution",
        },
    ]
    legacy_skill_know_components = [
        "/skill-know/search",
        "/skill-know/skills",
        "/skill-know/graph",
        "/skill-know/quick-setup",
        "/skill-know/upload-tasks",
        "/skill-know/packs",
        "/skill-know/prompts",
    ]
    await Menu.filter(parent_id=skill_know_parent.id, component__in=legacy_skill_know_components).delete()
    for child in skill_know_children:
        skill_know_menu = await Menu.filter(
            Q(component=child["component"]) | Q(path=child["path"], parent_id=skill_know_parent.id)
        ).first()
        if skill_know_menu:
            skill_know_menu.menu_type = MenuType.MENU
            skill_know_menu.name = child["name"]
            skill_know_menu.path = child["path"]
            skill_know_menu.order = child["order"]
            skill_know_menu.parent_id = skill_know_parent.id
            skill_know_menu.icon = child["icon"]
            skill_know_menu.is_hidden = False
            skill_know_menu.component = child["component"]
            skill_know_menu.keepalive = False
            skill_know_menu.redirect = ""
            await skill_know_menu.save()
        else:
            await Menu.create(
                menu_type=MenuType.MENU,
                parent_id=skill_know_parent.id,
                is_hidden=False,
                keepalive=False,
                redirect="",
                **child,
            )

    terminal_parent = await Menu.filter(path="/terminal").first()
    if not terminal_parent:
        terminal_parent = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="终端管理",
            path="/terminal",
            order=7,
            parent_id=0,
            icon="material-symbols:devices-outline",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/terminal/auth",
        )
    else:
        terminal_parent.menu_type = MenuType.CATALOG
        terminal_parent.name = "终端管理"
        terminal_parent.order = 7
        terminal_parent.parent_id = 0
        terminal_parent.icon = "material-symbols:devices-outline"
        terminal_parent.is_hidden = False
        terminal_parent.component = "Layout"
        terminal_parent.keepalive = False
        terminal_parent.redirect = "/terminal/auth"
        await terminal_parent.save()

    terminal_children = [
        {
            "name": "授权校验",
            "path": "auth",
            "order": 1,
            "icon": "material-symbols:verified-user-outline-rounded",
            "component": "/terminal/auth",
        },
        {
            "name": "在线升级",
            "path": "upgrade",
            "order": 2,
            "icon": "mdi:update",
            "component": "/terminal/upgrade",
        },
    ]
    for child in terminal_children:
        terminal_menu = await Menu.filter(
            Q(component=child["component"]) | Q(path=child["path"], parent_id=terminal_parent.id)
        ).first()
        if terminal_menu:
            terminal_menu.menu_type = MenuType.MENU
            terminal_menu.name = child["name"]
            terminal_menu.path = child["path"]
            terminal_menu.order = child["order"]
            terminal_menu.parent_id = terminal_parent.id
            terminal_menu.icon = child["icon"]
            terminal_menu.is_hidden = False
            terminal_menu.component = child["component"]
            terminal_menu.keepalive = False
            terminal_menu.redirect = ""
            await terminal_menu.save()
        else:
            await Menu.create(
                menu_type=MenuType.MENU,
                parent_id=terminal_parent.id,
                is_hidden=False,
                keepalive=False,
                redirect="",
                **child,
            )



async def init_apis():
    await api_controller.refresh_api()


async def _backfill_existing_role_permissions(
    *,
    role_name: str,
    api_paths: list[str],
    component_paths: list[str] | None = None,
) -> bool:
    role = await Role.filter(name=role_name).first()
    if not role:
        return False

    changed = False
    apis = await Api.filter(path__in=api_paths)
    if apis:
        existing_api_ids = {api.id for api in await role.apis.filter(id__in=[api.id for api in apis])}
        missing_apis = [api for api in apis if api.id not in existing_api_ids]
        if missing_apis:
            await role.apis.add(*missing_apis)
            changed = True

    if component_paths:
        menus = await Menu.filter(Q(component__in=component_paths))
        if menus:
            existing_menu_ids = {menu.id for menu in await role.menus.filter(id__in=[menu.id for menu in menus])}
            missing_menus = [menu for menu in menus if menu.id not in existing_menu_ids]
            if missing_menus:
                await role.menus.add(*missing_menus)
                changed = True

    if changed:
        from app.controllers.role import role_controller

        await role_controller.clear_permission_cache_by_role(role.id)
        await role_controller.clear_role_dict_cache()
        logger.info("[init_roles] backfilled permissions role={} api_count={}", role_name, len(apis))
    return changed


async def init_db():
    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        await Tortoise.generate_schemas(safe=True)
    except Exception as exc:
        if "already exists" in str(exc).lower():
            logger.warning("[init_db] schema generation skipped because tables already exist: {}", exc)
        else:
            raise
    await ensure_security_columns()


async def ensure_security_columns():
    async with in_transaction() as conn:
        for sql, label in [
            ("ALTER TABLE `user` ADD COLUMN `token_version` INT NOT NULL DEFAULT 0", "user.token_version"),
            ("ALTER TABLE `auditlog` ADD COLUMN `is_archived` BOOL NOT NULL DEFAULT 0", "auditlog.is_archived"),
            ("ALTER TABLE `ticket` ADD COLUMN `issue_type` VARCHAR(30) NOT NULL DEFAULT '现网问题'", "ticket.issue_type"),
            ("ALTER TABLE `ticket` ADD COLUMN `impact_scope` VARCHAR(30) NOT NULL DEFAULT '全部'", "ticket.impact_scope"),
            ("ALTER TABLE `ticket` ADD COLUMN `redmine_issue_id` BIGINT NULL", "ticket.redmine_issue_id"),
            ("ALTER TABLE `ticket` ADD COLUMN `redmine_issue_url` VARCHAR(500) NULL", "ticket.redmine_issue_url"),
            ("ALTER TABLE `ticket` ADD COLUMN `redmine_sync_status` VARCHAR(20) NOT NULL DEFAULT 'never'", "ticket.redmine_sync_status"),
            ("ALTER TABLE `ticket` ADD COLUMN `redmine_sync_error` TEXT NULL", "ticket.redmine_sync_error"),
            ("ALTER TABLE `ticket` ADD COLUMN `redmine_synced_at` DATETIME(6) NULL", "ticket.redmine_synced_at"),
            ("ALTER TABLE `ticket` ADD COLUMN `redmine_last_updated_on` DATETIME(6) NULL", "ticket.redmine_last_updated_on"),
            ("ALTER TABLE `ticket` ADD COLUMN `redmine_status_id` BIGINT NULL", "ticket.redmine_status_id"),
            ("ALTER TABLE `ticket` ADD COLUMN `redmine_status_name` VARCHAR(120) NULL", "ticket.redmine_status_name"),
            ("ALTER TABLE `sk_document` ADD COLUMN `owner_id` BIGINT NULL", "sk_document.owner_id"),
            ("ALTER TABLE `sk_conversation` ADD COLUMN `owner_id` BIGINT NULL", "sk_conversation.owner_id"),
            ("ALTER TABLE `ticket` MODIFY COLUMN `status` VARCHAR(32) NOT NULL DEFAULT 'pending_review'", "ticket.status.width"),
            ("ALTER TABLE `ticket_action_log` MODIFY COLUMN `action` VARCHAR(32) NOT NULL", "ticket_action_log.action.width"),
            ("ALTER TABLE `ticket_action_log` MODIFY COLUMN `from_status` VARCHAR(32) NULL", "ticket_action_log.from_status.width"),
            ("ALTER TABLE `ticket_action_log` MODIFY COLUMN `to_status` VARCHAR(32) NOT NULL", "ticket_action_log.to_status.width"),
        ]:
            try:
                await conn.execute_query(sql)
                logger.info("[init_db] added missing column {}", label)
            except Exception as exc:
                message = str(exc).lower()
                if "duplicate" in message or "exists" in message:
                    continue
                logger.warning("[init_db] ensure column {} skipped error={}", label, exc)


async def init_roles():
    old_partner_role = await Role.filter(name="代理商").first()
    if old_partner_role:
        old_partner_role.name = "渠道商"
        old_partner_role.desc = "渠道商角色"
        await old_partner_role.save()

    role_desc_map = {
        "管理员": "管理员角色",
        "渠道商": "渠道商角色",
        "用户": "用户角色",
        "技术": "技术角色",
        "客服": "客服角色",
    }

    role_names = list(role_desc_map.keys())
    existing_roles = await Role.filter(name__in=role_names).all()
    existing_role_names = {role.name for role in existing_roles}
    missing_roles = [name for name in role_names if name not in existing_role_names]

    if not missing_roles:
        has_role_bindings = False
        for role in existing_roles:
            has_menu_binding = await role.menus.all().first() is not None
            has_api_binding = await role.apis.all().first() is not None
            if has_menu_binding or has_api_binding:
                has_role_bindings = True
                break

        if has_role_bindings:
            admin_role = next((role for role in existing_roles if role.name == "管理员"), None)
            if admin_role:
                await admin_role.apis.add(*await Api.all())
                await admin_role.menus.add(*await Menu.all())
                await admin_role.apis.add(*await Api.filter(path__in=_monitor_api_paths()))
                await admin_role.apis.add(*await Api.filter(path__in=_terminal_api_paths()))
                await admin_role.apis.add(
                    *await Api.filter(
                        path__in=[
                            "/api/v1/settings/time-sync/status",
                            "/api/v1/settings/time-sync/sync",
                            "/api/v1/settings/database-backup/status",
                            "/api/v1/settings/database-backup/test",
                            "/api/v1/settings/database-backup/run",
                            *_webdav_password_api_paths(),
                        ]
                    )
                )
                await admin_role.menus.add(*await Menu.filter(Q(component="/system/monitor")))
                await admin_role.menus.add(*await Menu.filter(Q(component="/system/webdav-password")))
                await admin_role.menus.add(*await Menu.filter(Q(path="/terminal") | Q(component__in=["/terminal/auth", "/terminal/upgrade"])))
            await _backfill_existing_role_permissions(
                role_name="技术",
                api_paths=_ticket_redmine_api_paths(),
            )
            logger.info("[init_roles] detected existing role permissions, skip default role permission backfill")
            return

    role_map: dict[str, Role] = {}
    for role_name, role_desc in role_desc_map.items():
        role_obj, _ = await Role.get_or_create(name=role_name, defaults={"desc": role_desc})
        role_map[role_name] = role_obj

    all_apis = await Api.all()
    all_menus = await Menu.all()

    admin_role = role_map["管理员"]
    await admin_role.apis.add(*all_apis)
    await admin_role.menus.add(*all_menus)

    ticket_submit_apis = await Api.filter(
        path__in=[
            "/api/v1/ticket/upload",
            "/api/v1/ticket/create",
            "/api/v1/ticket/list",
            "/api/v1/ticket/export",
            "/api/v1/ticket/get",
            "/api/v1/ticket/resubmit",
            "/api/v1/ticket/actions",
        ]
    )
    ticket_tech_apis = await Api.filter(
        path__in=[
            "/api/v1/ticket/tech/action",
            "/api/v1/ticket/assign-tech",
            *_ticket_redmine_api_paths(),
        ]
    )
    ticket_review_apis = await Api.filter(path__in=["/api/v1/ticket/review", "/api/v1/ticket/assign-tech"])
    partner_review_apis = await Api.filter(
        path__in=["/api/v1/partner/register/list", "/api/v1/partner/register/review"]
    )
    settings_apis = await Api.filter(
        path__in=[
            "/api/v1/settings/get",
            "/api/v1/settings/update",
            "/api/v1/settings/time-sync/status",
            "/api/v1/settings/time-sync/sync",
            "/api/v1/settings/redmine/metadata",
            "/api/v1/settings/database-backup/status",
            "/api/v1/settings/database-backup/test",
            "/api/v1/settings/database-backup/run",
        ]
    )
    webdav_apis = await Api.filter(
        path__in=[
            "/api/v1/webdav/list",
            "/api/v1/webdav/download-url",
            "/api/v1/webdav/share/create",
            "/api/v1/webdav/share/list",
            "/api/v1/webdav/share/delete",
        ]
    )
    webdav_password_apis = await Api.filter(
        path__in=_webdav_password_api_paths()
    )
    notice_apis = await Api.filter(
        path__in=[
            "/api/v1/notice/create",
            "/api/v1/notice/list",
            "/api/v1/notice/inbox",
            "/api/v1/notice/unread_count",
            "/api/v1/notice/read",
            "/api/v1/notice/read_all",
        ]
    )
    monitor_apis = await Api.filter(path__in=_monitor_api_paths())
    terminal_apis = await Api.filter(path__in=_terminal_api_paths())
    notice_user_apis = await Api.filter(
        path__in=[
            "/api/v1/notice/inbox",
            "/api/v1/notice/unread_count",
            "/api/v1/notice/read",
            "/api/v1/notice/read_all",
        ]
    )
    basic_apis = await Api.filter(_default_basic_api_filter())

    submit_menus = await Menu.filter(Q(path="/ticket") | Q(component="/ticket/submit") | Q(component="/ticket/my"))
    tech_menus = await Menu.filter(Q(path="/ticket") | Q(component="/ticket/tech") | Q(component="/ticket/my"))
    review_menus = await Menu.filter(Q(path="/ticket") | Q(component="/ticket/review"))
    partner_review_menus = await Menu.filter(Q(path="/partner") | Q(component="/partner/review"))
    settings_menus = await Menu.filter(Q(component="/system/settings"))
    notice_menus = await Menu.filter(Q(component="/system/notice"))
    monitor_menus = await Menu.filter(Q(component="/system/monitor"))
    terminal_menus = await Menu.filter(Q(path="/terminal") | Q(component__in=["/terminal/auth", "/terminal/upgrade"]))
    webdav_menus = await Menu.filter(
        Q(path="/outbound")
        | Q(component="/system/webdav")
        | Q(component="/system/webdav-share")
    )
    webdav_password_menus = await Menu.filter(Q(component="/system/webdav-password"))

    for role_name in ["用户", "渠道商", "技术", "客服"]:
        role_obj = role_map[role_name]
        await role_obj.apis.add(*basic_apis)
        await role_obj.apis.add(*notice_user_apis)

    await role_map["用户"].apis.add(*ticket_submit_apis)
    await role_map["用户"].menus.add(*submit_menus)

    await role_map["渠道商"].apis.add(*ticket_submit_apis)
    await role_map["渠道商"].menus.add(*submit_menus)

    await role_map["技术"].apis.add(*ticket_submit_apis)
    await role_map["技术"].apis.add(*ticket_tech_apis)
    await role_map["技术"].menus.add(*tech_menus)

    await role_map["客服"].apis.add(*ticket_review_apis)
    await role_map["客服"].apis.add(*partner_review_apis)
    await role_map["客服"].apis.add(
        *await Api.filter(path__in=["/api/v1/ticket/list", "/api/v1/ticket/export", "/api/v1/ticket/get", "/api/v1/ticket/actions"])
    )
    await role_map["客服"].menus.add(*review_menus)
    await role_map["客服"].menus.add(*partner_review_menus)

    await role_map["管理员"].apis.add(*settings_apis)
    await role_map["管理员"].apis.add(*monitor_apis)
    await role_map["管理员"].apis.add(*terminal_apis)
    await role_map["管理员"].apis.add(*webdav_apis)
    await role_map["管理员"].apis.add(*webdav_password_apis)
    await role_map["管理员"].apis.add(*notice_apis)
    await role_map["管理员"].menus.add(*settings_menus)
    await role_map["管理员"].menus.add(*monitor_menus)
    await role_map["管理员"].menus.add(*terminal_menus)
    await role_map["管理员"].menus.add(*notice_menus)
    await role_map["管理员"].menus.add(*webdav_menus)
    await role_map["管理员"].menus.add(*webdav_password_menus)


async def init_skill_know_config_defaults():
    defaults = [
        {
            "key": "evolution_daily_eval_enabled",
            "value": True,
            "group": "evolution",
            "description": "是否启用 Skill-Know 自进化每日评测",
        },
        {
            "key": "evolution_daily_eval_time",
            "value": {"__raw": "02:10"},
            "group": "evolution",
            "description": "Skill-Know 自进化每日评测时间(HH:MM)",
        },
        {
            "key": "evolution_daily_eval_top_k",
            "value": 8,
            "group": "evolution",
            "description": "Skill-Know 自进化每日评测 TopK",
        },
    ]
    for default in defaults:
        exists = await SkillKnowSystemConfig.filter(key=default["key"]).exists()
        if not exists:
            await SkillKnowSystemConfig.create(
                key=default["key"],
                value=default["value"],
                group=default["group"],
                description=default["description"],
                is_sensitive=False,
            )

    item = await SkillKnowSystemConfig.filter(key="retrieval_max_context_chars").first()
    if not item:
        await SkillKnowSystemConfig.create(
            key="retrieval_max_context_chars",
            value=128000,
            group="retrieval",
            description="最大上下文字符数",
            is_sensitive=False,
        )
        return

    current_value = item.value
    if isinstance(current_value, dict) and "__raw" in current_value:
        current_value = current_value.get("__raw")
    try:
        normalized = int(current_value)
    except Exception:
        normalized = None

    if normalized in {None, 12000}:
        item.value = 128000
        item.group = "retrieval"
        item.description = item.description or "最大上下文字符数"
        item.is_sensitive = False
        await item.save()


async def init_data():
    await init_db()
    await init_superuser()
    await init_menus()
    await init_apis()
    await init_roles()
    await init_skill_know_config_defaults()
