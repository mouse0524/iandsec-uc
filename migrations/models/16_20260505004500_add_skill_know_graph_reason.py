from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        SET @has_reason := (
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sk_context_relation'
              AND COLUMN_NAME = 'reason'
        );
        SET @sql := IF(
            @has_reason = 0,
            'ALTER TABLE `sk_context_relation` ADD COLUMN `reason` LONGTEXT NOT NULL COMMENT ''关系原因''',
            'SELECT 1'
        );
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;

        SET @sk_parent_id := (SELECT `id` FROM `menu` WHERE `path` = '/skill-know' LIMIT 1);

        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT '知识图谱', NULL, 'menu', 'material-symbols:account-tree-outline', '/skill-know/graph', 4, @sk_parent_id, 0, '/skill-know/graph', 1, NULL
        WHERE @sk_parent_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know/graph');

        UPDATE `menu` SET `order` = 5 WHERE `path` = '/skill-know/chat';
        UPDATE `menu` SET `order` = 6 WHERE `path` = '/skill-know/prompts';
        UPDATE `menu` SET `order` = 7 WHERE `path` = '/skill-know/quick-setup';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DELETE FROM `menu` WHERE `path` = '/skill-know/graph';
        SET @has_reason := (
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sk_context_relation'
              AND COLUMN_NAME = 'reason'
        );
        SET @sql := IF(
            @has_reason = 1,
            'ALTER TABLE `sk_context_relation` DROP COLUMN `reason`',
            'SELECT 1'
        );
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    """
