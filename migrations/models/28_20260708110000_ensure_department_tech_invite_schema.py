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


async def _add_column_if_missing(db: BaseDBAsyncClient, table: str, column: str, definition: str) -> None:
    if await _table_exists(db, table) and not await _column_exists(db, table, column):
        await db.execute_script(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")


async def _drop_column_if_present(db: BaseDBAsyncClient, table: str, column: str) -> None:
    if await _table_exists(db, table) and await _column_exists(db, table, column):
        await db.execute_script(f"ALTER TABLE `{table}` DROP COLUMN `{column}`")


async def upgrade(db: BaseDBAsyncClient) -> str:
    await _add_column_if_missing(db, "dept", "tech_ids", "JSON NULL")
    await _add_column_if_missing(db, "partner_registration", "invite_code", "VARCHAR(32) NULL")
    await db.execute_script("UPDATE `partner_registration` SET `status` = 'pending' WHERE `status` = '待审核'")
    await db.execute_script(
        """
        CREATE TABLE IF NOT EXISTS `partner_invite` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `code` VARCHAR(32) NOT NULL UNIQUE,
            `created_by` BIGINT NOT NULL,
            `used_by` BIGINT NULL,
            `used_at` DATETIME(6) NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_partner_invite_code` (`code`),
            KEY `idx_partner_invite_created_by` (`created_by`),
            KEY `idx_partner_invite_used_by` (`used_by`)
        )
        """
    )
    return "SELECT 1;"


async def downgrade(db: BaseDBAsyncClient) -> str:
    await db.execute_script("DROP TABLE IF EXISTS `partner_invite`")
    await _drop_column_if_present(db, "partner_registration", "invite_code")
    await _drop_column_if_present(db, "dept", "tech_ids")
    return "SELECT 1;"
