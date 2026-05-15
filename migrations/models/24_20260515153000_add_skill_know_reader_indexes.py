from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `sk_document_section` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `uuid` VARCHAR(36) NOT NULL UNIQUE COMMENT '章节UUID',
            `document_id` BIGINT NOT NULL COMMENT '文档ID',
            `section_key` VARCHAR(100) NOT NULL COMMENT '章节Key',
            `heading` VARCHAR(300) NULL COMMENT '章节标题',
            `heading_path` VARCHAR(1000) NULL COMMENT '章节路径',
            `level` INT NOT NULL DEFAULT 0 COMMENT '标题层级',
            `start_line` INT NOT NULL COMMENT '起始行号',
            `end_line` INT NOT NULL COMMENT '结束行号',
            `text` LONGTEXT NOT NULL COMMENT '章节原文',
            `text_preview` LONGTEXT NULL COMMENT '章节预览',
            `keywords` JSON NOT NULL COMMENT '关键词',
            `token_count` INT NOT NULL DEFAULT 0 COMMENT '粗略Token数',
            `extra_metadata` JSON NOT NULL COMMENT '元数据',
            UNIQUE KEY `uidx_sk_doc_section_doc_key` (`document_id`, `section_key`),
            KEY `idx_sk_doc_section_uuid` (`uuid`),
            KEY `idx_sk_doc_section_doc` (`document_id`),
            KEY `idx_sk_doc_section_key` (`section_key`),
            KEY `idx_sk_doc_section_heading` (`heading`),
            KEY `idx_sk_doc_section_level` (`level`),
            KEY `idx_sk_doc_section_start` (`start_line`),
            KEY `idx_sk_doc_section_end` (`end_line`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `sk_document_line` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `document_id` BIGINT NOT NULL COMMENT '文档ID',
            `line_no` INT NOT NULL COMMENT '行号',
            `content` LONGTEXT NOT NULL COMMENT '行内容',
            UNIQUE KEY `uidx_sk_doc_line_doc_line` (`document_id`, `line_no`),
            KEY `idx_sk_doc_line_doc` (`document_id`),
            KEY `idx_sk_doc_line_no` (`line_no`)
        ) CHARACTER SET utf8mb4;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `sk_document_line`;
        DROP TABLE IF EXISTS `sk_document_section`;
    """
