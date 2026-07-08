from fastapi import HTTPException
from tortoise.expressions import Q
from tortoise.exceptions import IntegrityError
from tortoise.transactions import atomic

from app.core.crud import CRUDBase
from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import Dept, DeptClosure, User
from app.models.enums import PartnerLevel
from app.schemas.depts import DeptCreate, DeptUpdate


class DeptController(CRUDBase[Dept, DeptCreate, DeptUpdate]):
    DEPT_DICT_CACHE_KEY = "dict:depts:v1"
    def __init__(self):
        super().__init__(model=Dept)

    async def get_dept_tree(self, name):
        search = str(name or "").strip()
        all_depts = await self.model.filter(is_deleted=False).order_by("order")
        tech_ids = {
            int(tech_id)
            for dept in all_depts
            for tech_id in (dept.tech_ids or [])
            if int(tech_id or 0) > 0
        }
        tech_map = {}
        if tech_ids:
            users = await User.filter(id__in=tech_ids, is_active=True)
            tech_map = {user.id: (user.alias or user.username or str(user.id)) for user in users}

        # 辅助函数，用于递归构建部门树
        def build_tree(parent_id):
            rows = []
            for dept in all_depts:
                if dept.parent_id != parent_id:
                    continue
                children = build_tree(dept.id)
                if search and search not in dept.name and not children:
                    continue
                rows.append(
                    {
                        "id": dept.id,
                        "name": dept.name,
                        "desc": dept.desc,
                        "channel_level": dept.channel_level,
                        "tech_ids": dept.tech_ids or [],
                        "tech_names": [tech_map.get(int(tech_id), str(tech_id)) for tech_id in (dept.tech_ids or [])],
                        "order": dept.order,
                        "parent_id": dept.parent_id,
                        "children": children,
                    }
                )
            return rows

        # 从顶级部门（parent_id=0）开始构建部门树
        dept_tree = build_tree(0)
        return dept_tree

    async def clear_dept_dict_cache(self) -> None:
        try:
            await execute_redis("delete", self.DEPT_DICT_CACHE_KEY)
        except Exception:
            pass

    async def clear_ticket_scope_cache(self) -> None:
        try:
            keys: set[str] = set()
            cursor = 0
            while True:
                cursor, batch = await execute_redis(
                    "scan",
                    cursor=cursor,
                    match="ticket:tech_related_submitters:*",
                    count=500,
                )
                keys.update(batch or [])
                if int(cursor or 0) == 0:
                    break
            if keys:
                await execute_redis("delete", *keys)
        except Exception:
            pass

    async def get_dept_info(self):
        pass

    async def get_or_create(
        self, *, name: str, parent_id: int = 0, desc: str = "", channel_level: PartnerLevel | None = None
    ) -> Dept:
        name = str(name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="部门名称不能为空")
        dept_obj = await Dept.filter(name=name).first()
        if dept_obj:
            logger.info("[dept.get_or_create] reuse name={} dept_id={} parent_id={}", name, dept_obj.id, dept_obj.parent_id)
            if dept_obj.is_deleted:
                dept_obj.is_deleted = False
                dept_obj.parent_id = parent_id
                dept_obj.desc = desc or dept_obj.desc
                dept_obj.channel_level = channel_level or dept_obj.channel_level
                await dept_obj.save()
                await self.clear_dept_dict_cache()
                await self.clear_ticket_scope_cache()
                logger.info("[dept.get_or_create] revive name={} dept_id={} parent_id={}", name, dept_obj.id, parent_id)
            elif channel_level and not dept_obj.channel_level:
                dept_obj.channel_level = channel_level
                await dept_obj.save()
                await self.clear_dept_dict_cache()
                await self.clear_ticket_scope_cache()
            return dept_obj

        dept_obj = await Dept.create(
            name=name, parent_id=parent_id, desc=desc, channel_level=channel_level, order=0, is_deleted=False
        )
        logger.info("[dept.get_or_create] create name={} dept_id={} parent_id={}", name, dept_obj.id, parent_id)

        closure_rows = []
        if parent_id != 0:
            parent_paths = await DeptClosure.filter(descendant=parent_id)
            for item in parent_paths:
                closure_rows.append(DeptClosure(ancestor=item.ancestor, descendant=dept_obj.id, level=item.level + 1))
        closure_rows.append(DeptClosure(ancestor=dept_obj.id, descendant=dept_obj.id, level=0))
        await DeptClosure.bulk_create(closure_rows)
        await self.clear_dept_dict_cache()
        await self.clear_ticket_scope_cache()
        return dept_obj

    async def update_dept_closure(self, obj: Dept):
        parent_depts = await DeptClosure.filter(descendant=obj.parent_id)
        dept_closure_objs: list[DeptClosure] = []
        # 插入父级关系
        for item in parent_depts:
            dept_closure_objs.append(DeptClosure(ancestor=item.ancestor, descendant=obj.id, level=item.level + 1))
        # 插入自身x
        dept_closure_objs.append(DeptClosure(ancestor=obj.id, descendant=obj.id, level=0))
        # 创建关系
        await DeptClosure.bulk_create(dept_closure_objs)

    async def _normalize_tech_ids(self, tech_ids: list[int] | None) -> list[int]:
        ids = list(dict.fromkeys(int(item) for item in tech_ids or [] if int(item or 0) > 0))
        if not ids:
            return []
        users = await User.filter(id__in=ids, is_active=True, roles__name="技术").values_list("id", flat=True)
        valid_ids = set(int(item) for item in users)
        if len(valid_ids) != len(ids):
            raise HTTPException(status_code=400, detail="请选择有效的技术人员")
        return ids

    @atomic()
    async def create_dept(self, obj_in: DeptCreate):
        obj_in.name = str(obj_in.name or "").strip()
        obj_in.tech_ids = await self._normalize_tech_ids(obj_in.tech_ids)
        if not obj_in.name:
            raise HTTPException(status_code=400, detail="部门名称不能为空")
        if await Dept.filter(name=obj_in.name).exists():
            raise HTTPException(status_code=400, detail="部门名称已存在")
        logger.info(
            "[dept.create] start name={} parent_id={} order={}",
            obj_in.name,
            obj_in.parent_id,
            obj_in.order,
        )
        # 创建
        if obj_in.parent_id != 0:
            await self.get(id=obj_in.parent_id)
        try:
            new_obj = await self.create(obj_in=obj_in)
        except IntegrityError:
            raise HTTPException(status_code=400, detail="部门名称已存在")
        await self.update_dept_closure(new_obj)
        logger.info(
            "[dept.create] success dept_id={} name={} parent_id={}",
            new_obj.id,
            new_obj.name,
            new_obj.parent_id,
        )
        await self.clear_dept_dict_cache()
        await self.clear_ticket_scope_cache()

    @atomic()
    async def update_dept(self, obj_in: DeptUpdate):
        obj_in.name = str(obj_in.name or "").strip()
        obj_in.tech_ids = await self._normalize_tech_ids(obj_in.tech_ids)
        if not obj_in.name:
            raise HTTPException(status_code=400, detail="部门名称不能为空")
        if await Dept.filter(name=obj_in.name).exclude(id=obj_in.id).exists():
            raise HTTPException(status_code=400, detail="部门名称已存在")
        if obj_in.parent_id == obj_in.id:
            raise HTTPException(status_code=400, detail="上级部门不能选择自己")
        if obj_in.parent_id != 0:
            await self.get(id=obj_in.parent_id)
            if await DeptClosure.filter(ancestor=obj_in.id, descendant=obj_in.parent_id).exists():
                raise HTTPException(status_code=400, detail="上级部门不能选择自己的子部门")
        logger.info(
            "[dept.update] start dept_id={} name={} parent_id={}",
            obj_in.id,
            obj_in.name,
            obj_in.parent_id,
        )
        await self.clear_dept_dict_cache()
        await self.clear_ticket_scope_cache()
        dept_obj = await self.get(id=obj_in.id)
        # 更新部门关系
        if dept_obj.parent_id != obj_in.parent_id:
            dept_obj.parent_id = obj_in.parent_id
            await DeptClosure.filter(ancestor=dept_obj.id).delete()
            await DeptClosure.filter(descendant=dept_obj.id).delete()
            await self.update_dept_closure(dept_obj)
        # 更新部门信息
        dept_obj.update_from_dict(obj_in.model_dump(exclude_unset=True))
        try:
            await dept_obj.save()
        except IntegrityError:
            raise HTTPException(status_code=400, detail="部门名称已存在")
        await User.filter(dept_id=dept_obj.id).update(channel_level=dept_obj.channel_level)
        logger.info(
            "[dept.update] success dept_id={} name={} parent_id={}",
            dept_obj.id,
            dept_obj.name,
            dept_obj.parent_id,
        )

    @atomic()
    async def delete_dept(self, dept_id: int):
        # 删除部门
        obj = await self.get(id=dept_id)
        obj.is_deleted = True
        await obj.save()
        # 删除关系
        await DeptClosure.filter(descendant=dept_id).delete()
        await self.clear_dept_dict_cache()


dept_controller = DeptController()
