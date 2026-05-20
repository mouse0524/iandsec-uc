from fastapi import APIRouter, File, UploadFile

from app.log import logger
from app.controllers.system_setting import system_setting_controller
from app.schemas.base import Success
from app.schemas.settings import SystemSettingUpdateIn, WebDavTestIn

router = APIRouter()


@router.get("/get", summary="获取系统设置")
async def get_system_setting():
    logger.info("[api.settings.get] request")
    data = await system_setting_controller.get_safe_dict()
    logger.info("[api.settings.get] success setting_id={}", data.get("id"))
    return Success(data=data)


@router.post("/update", summary="更新系统设置")
async def update_system_setting(payload: SystemSettingUpdateIn):
    logger.info("[api.settings.update] request")
    data = payload.model_dump()
    for key in ("allow_channel_register", "allow_user_register"):
        if key not in payload.model_fields_set:
            data.pop(key, None)
    setting = await system_setting_controller.update(data)
    data = await system_setting_controller.get_safe_dict()
    logger.info("[api.settings.update] success setting_id={}", data.get("id"))
    return Success(msg="保存成功", data=data)


@router.post("/upload_logo", summary="上传站点Logo")
async def upload_site_logo(file: UploadFile = File(...)):
    logger.info("[api.settings.upload_logo] request filename={}", file.filename)
    rel_path = await system_setting_controller.upload_logo(file)
    logger.info("[api.settings.upload_logo] success path={}", rel_path)
    return Success(msg="上传成功", data={"site_logo": rel_path, "site_logo_url": "/api/v1/base/site_logo"})


@router.post("/webdav/test", summary="测试WebDAV连接")
async def test_webdav_connection(payload: WebDavTestIn):
    logger.info("[api.settings.webdav.test] request")
    data = await system_setting_controller.test_webdav_connection(payload.model_dump())
    return Success(msg="连接测试成功", data=data)
