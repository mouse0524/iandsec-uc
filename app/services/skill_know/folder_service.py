from __future__ import annotations

from fastapi import HTTPException

from app.models.admin import SkillKnowDocument, SkillKnowFolder
from app.services.skill_know.utils import folder_to_dict, new_uuid


class SkillKnowFolderService:
    async def ensure_root(self) -> SkillKnowFolder:
        root = await SkillKnowFolder.filter(is_system=True, parent_id=None, name="根目录").first()
        if root:
            return root
        return await SkillKnowFolder.create(uuid=new_uuid(), name="根目录", description="系统根目录", is_system=True)

    async def create(self, data) -> dict:
        folder = await SkillKnowFolder.create(
            uuid=new_uuid(),
            name=data.name,
            description=data.description,
            parent_id=data.parent_id,
            sort_order=data.sort_order,
        )
        return await folder_to_dict(folder)

    async def list(self, parent_id: int | None = None, tree: bool = False) -> list[dict]:
        await self.ensure_root()
        folders = await SkillKnowFolder.all().order_by("sort_order", "id") if tree else await SkillKnowFolder.filter(parent_id=parent_id).order_by("sort_order", "id")
        data = [await folder_to_dict(item) for item in folders]
        if not tree:
            return data
        by_parent: dict[int | None, list[dict]] = {}
        for item in data:
            by_parent.setdefault(item.get("parent_id"), []).append(item)
        for item in data:
            item["children"] = by_parent.get(item["id"], [])
        return by_parent.get(None, [])

    async def update(self, data) -> dict:
        folder = await SkillKnowFolder.filter(id=data.folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="文件夹不存在")
        for field in ["name", "description", "parent_id", "sort_order"]:
            value = getattr(data, field, None)
            if value is not None:
                setattr(folder, field, value)
        await folder.save()
        return await folder_to_dict(folder)

    async def delete(self, folder_id: int) -> None:
        folder = await SkillKnowFolder.filter(id=folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="文件夹不存在")
        if folder.is_system:
            raise HTTPException(status_code=400, detail="系统文件夹不可删除")
        await SkillKnowDocument.filter(folder_id=folder_id).update(folder_id=None)
        await SkillKnowFolder.filter(parent_id=folder_id).update(parent_id=folder.parent_id)
        await folder.delete()


skill_know_folder_service = SkillKnowFolderService()
