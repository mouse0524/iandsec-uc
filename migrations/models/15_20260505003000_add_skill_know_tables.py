from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `sk_folder` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `uuid` VARCHAR(36) NOT NULL UNIQUE COMMENT '文件夹UUID',
            `name` VARCHAR(100) NOT NULL COMMENT '文件夹名称',
            `description` LONGTEXT NULL COMMENT '文件夹描述',
            `parent_id` BIGINT NULL COMMENT '父文件夹ID',
            `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序',
            `is_system` BOOL NOT NULL DEFAULT 0 COMMENT '是否系统文件夹',
            KEY `idx_sk_folder_uuid` (`uuid`),
            KEY `idx_sk_folder_name` (`name`),
            KEY `idx_sk_folder_parent` (`parent_id`),
            KEY `idx_sk_folder_order` (`sort_order`),
            KEY `idx_sk_folder_system` (`is_system`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `sk_skill` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `uuid` VARCHAR(36) NOT NULL UNIQUE COMMENT '技能UUID',
            `uri` VARCHAR(500) NULL UNIQUE COMMENT 'Skill URI',
            `name` VARCHAR(100) NOT NULL COMMENT '技能名称',
            `description` LONGTEXT NOT NULL COMMENT '技能描述',
            `type` VARCHAR(8) NOT NULL DEFAULT 'user' COMMENT '技能类型',
            `category` VARCHAR(9) NOT NULL DEFAULT 'prompt' COMMENT '技能分类',
            `abstract` LONGTEXT NULL COMMENT 'L0摘要',
            `overview` LONGTEXT NULL COMMENT 'L1概览',
            `content` LONGTEXT NOT NULL COMMENT 'L2完整内容',
            `trigger_keywords` JSON NOT NULL COMMENT '触发关键词',
            `trigger_intents` JSON NOT NULL COMMENT '触发意图',
            `always_apply` BOOL NOT NULL DEFAULT 0 COMMENT '是否总是应用',
            `version` VARCHAR(20) NOT NULL DEFAULT '1.0.0' COMMENT '版本',
            `author` VARCHAR(100) NULL COMMENT '作者',
            `is_active` BOOL NOT NULL DEFAULT 1 COMMENT '是否启用',
            `source_document_id` BIGINT NULL COMMENT '来源文档ID',
            `folder_id` BIGINT NULL COMMENT '所属文件夹ID',
            `priority` INT NOT NULL DEFAULT 100 COMMENT '优先级',
            `config` JSON NOT NULL COMMENT '扩展配置',
            KEY `idx_sk_skill_uuid` (`uuid`),
            KEY `idx_sk_skill_uri` (`uri`),
            KEY `idx_sk_skill_name` (`name`),
            KEY `idx_sk_skill_type` (`type`),
            KEY `idx_sk_skill_category` (`category`),
            KEY `idx_sk_skill_active` (`is_active`),
            KEY `idx_sk_skill_doc` (`source_document_id`),
            KEY `idx_sk_skill_folder` (`folder_id`),
            KEY `idx_sk_skill_priority` (`priority`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `sk_document` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `uuid` VARCHAR(36) NOT NULL UNIQUE COMMENT '文档UUID',
            `uri` VARCHAR(500) NULL UNIQUE COMMENT 'Document URI',
            `title` VARCHAR(200) NOT NULL COMMENT '文档标题',
            `description` LONGTEXT NULL COMMENT '文档描述',
            `filename` VARCHAR(255) NOT NULL COMMENT '文件名',
            `file_path` VARCHAR(500) NOT NULL COMMENT '文件路径',
            `file_size` BIGINT NOT NULL DEFAULT 0 COMMENT '文件大小',
            `file_type` VARCHAR(50) NOT NULL COMMENT '文件类型',
            `abstract` LONGTEXT NULL COMMENT 'L0摘要',
            `overview` LONGTEXT NULL COMMENT 'L1概览',
            `content` LONGTEXT NULL COMMENT 'L2完整内容',
            `content_hash` VARCHAR(64) NULL COMMENT '内容哈希',
            `status` VARCHAR(10) NOT NULL DEFAULT 'pending' COMMENT '处理状态',
            `error_message` LONGTEXT NULL COMMENT '错误信息',
            `category` VARCHAR(100) NULL COMMENT '分类',
            `tags` JSON NOT NULL COMMENT '标签',
            `folder_id` BIGINT NULL COMMENT '所属文件夹ID',
            `extra_metadata` JSON NOT NULL COMMENT '元数据',
            `skill_id` BIGINT NULL COMMENT '转换后的技能ID',
            `is_converted` BOOL NOT NULL DEFAULT 0 COMMENT '是否已转技能',
            `converted_at` DATETIME(6) NULL COMMENT '转换时间',
            KEY `idx_sk_doc_uuid` (`uuid`),
            KEY `idx_sk_doc_uri` (`uri`),
            KEY `idx_sk_doc_title` (`title`),
            KEY `idx_sk_doc_type` (`file_type`),
            KEY `idx_sk_doc_hash` (`content_hash`),
            KEY `idx_sk_doc_status` (`status`),
            KEY `idx_sk_doc_category` (`category`),
            KEY `idx_sk_doc_folder` (`folder_id`),
            KEY `idx_sk_doc_skill` (`skill_id`),
            KEY `idx_sk_doc_converted` (`is_converted`),
            KEY `idx_sk_doc_converted_at` (`converted_at`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `sk_vector_index` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `uri` VARCHAR(500) NOT NULL COMMENT '资源URI',
            `level` INT NOT NULL COMMENT '内容层级',
            `text` LONGTEXT NOT NULL COMMENT '索引文本',
            `vector_id` VARCHAR(500) NULL COMMENT 'Chroma向量ID',
            `extra_metadata` JSON NOT NULL COMMENT '索引元数据',
            UNIQUE KEY `uidx_sk_vector_uri_level` (`uri`, `level`),
            KEY `idx_sk_vector_uri` (`uri`),
            KEY `idx_sk_vector_level` (`level`),
            KEY `idx_sk_vector_id` (`vector_id`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `sk_conversation` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `uuid` VARCHAR(36) NOT NULL UNIQUE COMMENT '会话UUID',
            `title` VARCHAR(200) NULL COMMENT '会话标题',
            `extra_metadata` JSON NOT NULL COMMENT '元数据',
            KEY `idx_sk_conv_uuid` (`uuid`),
            KEY `idx_sk_conv_title` (`title`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `sk_message` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `uuid` VARCHAR(36) NOT NULL UNIQUE COMMENT '消息UUID',
            `conversation_id` BIGINT NOT NULL COMMENT '会话ID',
            `role` VARCHAR(9) NOT NULL COMMENT '消息角色',
            `content` LONGTEXT NOT NULL COMMENT '消息内容',
            `tool_calls` JSON NULL COMMENT '工具调用',
            `timeline` JSON NOT NULL COMMENT '时间线事件',
            `latency_ms` INT NULL COMMENT '响应耗时',
            `is_archived` BOOL NOT NULL DEFAULT 0 COMMENT '是否归档',
            `extra_metadata` JSON NOT NULL COMMENT '元数据',
            KEY `idx_sk_msg_uuid` (`uuid`),
            KEY `idx_sk_msg_conv` (`conversation_id`),
            KEY `idx_sk_msg_role` (`role`),
            KEY `idx_sk_msg_archived` (`is_archived`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `sk_prompt` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `key` VARCHAR(100) NOT NULL UNIQUE COMMENT '提示词Key',
            `category` VARCHAR(14) NOT NULL COMMENT '提示词分类',
            `name` VARCHAR(100) NOT NULL COMMENT '显示名称',
            `description` VARCHAR(500) NULL COMMENT '描述',
            `content` LONGTEXT NOT NULL COMMENT '提示词内容',
            `variables` JSON NOT NULL COMMENT '变量列表',
            `is_active` BOOL NOT NULL DEFAULT 1 COMMENT '是否启用',
            KEY `idx_sk_prompt_key` (`key`),
            KEY `idx_sk_prompt_category` (`category`),
            KEY `idx_sk_prompt_active` (`is_active`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `sk_system_config` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `key` VARCHAR(100) NOT NULL UNIQUE COMMENT '配置Key',
            `value` JSON NULL COMMENT '配置值',
            `description` LONGTEXT NULL COMMENT '描述',
            `is_sensitive` BOOL NOT NULL DEFAULT 0 COMMENT '是否敏感',
            `group` VARCHAR(50) NOT NULL DEFAULT 'general' COMMENT '分组',
            KEY `idx_sk_cfg_key` (`key`),
            KEY `idx_sk_cfg_group` (`group`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `sk_upload_task` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `uuid` VARCHAR(36) NOT NULL UNIQUE COMMENT '任务UUID',
            `status` VARCHAR(30) NOT NULL DEFAULT 'pending' COMMENT '任务状态',
            `total` INT NOT NULL DEFAULT 0 COMMENT '总数',
            `success_count` INT NOT NULL DEFAULT 0 COMMENT '成功数',
            `failed_count` INT NOT NULL DEFAULT 0 COMMENT '失败数',
            `result` JSON NOT NULL COMMENT '任务结果',
            `error_message` LONGTEXT NULL COMMENT '错误信息',
            KEY `idx_sk_task_uuid` (`uuid`),
            KEY `idx_sk_task_status` (`status`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `sk_context_relation` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `source_uri` VARCHAR(500) NOT NULL COMMENT '源URI',
            `target_uri` VARCHAR(500) NOT NULL COMMENT '目标URI',
            `relation_type` VARCHAR(50) NOT NULL COMMENT '关系类型',
            `reason` LONGTEXT NOT NULL COMMENT '关系原因',
            `weight` DOUBLE NOT NULL DEFAULT 1 COMMENT '权重',
            `extra_metadata` JSON NOT NULL COMMENT '元数据',
            KEY `idx_sk_rel_source` (`source_uri`),
            KEY `idx_sk_rel_target` (`target_uri`),
            KEY `idx_sk_rel_type` (`relation_type`)
        ) CHARACTER SET utf8mb4;

        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT 'Skill知识库', NULL, 'catalog', 'material-symbols:psychology-outline', '/skill-know', 50, 0, 0, 'Layout', 1, '/skill-know/skills'
        WHERE NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know');

        SET @sk_parent_id := (SELECT `id` FROM `menu` WHERE `path` = '/skill-know' LIMIT 1);

        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT '技能管理', NULL, 'menu', 'material-symbols:sparkles-outline', '/skill-know/skills', 1, @sk_parent_id, 0, '/skill-know/skills', 1, NULL
        WHERE NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know/skills');
        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT '文档管理', NULL, 'menu', 'material-symbols:docs-outline', '/skill-know/documents', 2, @sk_parent_id, 0, '/skill-know/documents', 1, NULL
        WHERE NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know/documents');
        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT '知识搜索', NULL, 'menu', 'material-symbols:search', '/skill-know/search', 3, @sk_parent_id, 0, '/skill-know/search', 1, NULL
        WHERE NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know/search');
        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT '知识图谱', NULL, 'menu', 'material-symbols:account-tree-outline', '/skill-know/graph', 4, @sk_parent_id, 0, '/skill-know/graph', 1, NULL
        WHERE NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know/graph');
        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT '智能对话', NULL, 'menu', 'material-symbols:chat-outline', '/skill-know/chat', 5, @sk_parent_id, 0, '/skill-know/chat', 1, NULL
        WHERE NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know/chat');
        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT '提示词管理', NULL, 'menu', 'material-symbols:edit-note-outline', '/skill-know/prompts', 6, @sk_parent_id, 0, '/skill-know/prompts', 1, NULL
        WHERE NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know/prompts');
        INSERT INTO `menu` (`name`, `remark`, `menu_type`, `icon`, `path`, `order`, `parent_id`, `is_hidden`, `component`, `keepalive`, `redirect`)
        SELECT '快速设置', NULL, 'menu', 'material-symbols:settings-outline', '/skill-know/quick-setup', 7, @sk_parent_id, 0, '/skill-know/quick-setup', 1, NULL
        WHERE NOT EXISTS (SELECT 1 FROM `menu` WHERE `path` = '/skill-know/quick-setup');

        INSERT INTO `api` (`path`, `method`, `summary`, `tags`)
        SELECT '/api/v1/skill-know/%', 'GET', 'Skill-Know查询接口', 'Skill-Know'
        WHERE NOT EXISTS (SELECT 1 FROM `api` WHERE `path` = '/api/v1/skill-know/%' AND `method` = 'GET');
        INSERT INTO `api` (`path`, `method`, `summary`, `tags`)
        SELECT '/api/v1/skill-know/%', 'POST', 'Skill-Know写入接口', 'Skill-Know'
        WHERE NOT EXISTS (SELECT 1 FROM `api` WHERE `path` = '/api/v1/skill-know/%' AND `method` = 'POST');
        INSERT INTO `api` (`path`, `method`, `summary`, `tags`)
        SELECT '/api/v1/skill-know/%', 'DELETE', 'Skill-Know删除接口', 'Skill-Know'
        WHERE NOT EXISTS (SELECT 1 FROM `api` WHERE `path` = '/api/v1/skill-know/%' AND `method` = 'DELETE');
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DELETE FROM `api` WHERE `path` = '/api/v1/skill-know/%';
        DELETE FROM `menu` WHERE `path` LIKE '/skill-know%';
        DROP TABLE IF EXISTS `sk_context_relation`;
        DROP TABLE IF EXISTS `sk_upload_task`;
        DROP TABLE IF EXISTS `sk_system_config`;
        DROP TABLE IF EXISTS `sk_prompt`;
        DROP TABLE IF EXISTS `sk_message`;
        DROP TABLE IF EXISTS `sk_conversation`;
        DROP TABLE IF EXISTS `sk_vector_index`;
        DROP TABLE IF EXISTS `sk_document`;
        DROP TABLE IF EXISTS `sk_skill`;
        DROP TABLE IF EXISTS `sk_folder`;
    """
