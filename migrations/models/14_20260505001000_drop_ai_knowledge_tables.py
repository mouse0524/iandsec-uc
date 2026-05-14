from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        DELETE FROM `system_setting_item` WHERE `section` = 'ai_kb';

        DELETE FROM `menu`
        WHERE `path` = '/ai-kb'
           OR `component` IN ('/system/ai-kb', '/system/ai-kb-manage', '/ai-kb/bases', '/ai-kb/nodes', '/ai-kb/import', '/ai-kb/releases', '/ai-kb/conversations', '/ai-kb/feedback');

        DELETE FROM `api`
        WHERE `path` LIKE '/api/v1/ai-kb%';

        DROP TABLE IF EXISTS `ai_knowledge_feedback`;
        DROP TABLE IF EXISTS `ai_knowledge_reference`;
        DROP TABLE IF EXISTS `ai_knowledge_message`;
        DROP TABLE IF EXISTS `ai_knowledge_conversation`;
        DROP TABLE IF EXISTS `ai_knowledge_import_task`;
        DROP TABLE IF EXISTS `ai_knowledge_app`;
        DROP TABLE IF EXISTS `ai_knowledge_kb_release`;
        DROP TABLE IF EXISTS `ai_knowledge_node_release`;
        DROP TABLE IF EXISTS `ai_knowledge_node`;
        DROP TABLE IF EXISTS `ai_knowledge_nav`;
        DROP TABLE IF EXISTS `ai_knowledge_kb_user`;
        DROP TABLE IF EXISTS `ai_knowledge_base`;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `ai_knowledge_base` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `name` VARCHAR(120) NOT NULL,
            `slug` VARCHAR(120) NOT NULL UNIQUE,
            `description` LONGTEXT NULL,
            `is_default` BOOL NOT NULL DEFAULT 0,
            `is_enabled` BOOL NOT NULL DEFAULT 1,
            `is_public` BOOL NOT NULL DEFAULT 0,
            `settings` JSON NOT NULL,
            `created_by` BIGINT NULL,
            KEY `idx_ai_kb_base_name` (`name`),
            KEY `idx_ai_kb_base_slug` (`slug`)
        ) CHARACTER SET utf8mb4;
    """
