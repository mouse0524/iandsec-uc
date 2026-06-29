from datetime import datetime

from fastapi import HTTPException
from tortoise.expressions import Q

from app.controllers.system_setting import system_setting_controller
from app.controllers.user import user_controller
from app.models.admin import Project, ProjectActivity, Ticket, User


PROJECT_ROLES = {"管理员", "客服", "技术"}
ASSIGNEE_ROLES = {"技术"}
ACTIVITY_STATUSES = {"待处理", "处理中", "已完成"}
PROJECT_STATUSES = ["售前", "待实施", "实施中", "待验收", "已验收", "丢单"]


class ProjectController:
    @staticmethod
    def _clean(value) -> str:
        return str(value or "").strip()

    @staticmethod
    def _can_manage(user: User, role_names: list[str]) -> bool:
        return bool(user.is_superuser or PROJECT_ROLES.intersection(role_names))

    async def require_manager(self, user: User, role_names: list[str]) -> None:
        if not self._can_manage(user, role_names):
            raise HTTPException(status_code=403, detail="仅客服、技术或管理员可管理项目")

    @staticmethod
    def can_view_all(user: User, role_names: list[str]) -> bool:
        return bool(user.is_superuser or {"管理员", "客服"}.intersection(role_names))

    def _project_q(self, filters: dict) -> Q:
        q = Q()
        if filters.get("project_name"):
            q &= Q(project_name__contains=filters["project_name"])
        if filters.get("status"):
            q &= Q(status=filters["status"])
        if filters.get("region"):
            q &= Q(region=filters["region"])
        if filters.get("assignee_id"):
            q &= Q(assignee_id=filters["assignee_id"])
        return q

    def _activity_q(self, filters: dict) -> Q:
        q = Q()
        if filters.get("project_ids") is not None:
            q &= Q(project_id__in=filters["project_ids"])
        if filters.get("project_id"):
            q &= Q(project_id=filters["project_id"])
        if filters.get("activity_type"):
            q &= Q(activity_type=filters["activity_type"])
        if filters.get("status"):
            q &= Q(status=filters["status"])
        return q

    async def _config(self) -> dict:
        config = await system_setting_controller.get_full_dict()
        return {
            "products": config.get("project_products") or ["安得卫士"],
            "statuses": config.get("project_statuses") or PROJECT_STATUSES,
            "regions": config.get("project_regions") or ["华东", "华南", "华北", "华中", "西南", "西北"],
            "activity_types": config.get("project_activity_types") or ["迁移库", "重做系统", "运维", "其他"],
        }

    async def _validate_assignee(self, assignee_id: int | None) -> None:
        if not assignee_id:
            return
        user = await User.filter(id=assignee_id, is_active=True).prefetch_related("roles").first()
        if not user:
            raise HTTPException(status_code=400, detail="负责人不存在或未启用")
        role_names = {role.name for role in await user.roles}
        if not ASSIGNEE_ROLES.intersection(role_names):
            raise HTTPException(status_code=400, detail="负责人必须是技术")

    async def _validate_payload(self, payload: dict, *, partial: bool = False) -> dict:
        config = await self._config()
        data = dict(payload)
        for key in [
            "project_name",
            "region",
            "server_version",
            "client_version",
            "customer_contact",
            "customer_phone",
            "customer_email",
            "status",
            "remark",
        ]:
            if key in data:
                data[key] = self._clean(data.get(key)) or None
        if not partial:
            if not data.get("project_name"):
                raise HTTPException(status_code=400, detail="项目名称不能为空")
        data["product_points"] = self._normalize_product_points(data.get("product_points"), config["products"])
        if not data.get("status"):
            data["status"] = config["statuses"][0]
        if data["status"] not in config["statuses"]:
            raise HTTPException(status_code=400, detail="项目状态不在配置范围内")
        if data.get("region") and data["region"] not in config["regions"]:
            raise HTTPException(status_code=400, detail="项目区域不在配置范围内")
        await self._validate_assignee(data.get("assignee_id"))
        return data

    def _normalize_product_points(self, value, products: list[str]) -> list[dict]:
        rows = []
        seen = set()
        for item in value or []:
            name = self._clean((item or {}).get("product_name"))
            if not name:
                continue
            if name not in products:
                raise HTTPException(status_code=400, detail="使用产品不在配置范围内")
            if name in seen:
                raise HTTPException(status_code=400, detail="使用产品不能重复")
            seen.add(name)
            rows.append({"product_name": name, "points": max(0, int((item or {}).get("points") or 0))})
        if not rows:
            raise HTTPException(status_code=400, detail="使用产品不能为空")
        return rows

    async def create_project(self, *, user_id: int, payload: dict) -> Project:
        data = await self._validate_payload(payload)
        assignee_id = data.get("assignee_id")
        project = await Project.create(
            **data,
            created_by=user_id,
            assigned_by=user_id if assignee_id else None,
            assigned_at=datetime.now() if assignee_id else None,
        )
        return project

    async def update_project(self, *, project_id: int, user_id: int, payload: dict) -> Project:
        project = await Project.get(id=project_id)
        data = await self._validate_payload(payload)
        old_assignee_id = project.assignee_id
        for key, value in data.items():
            setattr(project, key, value)
        if project.assignee_id != old_assignee_id:
            project.assigned_by = user_id if project.assignee_id else None
            project.assigned_at = datetime.now() if project.assignee_id else None
        await project.save()
        return project

    async def set_status(self, *, project_id: int, status: str) -> Project:
        project = await Project.get(id=project_id)
        config = await self._config()
        normalized = self._clean(status)
        if normalized not in config["statuses"]:
            raise HTTPException(status_code=400, detail="项目状态不在配置范围内")
        project.status = normalized
        await project.save()
        return project

    async def assign(self, *, project_id: int, user_id: int, assignee_id: int | None) -> Project:
        project = await Project.get(id=project_id)
        await self._validate_assignee(assignee_id)
        project.assignee_id = assignee_id
        project.assigned_by = user_id if assignee_id else None
        project.assigned_at = datetime.now() if assignee_id else None
        await project.save()
        return project

    async def list_projects(self, *, page: int, page_size: int, filters: dict) -> tuple[int, list[dict]]:
        q = self._project_q(filters)
        query = Project.filter(q)
        total = await query.count()
        projects = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        rows = [await self._project_row(item) for item in projects]
        return total, rows

    async def project_summary(self, filters: dict) -> dict:
        q = self._project_q(filters)
        total = await Project.filter(q).count()
        return {
            "total": total,
            "presale": await Project.filter(q & Q(status="售前")).count(),
            "pending": await Project.filter(q & Q(status="待实施")).count(),
            "implementing": await Project.filter(q & Q(status="实施中")).count(),
            "pending_acceptance": await Project.filter(q & Q(status="待验收")).count(),
            "accepted": await Project.filter(q & Q(status="已验收")).count(),
            "lost": await Project.filter(q & Q(status="丢单")).count(),
        }

    async def _project_row(self, project: Project) -> dict:
        data = await project.to_dict()
        issue_count = await Ticket.filter(company_name=project.project_name, issue_type="现网问题").count()
        requirement_count = await Ticket.filter(company_name=project.project_name, issue_type="现网需求").count()
        activity_count = await ProjectActivity.filter(project_id=project.id).count()
        data.update(
            {
                "issue_count": issue_count,
                "requirement_count": requirement_count,
                "activity_count": activity_count,
                "assignee_name": await self._user_name(project.assignee_id),
                "creator_name": await self._user_name(project.created_by),
            }
        )
        return data

    async def get_project(self, project_id: int) -> dict:
        return await self._project_row(await Project.get(id=project_id))

    async def visible_projects_for_user(self, user_id: int, project_id: int | None = None) -> list[Project]:
        q = Q(assignee_id=user_id)
        if project_id:
            q &= Q(id=project_id)
        return await Project.filter(q)

    async def list_activities(self, *, page: int, page_size: int, filters: dict) -> tuple[int, list[dict]]:
        q = self._activity_q(filters)
        query = ProjectActivity.filter(q)
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        return total, [await self._activity_row(item) for item in rows]

    async def activity_summary(self, filters: dict) -> dict:
        q = self._activity_q(filters)
        total = await ProjectActivity.filter(q).count()
        return {
            "total": total,
            "pending": await ProjectActivity.filter(q & Q(status="待处理")).count(),
            "processing": await ProjectActivity.filter(q & Q(status="处理中")).count(),
            "done": await ProjectActivity.filter(q & Q(status="已完成")).count(),
        }

    async def _activity_row(self, item: ProjectActivity) -> dict:
        data = await item.to_dict()
        project = await Project.filter(id=item.project_id).first()
        data["project_name"] = project.project_name if project else ""
        data["operator_name"] = await self._user_name(item.operator_id)
        data["creator_name"] = await self._user_name(item.created_by)
        return data

    async def get_activity(self, activity_id: int) -> ProjectActivity:
        return await ProjectActivity.get(id=activity_id)

    async def save_activity(self, *, user_id: int, payload: dict, activity_id: int | None = None) -> ProjectActivity:
        config = await self._config()
        data = dict(payload)
        for key in ["activity_type", "title", "content", "status"]:
            if key in data:
                data[key] = self._clean(data.get(key)) or None
        if not await Project.filter(id=data.get("project_id")).exists():
            raise HTTPException(status_code=404, detail="项目不存在")
        if data.get("activity_type") not in config["activity_types"]:
            raise HTTPException(status_code=400, detail="活动类型不在配置范围内")
        if not data.get("title"):
            raise HTTPException(status_code=400, detail="活动标题不能为空")
        if data.get("status") not in ACTIVITY_STATUSES:
            raise HTTPException(status_code=400, detail="活动状态不正确")
        await self._validate_assignee(data.get("operator_id"))
        if activity_id:
            activity = await ProjectActivity.get(id=activity_id)
            for key, value in data.items():
                setattr(activity, key, value)
            await activity.save()
            return activity
        return await ProjectActivity.create(**data, created_by=user_id)

    @staticmethod
    async def _user_name(user_id: int | None) -> str:
        if not user_id:
            return ""
        try:
            basic = await user_controller.get_user_basic(int(user_id))
            return str(basic.get("alias") or basic.get("username") or "")
        except Exception:
            return ""


project_controller = ProjectController()
