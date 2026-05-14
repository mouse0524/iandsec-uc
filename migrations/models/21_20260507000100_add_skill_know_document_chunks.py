from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `sk_document_chunk` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `uuid` VARCHAR(36) NOT NULL UNIQUE COMMENT 'Chunk UUID',
            `document_id` BIGINT NOT NULL COMMENT '文档ID',
            `uri` VARCHAR(500) NOT NULL UNIQUE COMMENT 'Chunk URI',
            `chunk_index` INT NOT NULL COMMENT '分块序号',
            `heading` VARCHAR(300) NULL COMMENT '标题路径',
            `content` LONGTEXT NOT NULL COMMENT 'Markdown分块内容',
            `content_hash` VARCHAR(64) NOT NULL COMMENT '内容哈希',
            `token_count` INT NOT NULL DEFAULT 0 COMMENT '粗略Token数',
            `vector_id` VARCHAR(500) NULL COMMENT 'Chroma向量ID',
            `extra_metadata` JSON NOT NULL COMMENT '元数据',
            UNIQUE KEY `uidx_sk_doc_chunk_doc_idx` (`document_id`, `chunk_index`),
            KEY `idx_sk_doc_chunk_uuid` (`uuid`),
            KEY `idx_sk_doc_chunk_doc` (`document_id`),
            KEY `idx_sk_doc_chunk_uri` (`uri`),
            KEY `idx_sk_doc_chunk_idx` (`chunk_index`),
            KEY `idx_sk_doc_chunk_hash` (`content_hash`),
            KEY `idx_sk_doc_chunk_vector` (`vector_id`)
        ) CHARACTER SET utf8mb4;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `sk_document_chunk`;
    """
