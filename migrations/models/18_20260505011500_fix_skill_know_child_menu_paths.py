from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE `menu` SET `path` = 'skills' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/skills';
        UPDATE `menu` SET `path` = 'documents' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/documents';
        UPDATE `menu` SET `path` = 'search' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/search';
        UPDATE `menu` SET `path` = 'graph' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/graph';
        UPDATE `menu` SET `path` = 'chat' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/chat';
        UPDATE `menu` SET `path` = 'prompts' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/prompts';
        UPDATE `menu` SET `path` = 'quick-setup' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/quick-setup';
        UPDATE `menu` SET `path` = 'upload-tasks' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/upload-tasks';
        UPDATE `menu` SET `path` = 'packs' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/packs';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE `menu` SET `path` = '/skill-know/skills' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/skills';
        UPDATE `menu` SET `path` = '/skill-know/documents' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/documents';
        UPDATE `menu` SET `path` = '/skill-know/search' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/search';
        UPDATE `menu` SET `path` = '/skill-know/graph' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/graph';
        UPDATE `menu` SET `path` = '/skill-know/chat' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/chat';
        UPDATE `menu` SET `path` = '/skill-know/prompts' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/prompts';
        UPDATE `menu` SET `path` = '/skill-know/quick-setup' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/quick-setup';
        UPDATE `menu` SET `path` = '/skill-know/upload-tasks' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/upload-tasks';
        UPDATE `menu` SET `path` = '/skill-know/packs' WHERE `parent_id` = (SELECT `id` FROM (SELECT `id` FROM `menu` WHERE `path`='/skill-know' LIMIT 1) t) AND `component` = '/skill-know/packs';
    """
