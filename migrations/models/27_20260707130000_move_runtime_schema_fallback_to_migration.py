from tortoise import BaseDBAsyncClient


async def _table_exists(db: BaseDBAsyncClient, table: str) -> bool:
    rows = await db.execute_query_dict(
        """
        SELECT COUNT(*) AS count
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        """,
        [table],
    )
    return bool(rows and int(rows[0]["count"]) > 0)


async def _column_exists(db: BaseDBAsyncClient, table: str, column: str) -> bool:
    rows = await db.execute_query_dict(
        """
        SELECT COUNT(*) AS count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        [table, column],
    )
    return bool(rows and int(rows[0]["count"]) > 0)


async def _columns_exist(db: BaseDBAsyncClient, table: str, columns: list[str]) -> bool:
    return all([await _column_exists(db, table, column) for column in columns])


async def _add_column_if_missing(db: BaseDBAsyncClient, table: str, column: str, definition: str) -> None:
    if not await _column_exists(db, table, column):
        await db.execute_script(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")


async def _drop_column_if_present(db: BaseDBAsyncClient, table: str, column: str) -> None:
    if await _column_exists(db, table, column):
        await db.execute_script(f"ALTER TABLE `{table}` DROP COLUMN `{column}`")


async def upgrade(db: BaseDBAsyncClient) -> str:
    for table, column, definition in [
        ("auditlog", "is_archived", "BOOL NOT NULL DEFAULT 0"),
        ("ticket", "issue_type", "VARCHAR(30) NOT NULL DEFAULT '现网问题'"),
        ("ticket", "impact_scope", "VARCHAR(30) NOT NULL DEFAULT '全部'"),
        ("ticket", "redmine_issue_id", "BIGINT NULL"),
        ("ticket", "redmine_issue_url", "VARCHAR(500) NULL"),
        ("ticket", "redmine_sync_status", "VARCHAR(20) NOT NULL DEFAULT 'never'"),
        ("ticket", "redmine_sync_error", "TEXT NULL"),
        ("ticket", "redmine_synced_at", "DATETIME(6) NULL"),
        ("ticket", "redmine_last_updated_on", "DATETIME(6) NULL"),
        ("ticket", "redmine_status_id", "BIGINT NULL"),
        ("ticket", "redmine_status_name", "VARCHAR(120) NULL"),
        ("ticket", "redmine_closed", "BOOL NOT NULL DEFAULT 0"),
        ("global_notice", "delivery_channels", "JSON NULL"),
        ("project", "product_points", "JSON NULL"),
        ("project", "region", "VARCHAR(30) NULL"),
        ("project", "agent_id", "BIGINT NULL"),
        ("project", "server_version", "VARCHAR(80) NULL"),
        ("project", "client_version", "VARCHAR(80) NULL"),
        ("project", "start_time", "DATETIME NULL"),
        ("project", "end_time", "DATETIME NULL"),
        ("project", "maintenance_time", "DATETIME NULL"),
        ("dept", "channel_level", "VARCHAR(20) NULL"),
        ("user", "channel_level", "VARCHAR(20) NULL"),
    ]:
        await _add_column_if_missing(db, table, column, definition)

    if await _table_exists(db, "project_activity") and await _columns_exist(
        db, "project_activity", ["activity_type", "content", "title"]
    ):
        await db.execute_script(
            """
            UPDATE `project_activity` SET `title` = LEFT(`content`, 200)
            WHERE `activity_type` = '备注' AND `content` IS NOT NULL AND TRIM(`content`) <> ''
            AND (`title` IS NULL OR `title` = '' OR `title` = '备注')
            """
        )

    await db.execute_script(
        """
        CREATE TABLE IF NOT EXISTS `webdav_download_log` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `download_type` VARCHAR(20) NOT NULL,
            `file_path` VARCHAR(1000) NOT NULL,
            `file_name` VARCHAR(255) NULL,
            `share_code` VARCHAR(32) NULL,
            `downloader_id` BIGINT NULL,
            `downloader_name` VARCHAR(120) NULL,
            `source_ip` VARCHAR(64) NULL,
            `user_agent` VARCHAR(500) NULL,
            `referer` VARCHAR(500) NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_webdav_dl_type` (`download_type`),
            KEY `idx_webdav_dl_share` (`share_code`),
            KEY `idx_webdav_dl_user` (`downloader_id`),
            KEY `idx_webdav_dl_ip` (`source_ip`),
            KEY `idx_webdav_dl_created` (`created_at`)
        )
        """
    )
    return "SELECT 1;"


async def downgrade(db: BaseDBAsyncClient) -> str:
    await db.execute_script("DROP TABLE IF EXISTS `webdav_download_log`")

    for table, column in [
        ("user", "channel_level"),
        ("dept", "channel_level"),
        ("project", "maintenance_time"),
        ("project", "end_time"),
        ("project", "start_time"),
        ("project", "client_version"),
        ("project", "server_version"),
        ("project", "agent_id"),
        ("project", "region"),
        ("project", "product_points"),
        ("global_notice", "delivery_channels"),
        ("ticket", "redmine_closed"),
        ("ticket", "redmine_status_name"),
        ("ticket", "redmine_status_id"),
        ("ticket", "redmine_last_updated_on"),
        ("ticket", "redmine_synced_at"),
        ("ticket", "redmine_sync_error"),
        ("ticket", "redmine_sync_status"),
        ("ticket", "redmine_issue_url"),
        ("ticket", "redmine_issue_id"),
        ("ticket", "impact_scope"),
        ("ticket", "issue_type"),
        ("auditlog", "is_archived"),
    ]:
        await _drop_column_if_present(db, table, column)

    return "SELECT 1;"
