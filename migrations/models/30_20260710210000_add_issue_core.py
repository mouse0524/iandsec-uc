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


async def _add_column_if_missing(db: BaseDBAsyncClient, table: str, column: str, definition: str) -> None:
    if await _table_exists(db, table) and not await _column_exists(db, table, column):
        await db.execute_script(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")


async def _drop_column_if_present(db: BaseDBAsyncClient, table: str, column: str) -> None:
    if await _table_exists(db, table) and await _column_exists(db, table, column):
        await db.execute_script(f"ALTER TABLE `{table}` DROP COLUMN `{column}`")


async def _add_index_if_missing(db: BaseDBAsyncClient, table: str, index_name: str, columns: str) -> None:
    if await _table_exists(db, table) and not await _index_exists(db, table, index_name):
        await db.execute_script(f"ALTER TABLE `{table}` ADD KEY `{index_name}` ({columns})")


async def upgrade(db: BaseDBAsyncClient) -> str:
    for column, definition in [
        ("issue_project_id", "BIGINT NULL"),
        ("issue_tracker_id", "BIGINT NULL"),
        ("issue_status_id", "BIGINT NULL"),
        ("issue_priority_id", "BIGINT NULL"),
        ("issue_category_id", "BIGINT NULL"),
        ("issue_fixed_version_id", "BIGINT NULL"),
        ("parent_issue_id", "BIGINT NULL"),
        ("root_issue_id", "BIGINT NULL"),
        ("assigned_to_id", "BIGINT NULL"),
        ("start_date", "DATE NULL"),
        ("due_date", "DATE NULL"),
        ("done_ratio", "INT NOT NULL DEFAULT 0"),
        ("estimated_hours", "DOUBLE NULL"),
        ("closed_at", "DATETIME(6) NULL"),
        ("is_private", "BOOL NOT NULL DEFAULT 0"),
        ("lock_version", "INT NOT NULL DEFAULT 0"),
    ]:
        await _add_column_if_missing(db, "ticket", column, definition)

    for index_name, columns in [
        ("idx_ticket_issue_project", "`issue_project_id`"),
        ("idx_ticket_issue_tracker", "`issue_tracker_id`"),
        ("idx_ticket_issue_status", "`issue_status_id`"),
        ("idx_ticket_issue_priority", "`issue_priority_id`"),
        ("idx_ticket_issue_category", "`issue_category_id`"),
        ("idx_ticket_issue_version", "`issue_fixed_version_id`"),
        ("idx_ticket_parent_issue", "`parent_issue_id`"),
        ("idx_ticket_root_issue", "`root_issue_id`"),
        ("idx_ticket_assigned_to", "`assigned_to_id`"),
        ("idx_ticket_start_date", "`start_date`"),
        ("idx_ticket_due_date", "`due_date`"),
        ("idx_ticket_closed_at", "`closed_at`"),
        ("idx_ticket_is_private", "`is_private`"),
    ]:
        await _add_index_if_missing(db, "ticket", index_name, columns)

    await db.execute_script(
        """
        CREATE TABLE IF NOT EXISTS `project_member` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `project_id` BIGINT NOT NULL,
            `user_id` BIGINT NOT NULL,
            `role_id` BIGINT NOT NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            UNIQUE KEY `uidx_project_member` (`project_id`, `user_id`, `role_id`),
            KEY `idx_project_member_project` (`project_id`),
            KEY `idx_project_member_user` (`user_id`),
            KEY `idx_project_member_role` (`role_id`)
        );

        CREATE TABLE IF NOT EXISTS `issue_tracker` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `name` VARCHAR(60) NOT NULL UNIQUE,
            `description` TEXT NULL,
            `position` INT NOT NULL DEFAULT 0,
            `default_status_id` BIGINT NULL,
            `is_in_roadmap` BOOL NOT NULL DEFAULT 1,
            `copy_workflow_from_id` BIGINT NULL,
            `is_active` BOOL NOT NULL DEFAULT 1,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_issue_tracker_name` (`name`),
            KEY `idx_issue_tracker_position` (`position`),
            KEY `idx_issue_tracker_default_status` (`default_status_id`),
            KEY `idx_issue_tracker_active` (`is_active`)
        );

        CREATE TABLE IF NOT EXISTS `issue_status` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `name` VARCHAR(60) NOT NULL UNIQUE,
            `position` INT NOT NULL DEFAULT 0,
            `is_closed` BOOL NOT NULL DEFAULT 0,
            `is_default` BOOL NOT NULL DEFAULT 0,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_issue_status_name` (`name`),
            KEY `idx_issue_status_position` (`position`),
            KEY `idx_issue_status_closed` (`is_closed`),
            KEY `idx_issue_status_default` (`is_default`)
        );

        CREATE TABLE IF NOT EXISTS `issue_priority` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `name` VARCHAR(60) NOT NULL UNIQUE,
            `position` INT NOT NULL DEFAULT 0,
            `is_default` BOOL NOT NULL DEFAULT 0,
            `active` BOOL NOT NULL DEFAULT 1,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_issue_priority_name` (`name`),
            KEY `idx_issue_priority_position` (`position`),
            KEY `idx_issue_priority_default` (`is_default`),
            KEY `idx_issue_priority_active` (`active`)
        );

        CREATE TABLE IF NOT EXISTS `issue_category` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `project_id` BIGINT NOT NULL,
            `name` VARCHAR(120) NOT NULL,
            `assigned_to_id` BIGINT NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            UNIQUE KEY `uidx_issue_category_project_name` (`project_id`, `name`),
            KEY `idx_issue_category_project` (`project_id`),
            KEY `idx_issue_category_assigned` (`assigned_to_id`)
        );

        CREATE TABLE IF NOT EXISTS `issue_version` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `project_id` BIGINT NOT NULL,
            `name` VARCHAR(120) NOT NULL,
            `description` TEXT NULL,
            `status` VARCHAR(20) NOT NULL DEFAULT 'open',
            `sharing` VARCHAR(20) NOT NULL DEFAULT 'none',
            `effective_date` DATE NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            UNIQUE KEY `uidx_issue_version_project_name` (`project_id`, `name`),
            KEY `idx_issue_version_project` (`project_id`),
            KEY `idx_issue_version_status` (`status`),
            KEY `idx_issue_version_sharing` (`sharing`),
            KEY `idx_issue_version_effective` (`effective_date`)
        );

        CREATE TABLE IF NOT EXISTS `issue_custom_field` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `type` VARCHAR(30) NOT NULL DEFAULT 'issue',
            `name` VARCHAR(120) NOT NULL,
            `field_format` VARCHAR(20) NOT NULL DEFAULT 'string',
            `possible_values` JSON NULL,
            `default_value` TEXT NULL,
            `is_required` BOOL NOT NULL DEFAULT 0,
            `is_filter` BOOL NOT NULL DEFAULT 0,
            `searchable` BOOL NOT NULL DEFAULT 0,
            `multiple` BOOL NOT NULL DEFAULT 0,
            `visible` BOOL NOT NULL DEFAULT 1,
            `position` INT NOT NULL DEFAULT 0,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_issue_cf_type` (`type`),
            KEY `idx_issue_cf_name` (`name`),
            KEY `idx_issue_cf_format` (`field_format`),
            KEY `idx_issue_cf_required` (`is_required`),
            KEY `idx_issue_cf_filter` (`is_filter`),
            KEY `idx_issue_cf_visible` (`visible`),
            KEY `idx_issue_cf_position` (`position`)
        );

        CREATE TABLE IF NOT EXISTS `issue_custom_field_binding` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `custom_field_id` BIGINT NOT NULL,
            `tracker_id` BIGINT NULL,
            `project_id` BIGINT NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_issue_cfb_cf` (`custom_field_id`),
            KEY `idx_issue_cfb_tracker` (`tracker_id`),
            KEY `idx_issue_cfb_project` (`project_id`)
        );

        CREATE TABLE IF NOT EXISTS `issue_custom_value` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `customized_type` VARCHAR(30) NOT NULL DEFAULT 'Issue',
            `customized_id` BIGINT NOT NULL,
            `custom_field_id` BIGINT NOT NULL,
            `value` TEXT NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_issue_cv_customized` (`customized_type`, `customized_id`),
            KEY `idx_issue_cv_cf` (`custom_field_id`)
        );

        CREATE TABLE IF NOT EXISTS `issue_workflow_transition` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `role_id` BIGINT NOT NULL,
            `tracker_id` BIGINT NOT NULL,
            `old_status_id` BIGINT NOT NULL,
            `new_status_id` BIGINT NOT NULL,
            `assignee_required` BOOL NOT NULL DEFAULT 1,
            `author_allowed` BOOL NOT NULL DEFAULT 1,
            `assignee_allowed` BOOL NOT NULL DEFAULT 1,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            UNIQUE KEY `uidx_issue_wf_transition` (`role_id`, `tracker_id`, `old_status_id`, `new_status_id`),
            KEY `idx_issue_wft_role` (`role_id`),
            KEY `idx_issue_wft_tracker` (`tracker_id`),
            KEY `idx_issue_wft_old` (`old_status_id`),
            KEY `idx_issue_wft_new` (`new_status_id`)
        );

        CREATE TABLE IF NOT EXISTS `issue_workflow_permission` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `role_id` BIGINT NOT NULL,
            `tracker_id` BIGINT NOT NULL,
            `old_status_id` BIGINT NOT NULL,
            `field_name` VARCHAR(120) NOT NULL,
            `rule` VARCHAR(20) NOT NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            UNIQUE KEY `uidx_issue_wf_permission` (`role_id`, `tracker_id`, `old_status_id`, `field_name`, `rule`),
            KEY `idx_issue_wfp_role` (`role_id`),
            KEY `idx_issue_wfp_tracker` (`tracker_id`),
            KEY `idx_issue_wfp_status` (`old_status_id`),
            KEY `idx_issue_wfp_field` (`field_name`),
            KEY `idx_issue_wfp_rule` (`rule`)
        );

        CREATE TABLE IF NOT EXISTS `issue_watcher` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `watchable_type` VARCHAR(30) NOT NULL DEFAULT 'Issue',
            `watchable_id` BIGINT NOT NULL,
            `user_id` BIGINT NOT NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            UNIQUE KEY `uidx_issue_watcher` (`watchable_type`, `watchable_id`, `user_id`),
            KEY `idx_issue_watcher_target` (`watchable_type`, `watchable_id`),
            KEY `idx_issue_watcher_user` (`user_id`)
        );

        CREATE TABLE IF NOT EXISTS `issue_relation` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `issue_from_id` BIGINT NOT NULL,
            `issue_to_id` BIGINT NOT NULL,
            `relation_type` VARCHAR(20) NOT NULL,
            `delay` INT NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            UNIQUE KEY `uidx_issue_relation` (`issue_from_id`, `issue_to_id`, `relation_type`),
            KEY `idx_issue_relation_from` (`issue_from_id`),
            KEY `idx_issue_relation_to` (`issue_to_id`),
            KEY `idx_issue_relation_type` (`relation_type`)
        );

        CREATE TABLE IF NOT EXISTS `issue_time_entry` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `project_id` BIGINT NOT NULL,
            `issue_id` BIGINT NULL,
            `user_id` BIGINT NOT NULL,
            `activity_id` BIGINT NULL,
            `hours` DOUBLE NOT NULL,
            `comments` VARCHAR(255) NULL,
            `spent_on` DATE NOT NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_issue_time_project` (`project_id`),
            KEY `idx_issue_time_issue` (`issue_id`),
            KEY `idx_issue_time_user` (`user_id`),
            KEY `idx_issue_time_activity` (`activity_id`),
            KEY `idx_issue_time_spent` (`spent_on`)
        );

        CREATE TABLE IF NOT EXISTS `issue_journal` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `journalized_type` VARCHAR(30) NOT NULL DEFAULT 'Issue',
            `journalized_id` BIGINT NOT NULL,
            `user_id` BIGINT NOT NULL,
            `notes` TEXT NULL,
            `private_notes` BOOL NOT NULL DEFAULT 0,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_issue_journal_target` (`journalized_type`, `journalized_id`),
            KEY `idx_issue_journal_user` (`user_id`),
            KEY `idx_issue_journal_private` (`private_notes`)
        );

        CREATE TABLE IF NOT EXISTS `issue_journal_detail` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `journal_id` BIGINT NOT NULL,
            `property` VARCHAR(30) NOT NULL DEFAULT 'attr',
            `prop_key` VARCHAR(120) NOT NULL,
            `old_value` TEXT NULL,
            `value` TEXT NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_issue_jd_journal` (`journal_id`),
            KEY `idx_issue_jd_property` (`property`),
            KEY `idx_issue_jd_key` (`prop_key`)
        );

        CREATE TABLE IF NOT EXISTS `issue_query` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `name` VARCHAR(120) NOT NULL,
            `user_id` BIGINT NULL,
            `project_id` BIGINT NULL,
            `visibility` VARCHAR(20) NOT NULL DEFAULT 'private',
            `filters` JSON NULL,
            `columns` JSON NULL,
            `sort_criteria` JSON NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_issue_query_name` (`name`),
            KEY `idx_issue_query_user` (`user_id`),
            KEY `idx_issue_query_project` (`project_id`),
            KEY `idx_issue_query_visibility` (`visibility`)
        )
        """
    )
    return "SELECT 1;"


async def downgrade(db: BaseDBAsyncClient) -> str:
    for table in [
        "issue_query",
        "issue_journal_detail",
        "issue_journal",
        "issue_time_entry",
        "issue_relation",
        "issue_watcher",
        "issue_workflow_permission",
        "issue_workflow_transition",
        "issue_custom_value",
        "issue_custom_field_binding",
        "issue_custom_field",
        "issue_version",
        "issue_category",
        "issue_priority",
        "issue_status",
        "issue_tracker",
        "project_member",
    ]:
        await db.execute_script(f"DROP TABLE IF EXISTS `{table}`")

    for column in [
        "lock_version",
        "is_private",
        "closed_at",
        "estimated_hours",
        "done_ratio",
        "due_date",
        "start_date",
        "assigned_to_id",
        "root_issue_id",
        "parent_issue_id",
        "issue_fixed_version_id",
        "issue_category_id",
        "issue_priority_id",
        "issue_status_id",
        "issue_tracker_id",
        "issue_project_id",
    ]:
        await _drop_column_if_present(db, "ticket", column)

    return "SELECT 1;"
