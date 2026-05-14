from typing import List

from app.core.crud import CRUDBase
from app.core.redis_client import execute_redis
from app.models.admin import Api, Menu, Role
from app.schemas.roles import RoleCreate, RoleUpdate


class RoleController(CRUDBase[Role, RoleCreate, RoleUpdate]):
    ROLE_DICT_CACHE_KEY = "dict:roles:v1"
    def __init__(self):
        super().__init__(model=Role)

    async def is_exist(self, name: str) -> bool:
        return await self.model.filter(name=name).exists()

    async def clear_role_dict_cache(self) -> None:
        try:
            await execute_redis("delete", self.ROLE_DICT_CACHE_KEY)
        except Exception:
            pass

    async def update_roles(self, role: Role, menu_ids: List[int], api_infos: List[dict]) -> None:
        await role.menus.clear()
        for menu_id in menu_ids:
            menu_obj = await Menu.filter(id=menu_id).first()
            await role.menus.add(menu_obj)

        await role.apis.clear()
        for item in api_infos:
            api_obj = await Api.filter(path=item.get("path"), method=item.get("method")).first()
            await role.apis.add(api_obj)
        await self.clear_permission_cache_by_role(role.id)
        await self.clear_role_dict_cache()

    @staticmethod
    async def clear_permission_cache_by_role(role_id: int) -> None:
        user_ids = await get_role_user_ids(role_id)
        if not user_ids:
            return
        keys = []
        for user_id in user_ids:
            keys.extend([
                f"perm:menu:user:{user_id}:v1",
                f"perm:api:user:{user_id}:v1",
                f"perm:menu:user:{user_id}:v2",
                f"perm:api:user:{user_id}:v2",
                f"perm:is_admin:user:{user_id}:v1",
            ])
        try:
            await execute_redis("delete", *keys)
        except Exception:
            pass


async def get_role_user_ids(role_id: int) -> list[int]:
    role = await Role.filter(id=role_id).first()
    if not role:
        return []
    users = await role.user_roles.all()
    return [item.id for item in users if item and item.id]


role_controller = RoleController()
