from tortoise import BaseDBAsyncClient


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


async def _index_exists(db: BaseDBAsyncClient, table: str, index_name: str) -> bool:
    rows = await db.execute_query_dict(
        """
        SELECT COUNT(*) AS count
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s
        """,
        [table, index_name],
    )
    return bool(rows and int(rows[0]["count"]) > 0)


async def upgrade(db: BaseDBAsyncClient) -> str:
    if not await _column_exists(db, "issue_status", "active"):
        await db.execute_script("ALTER TABLE `issue_status` ADD COLUMN `active` BOOL NOT NULL DEFAULT 1")
    if not await _index_exists(db, "issue_status", "idx_issue_status_active"):
        await db.execute_script("ALTER TABLE `issue_status` ADD KEY `idx_issue_status_active` (`active`)")
    return "SELECT 1;"


async def downgrade(db: BaseDBAsyncClient) -> str:
    if await _column_exists(db, "issue_status", "active"):
        await db.execute_script("ALTER TABLE `issue_status` DROP COLUMN `active`")
    return "SELECT 1;"
