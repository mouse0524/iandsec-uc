from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        SET @sk_parent_id := (SELECT `id` FROM `menu` WHERE `path` = '/skill-know' LIMIT 1);

        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT '批量上传任务', NULL, 'menu', 'material-symbols:task-outline', '/skill-know/upload-tasks', 8, @sk_parent_id, 0, '/skill-know/upload-tasks', 1, NULL
        WHERE @sk_parent_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know/upload-tasks');

        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT '知识包管理', NULL, 'menu', 'material-symbols:archive-outline', '/skill-know/packs', 9, @sk_parent_id, 0, '/skill-know/packs', 1, NULL
        WHERE @sk_parent_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know/packs');

        INSERT INTO `api` (`path`, `method`, `summary`, `tags`)
        SELECT '/api/v1/skill-know/upload/%', 'POST', 'Skill-Know批量上传接口', 'Skill-Know'
        WHERE NOT EXISTS (SELECT 1 FROM `api` WHERE `path` = '/api/v1/skill-know/upload/%' AND `method` = 'POST');

        INSERT INTO `api` (`path`, `method`, `summary`, `tags`)
        SELECT '/api/v1/skill-know/pack/%', 'POST', 'Skill-Know知识包接口', 'Skill-Know'
        WHERE NOT EXISTS (SELECT 1 FROM `api` WHERE `path` = '/api/v1/skill-know/pack/%' AND `method` = 'POST');
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DELETE FROM `menu` WHERE `path` IN ('/skill-know/upload-tasks', '/skill-know/packs');
        DELETE FROM `api` WHERE (`path` = '/api/v1/skill-know/upload/%' AND `method` = 'POST') OR (`path` = '/api/v1/skill-know/pack/%' AND `method` = 'POST');
    """
