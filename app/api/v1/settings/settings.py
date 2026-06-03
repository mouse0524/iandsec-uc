import html
import json

from fastapi import APIRouter, File, UploadFile

from app.log import logger
from app.controllers.system_setting import system_setting_controller
from app.core.redis_client import execute_redis
from app.schemas.base import Success
from app.schemas.settings import DatabaseBackupConfigIn, RedmineMetadataIn, SystemSettingUpdateIn, WebDavTestIn
from app.services.database_backup_service import database_backup_scheduler, database_backup_service
from app.services.redmine_client import RedmineClient

router = APIRouter()
MASKED_SECRET = "******"
REDMINE_METADATA_CACHE_KEY = system_setting_controller.REDMINE_METADATA_CACHE_KEY
REDMINE_METADATA_CACHE_TTL_SECONDS = system_setting_controller.REDMINE_METADATA_CACHE_TTL_SECONDS


async def _database_backup_config(payload: DatabaseBackupConfigIn) -> dict:
    config = await system_setting_controller.get_full_dict()
    data = payload.model_dump(exclude_none=True)
    if data.get("db_backup_webdav_password") == MASKED_SECRET:
        data.pop("db_backup_webdav_password", None)
    config.update(data)
    return config


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
        "db_backup_mysql_container",
        "db_backup_webdav_base_url",
        "db_backup_webdav_username",
        "db_backup_webdav_password",
        "db_backup_run_at",
        "db_backup_retention_days",
        "ticket_cs_review_project_phases",
        "ticket_issue_types",
        "ticket_impact_scopes",
        "redmine_enabled",
        "redmine_base_url",
        "redmine_api_key",
        "redmine_project_id",
        "redmine_tracker_id",
        "redmine_priority_id",
        "redmine_assigned_to_id",
        "redmine_project_phase_field_id",
        "redmine_os_field_id",
        "redmine_sync_visible_fields",
        "redmine_sync_options",
        "redmine_auto_pull_enabled",
        "redmine_auto_pull_interval_minutes",
        "redmine_auto_pull_ticket_statuses",
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



def _redmine_item(item) -> dict:
    if isinstance(item, dict):
        item_id = item.get("id")
        name = item.get("name")
        identifier = item.get("identifier")
        login = item.get("login")
        customized_type = item.get("customized_type")
        possible_values = item.get("possible_values")
    else:
        item_id = getattr(item, "id", None)
        name = getattr(item, "name", None)
        identifier = getattr(item, "identifier", None)
        login = getattr(item, "login", None)
        customized_type = getattr(item, "customized_type", None)
        possible_values = getattr(item, "possible_values", None)
        if not name:
            firstname = getattr(item, "firstname", None)
            lastname = getattr(item, "lastname", None)
            name = " ".join(part for part in [lastname, firstname] if part)
    value = identifier or item_id
    label_value = value if value is not None else ""
    display_name = name or login or label_value
    safe_name = html.escape(str(display_name or ""))
    return {
        "id": item_id,
        "identifier": identifier,
        "login": login,
        "customized_type": customized_type,
        "name": safe_name,
        "value": str(label_value),
        "label": safe_name,
        "possible_values": _redmine_possible_values(possible_values),
    }


def _redmine_possible_values(values) -> list[dict]:
    result = []
    for item in values or []:
        raw_value = item.get("value") if isinstance(item, dict) else getattr(item, "value", item)
        value = str(raw_value or "").strip()
        if value:
            result.append({"label": html.escape(value), "value": value})
    return result


@router.post("/redmine/metadata", summary="获取 Redmine 配置选项")
async def get_redmine_metadata(payload: RedmineMetadataIn):
    logger.info("[api.settings.redmine.metadata] request")
    data = payload.model_dump(exclude_none=True)
    if not data:
        cached = await _get_redmine_metadata_cache()
        if cached is not None:
            return Success(data=cached)
    config = await system_setting_controller.get_full_dict()
    if data.get("redmine_api_key") == MASKED_SECRET:
        data.pop("redmine_api_key", None)
    config.update(data)
    client = RedmineClient(config)
    projects = await client.list_projects()
    trackers = await client.list_trackers()
    priorities = await client.list_issue_priorities()
    users = await client.list_users()
    custom_fields = [
        item
        for item in await client.list_custom_fields()
        if not getattr(item, "customized_type", None) or getattr(item, "customized_type", None) == "issue"
    ]
    metadata = {
        "projects": [_redmine_item(item) for item in projects],
        "trackers": [_redmine_item(item) for item in trackers],
        "priorities": [_redmine_item(item) for item in priorities],
        "users": [_redmine_item(item) for item in users],
        "custom_fields": [_redmine_item(item) for item in custom_fields],
        "redmine_project_id": config.get("redmine_project_id"),
        "redmine_tracker_id": config.get("redmine_tracker_id"),
        "redmine_priority_id": config.get("redmine_priority_id"),
        "redmine_assigned_to_id": config.get("redmine_assigned_to_id"),
        "redmine_project_phase_field_id": config.get("redmine_project_phase_field_id"),
        "redmine_os_field_id": config.get("redmine_os_field_id"),
        "redmine_sync_visible_fields": config.get("redmine_sync_visible_fields") or [],
        "redmine_sync_options": config.get("redmine_sync_options") or {},
    }
    await _set_redmine_metadata_cache(metadata)
    return Success(data=metadata)


async def _get_redmine_metadata_cache() -> dict | None:
    try:
        cached = await execute_redis("get", REDMINE_METADATA_CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception as exc:
        logger.warning("[api.settings.redmine.metadata] cache_read_failed key={} error={}", REDMINE_METADATA_CACHE_KEY, str(exc))
    return None


async def _set_redmine_metadata_cache(metadata: dict) -> None:
    try:
        await execute_redis(
            "setex",
            REDMINE_METADATA_CACHE_KEY,
            REDMINE_METADATA_CACHE_TTL_SECONDS,
            json.dumps(metadata, ensure_ascii=False),
        )
    except Exception as exc:
        logger.warning("[api.settings.redmine.metadata] cache_write_failed key={} error={}", REDMINE_METADATA_CACHE_KEY, str(exc))


@router.get("/database-backup/status", summary="获取数据库备份状态")
async def get_database_backup_status():
    logger.info("[api.settings.database_backup.status] request")
    data = await system_setting_controller.get_full_dict()
    return Success(data=database_backup_service.status(data))


@router.post("/database-backup/test", summary="测试数据库备份目录")
async def test_database_backup_directory(payload: DatabaseBackupConfigIn):
    logger.info("[api.settings.database_backup.test] request")
    config = await _database_backup_config(payload)
    data = await database_backup_service.test_directory(config)
    return Success(msg="NAS远端目录可用", data=data)


@router.post("/database-backup/run", summary="立即执行数据库备份")
async def run_database_backup(payload: DatabaseBackupConfigIn):
    logger.info("[api.settings.database_backup.run] request")
    config = await _database_backup_config(payload)
    data = await database_backup_scheduler.run_once(config=config, force=True)
    if data is None:
        return Success(msg="已有数据库备份任务正在执行", data={"ok": True, "skipped": True, "reason": "locked"})
    return Success(msg="数据库备份完成", data=data)
