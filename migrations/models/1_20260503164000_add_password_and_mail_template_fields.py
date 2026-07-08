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
    for column, definition in [
        ("password_min_length", "INT NOT NULL DEFAULT 8"),
        ("password_min_category_count", "INT NOT NULL DEFAULT 2"),
        ("ticket_mail_notify_statuses", "JSON NULL"),
        ("reset_password_subject", "VARCHAR(200) NULL"),
        ("reset_password_is_html", "BOOL NOT NULL DEFAULT 0"),
        ("reset_password_template", "LONGTEXT NULL"),
        ("admin_reset_password_subject", "VARCHAR(200) NULL"),
        ("admin_reset_password_is_html", "BOOL NOT NULL DEFAULT 0"),
        ("admin_reset_password_template", "LONGTEXT NULL"),
    ]:
        await _add_column_if_missing(db, "system_setting", column, definition)
    return "SELECT 1;"


async def downgrade(db: BaseDBAsyncClient) -> str:
    for column in [
        "admin_reset_password_template",
        "admin_reset_password_is_html",
        "admin_reset_password_subject",
        "reset_password_template",
        "reset_password_is_html",
        "reset_password_subject",
        "ticket_mail_notify_statuses",
        "password_min_category_count",
        "password_min_length",
    ]:
        await _drop_column_if_present(db, "system_setting", column)
    return "SELECT 1;"
