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


async def upgrade(db: BaseDBAsyncClient) -> str:
    if not await _column_exists(db, "user", "token_version"):
        await db.execute_script("ALTER TABLE `user` ADD COLUMN `token_version` INT NOT NULL DEFAULT 0")
    return "SELECT 1;"


async def downgrade(db: BaseDBAsyncClient) -> str:
    if await _column_exists(db, "user", "token_version"):
        await db.execute_script("ALTER TABLE `user` DROP COLUMN `token_version`")
    return "SELECT 1;"
