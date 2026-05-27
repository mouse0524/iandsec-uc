from fastapi import APIRouter, File, UploadFile

from app.log import logger
from app.controllers.system_setting import system_setting_controller
from app.schemas.base import Success
from app.schemas.settings import DatabaseBackupConfigIn, SystemSettingUpdateIn, WebDavTestIn
from app.services.database_backup_service import database_backup_scheduler, database_backup_service

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
    optional_preserve_keys = (
        "allow_channel_register",
        "allow_user_register",
        "db_backup_enabled",
        "db_backup_directory",
        "db_backup_run_at",
        "db_backup_retention_days",
        "webdav_public_base_url",
    )
    for key in optional_preserve_keys:
        if key not in payload.model_fields_set:
            data.pop(key, None)
    await system_setting_controller.update(data)
    data = await system_setting_controller.get_safe_dict()
    logger.info("[api.settings.update] success setting_id={}", data.get("id"))
    return Success(msg="保存成功", data=data)


@router.get("/time-sync/status", summary="检测时间同步状态")
async def get_time_sync_status():
    logger.info("[api.settings.time_sync.status] request")
    data = await system_setting_controller.get_time_sync_status()
    return Success(data=data)


@router.post("/time-sync/sync", summary="执行时间同步")
async def sync_system_time():
    logger.info("[api.settings.time_sync.sync] request")
    data = await system_setting_controller.sync_time()
    return Success(msg="时间同步完成", data=data)


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


@router.get("/database-backup/status", summary="获取数据库备份状态")
async def get_database_backup_status():
    logger.info("[api.settings.database_backup.status] request")
    data = await system_setting_controller.get_full_dict()
    return Success(data=database_backup_service.status(data))


@router.post("/database-backup/test", summary="测试数据库备份目录")
async def test_database_backup_directory(payload: DatabaseBackupConfigIn):
    logger.info("[api.settings.database_backup.test] request")
    data = await database_backup_service.test_directory(payload.model_dump(exclude_none=True))
    return Success(msg="备份目录可用", data=data)


@router.post("/database-backup/run", summary="立即执行数据库备份")
async def run_database_backup(payload: DatabaseBackupConfigIn):
    logger.info("[api.settings.database_backup.run] request")
    config = await system_setting_controller.get_full_dict()
    config.update(payload.model_dump(exclude_none=True))
    data = await database_backup_scheduler.run_once(config=config, force=True)
    if data is None:
        return Success(msg="已有数据库备份任务正在执行", data={"ok": True, "skipped": True, "reason": "locked"})
    return Success(msg="数据库备份完成", data=data)
