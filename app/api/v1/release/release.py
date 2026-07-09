from datetime import datetime
from time import time

from fastapi import APIRouter, HTTPException
from tortoise.transactions import in_transaction

from app.models.admin import SystemSettingItem
from app.schemas.base import Success
from app.schemas.release import ReleaseRecordDeleteIn, ReleaseRecordIn

router = APIRouter()
SECTION = "release_records"


async def _setting(*, for_update: bool = False) -> SystemSettingItem:
    if for_update:
        item = await SystemSettingItem.filter(section=SECTION).select_for_update().first()
        if not item:
            item, _ = await SystemSettingItem.get_or_create(section=SECTION, defaults={"data": {"records": []}})
    else:
        item, _ = await SystemSettingItem.get_or_create(section=SECTION, defaults={"data": {"records": []}})
    if not isinstance(item.data, dict):
        item.data = {"records": []}
    if not isinstance(item.data.get("records"), list):
        item.data["records"] = []
    return item


async def _records() -> list[dict]:
    item = await _setting()
    return sorted(item.data["records"], key=lambda record: int(record.get("id") or 0), reverse=True)


def _date_text(value: int | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromtimestamp(int(value) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


@router.get("/view-list", summary="查看版本发布记录")
async def view_release_records():
    return Success(data=[record for record in await _records() if record.get("status") == "已发布"])


@router.get("/list", summary="版本发布记录列表")
async def list_release_records():
    return Success(data=await _records())


@router.post("/save", summary="保存版本发布记录")
async def save_release_record(payload: ReleaseRecordIn):
    async with in_transaction():
        item = await _setting(for_update=True)
        records = item.data["records"]
        record = payload.model_dump()
        record["id"] = record.get("id") or int(time() * 1000)
        record["publishDateText"] = _date_text(record.get("publishDate"))
        if record.get("id") in [row.get("id") for row in records]:
            item.data["records"] = [record if row.get("id") == record["id"] else row for row in records]
        else:
            item.data["records"] = [record, *records]
        await item.save()
    return Success(msg="保存成功", data=record)


@router.post("/delete", summary="删除版本发布记录")
async def delete_release_record(payload: ReleaseRecordDeleteIn):
    async with in_transaction():
        item = await _setting(for_update=True)
        before = len(item.data["records"])
        item.data["records"] = [record for record in item.data["records"] if record.get("id") != payload.id]
        if len(item.data["records"]) == before:
            raise HTTPException(status_code=404, detail="发布记录不存在")
        await item.save()
    return Success(msg="删除成功")


@router.post("/clear", summary="清空版本发布记录")
async def clear_release_records():
    async with in_transaction():
        item = await _setting(for_update=True)
        item.data["records"] = []
        await item.save()
    return Success(msg="清空成功")
