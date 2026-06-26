import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from tortoise.expressions import Q

from app.models.admin import RdTask, RdTaskLog, RdTaskTicket, Ticket, User
from app.models.enums import RdTaskStatus, RdTaskType

class RdTaskController:
    ACTION_RULES = {
        "product_approve": {
            "from": {RdTaskStatus.PENDING_PRODUCT_REVIEW},
            "to": RdTaskStatus.PENDING_DEV,
            "roles": {"产品", "管理员"},
        },
        "product_reject": {
            "from": {RdTaskStatus.PENDING_PRODUCT_REVIEW},
            "to": RdTaskStatus.REJECTED,
            "roles": {"产品", "管理员"},
        },
        "assign_dev": {
            "from": {RdTaskStatus.PENDING_DEV, RdTaskStatus.TEST_REJECTED},
            "to": RdTaskStatus.PENDING_DEV,
            "roles": {"技术", "产品", "研发", "管理员"},
        },
        "dev_start": {
            "from": {RdTaskStatus.PENDING_DEV, RdTaskStatus.TEST_REJECTED},
            "to": RdTaskStatus.DEV_PROCESSING,
            "roles": {"研发", "管理员"},
        },
        "submit_test": {
            "from": {RdTaskStatus.DEV_PROCESSING},
            "to": RdTaskStatus.PENDING_TEST,
            "roles": {"研发", "管理员"},
        },
        "test_pass": {
            "from": {RdTaskStatus.PENDING_TEST},
            "to": RdTaskStatus.TEST_PASSED,
            "roles": {"测试", "管理员"},
        },
        "test_reject": {
            "from": {RdTaskStatus.PENDING_TEST},
            "to": RdTaskStatus.TEST_REJECTED,
            "roles": {"测试", "管理员"},
        },
        "mark_pending_release": {
            "from": {RdTaskStatus.TEST_PASSED},
            "to": RdTaskStatus.PENDING_RELEASE,
            "roles": {"技术", "产品", "研发", "测试", "管理员"},
        },
        "complete": {
            "from": {RdTaskStatus.TEST_PASSED, RdTaskStatus.PENDING_RELEASE, RdTaskStatus.DEV_PROCESSING},
            "to": RdTaskStatus.COMPLETED,
            "roles": {"技术", "产品", "研发", "测试", "管理员"},
        },
        "reject": {
            "from": {RdTaskStatus.PENDING_DEV, RdTaskStatus.DEV_PROCESSING, RdTaskStatus.TEST_REJECTED},
            "to": RdTaskStatus.REJECTED,
            "roles": {"技术", "产品", "研发", "管理员"},
        },
    }

    def __init__(
        self,
        *,
        task_model: Any | None = None,
        link_model: Any | None = None,
        log_model: Any | None = None,
        ticket_model: Any | None = None,
    ) -> None:
        self.task_model = task_model or RdTask
        self.link_model = link_model or RdTaskTicket
        self.log_model = log_model or RdTaskLog
        self.ticket_model = ticket_model or Ticket

    @staticmethod
    def _next_task_no() -> str:
        return f"RD{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"

    @staticmethod
    def _initial_status(task_type: RdTaskType) -> RdTaskStatus:
        if task_type == RdTaskType.REQUIREMENT:
            return RdTaskStatus.PENDING_PRODUCT_REVIEW
        return RdTaskStatus.PENDING_DEV

    async def create_from_ticket(
        self,
        *,
        ticket_id: int,
        operator_id: int,
        task_type: RdTaskType,
        title: str | None,
        description: str | None,
        priority: str,
        product_owner_id: int | None,
        dev_owner_id: int | None,
        test_owner_id: int | None,
        planned_version: str | None,
    ):
        ticket = await self.ticket_model.get(id=ticket_id)
        status = self._initial_status(task_type)
        task = await self.task_model.create(
            task_no=self._next_task_no(),
            title=(title or getattr(ticket, "title", "") or "未命名产研任务").strip(),
            task_type=task_type,
            status=status,
            priority=(priority or "normal").strip(),
            product_owner_id=product_owner_id,
            dev_owner_id=dev_owner_id,
            test_owner_id=test_owner_id,
            planned_version=(planned_version or "").strip() or None,
            description=(description or getattr(ticket, "description", "") or "").strip() or None,
            created_by=operator_id,
        )
        await self.log_model.create(
            rd_task_id=task.id,
            action="create",
            from_status=None,
            to_status=status,
            operator_id=operator_id,
            comment=f"由工单 {ticket_id} 转产研",
        )
        await self.link_ticket(task_id=task.id, ticket_id=ticket_id, operator_id=operator_id)
        return task

    async def link_ticket(self, *, task_id: int, ticket_id: int, operator_id: int):
        existing = None
        if hasattr(self.link_model, "filter"):
            query = self.link_model.filter(rd_task_id=task_id, ticket_id=ticket_id)
            if hasattr(query, "first"):
                existing = await query.first()
        if existing:
            return existing

        link = await self.link_model.create(ticket_id=ticket_id, rd_task_id=task_id, created_by=operator_id)
        task = await self.task_model.get(id=task_id) if hasattr(self.task_model, "get") else None
        await self.log_model.create(
            rd_task_id=task_id,
            action="link_ticket",
            from_status=getattr(task, "status", None),
            to_status=getattr(task, "status", RdTaskStatus.PENDING_DEV),
            operator_id=operator_id,
            comment=f"关联工单 {ticket_id}",
        )
        return link

    async def transition(
        self,
        *,
        task_id: int,
        operator_id: int,
        action: str,
        comment: str | None,
        role_names: list[str] | None = None,
        is_superuser: bool = False,
    ):
        task = await self.task_model.get(id=task_id)
        old_status = task.status
        new_status = self._status_for_action(task, action, role_names=role_names or [], is_superuser=is_superuser)
        task.status = new_status
        if action in {"complete", "reject"}:
            task.result_note = (comment or "").strip() or task.result_note
            task.finished_at = datetime.now() if action == "complete" else getattr(task, "finished_at", None)
        await task.save()
        await self.log_model.create(
            rd_task_id=task.id,
            action=action,
            from_status=old_status,
            to_status=new_status,
            operator_id=operator_id,
            comment=(comment or "").strip() or None,
        )
        followup_ticket_ids = await self._linked_ticket_ids(task.id) if new_status in {RdTaskStatus.COMPLETED, RdTaskStatus.REJECTED} else []
        return {"task": task, "followup_ticket_ids": followup_ticket_ids}

    def _status_for_action(
        self,
        task,
        action: str,
        *,
        role_names: list[str],
        is_superuser: bool,
    ) -> RdTaskStatus:
        rule = self.ACTION_RULES.get(action)
        if not rule:
            raise HTTPException(status_code=400, detail="不支持的产研任务动作")
        if not is_superuser and not set(role_names).intersection(rule["roles"]):
            raise HTTPException(status_code=403, detail="当前角色不能执行该产研任务动作")
        if task.status not in rule["from"]:
            raise HTTPException(status_code=400, detail="当前状态不能执行该产研任务动作")
        return rule["to"]

    async def _linked_ticket_ids(self, task_id: int) -> list[int]:
        query = self.link_model.filter(rd_task_id=task_id)
        values = await query.values_list("ticket_id", flat=True)
        return [int(item) for item in values]

    async def list_tasks(
        self,
        *,
        page: int,
        page_size: int,
        status: RdTaskStatus | None,
        task_type: RdTaskType | None,
        keyword: str | None,
        owner_id: int | None,
    ) -> tuple[int, list[dict]]:
        query = self.task_model.all()
        if status:
            query = query.filter(status=status)
        if task_type:
            query = query.filter(task_type=task_type)
        if keyword:
            query = query.filter(Q(title__contains=keyword) | Q(task_no__contains=keyword))
        if owner_id:
            query = query.filter(Q(product_owner_id=owner_id) | Q(dev_owner_id=owner_id) | Q(test_owner_id=owner_id))

        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        data = [await item.to_dict() for item in rows]
        await self._attach_user_names(data)
        await self._attach_linked_ticket_counts(data)
        return total, data

    async def detail(self, task_id: int) -> dict:
        task = await self.task_model.get(id=task_id)
        data = await task.to_dict()
        links = await self.link_model.filter(rd_task_id=task_id).order_by("-id").values()
        logs = await self.log_model.filter(rd_task_id=task_id).order_by("id").values()
        data["ticket_links"] = list(links)
        data["logs"] = list(logs)
        await self._attach_user_names([data])
        return data

    async def _attach_user_names(self, rows: list[dict]) -> None:
        user_ids = {
            row.get(field)
            for row in rows
            for field in ("product_owner_id", "dev_owner_id", "test_owner_id", "created_by")
            if row.get(field)
        }
        if not user_ids:
            return
        users = await User.filter(id__in=list(user_ids)).values("id", "username", "alias")
        user_map = {item["id"]: item.get("alias") or item.get("username") or "" for item in users}
        for row in rows:
            row["product_owner_name"] = user_map.get(row.get("product_owner_id"), "")
            row["dev_owner_name"] = user_map.get(row.get("dev_owner_id"), "")
            row["test_owner_name"] = user_map.get(row.get("test_owner_id"), "")
            row["created_by_name"] = user_map.get(row.get("created_by"), "")

    async def _attach_linked_ticket_counts(self, rows: list[dict]) -> None:
        for row in rows:
            row["ticket_count"] = await self.link_model.filter(rd_task_id=row["id"]).count()


rd_task_controller = RdTaskController()
