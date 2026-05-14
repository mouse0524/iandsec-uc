from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `global_notice` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `title` VARCHAR(100) NULL COMMENT '通知标题',
            `content_html` LONGTEXT NOT NULL COMMENT '通知内容HTML',
            `target_type` VARCHAR(10) NOT NULL COMMENT '发送范围类型',
            `target_role_ids` JSON NOT NULL COMMENT '目标角色ID列表',
            `target_user_ids` JSON NOT NULL COMMENT '目标用户ID列表',
            `created_by` BIGINT NOT NULL COMMENT '创建人ID',
            `is_active` BOOL NOT NULL DEFAULT 1 COMMENT '是否生效',
            KEY `idx_global_notice_created_1` (`created_at`),
            KEY `idx_global_notice_updated_1` (`updated_at`),
            KEY `idx_global_notice_target_type_1` (`target_type`),
            KEY `idx_global_notice_created_by_1` (`created_by`),
            KEY `idx_global_notice_is_active_1` (`is_active`)
        ) CHARACTER SET utf8mb4;

        CREATE TABLE IF NOT EXISTS `global_notice_user` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `notice_id` BIGINT NOT NULL COMMENT '通知ID',
            `user_id` BIGINT NOT NULL COMMENT '接收用户ID',
            `is_read` BOOL NOT NULL DEFAULT 0 COMMENT '是否已读',
            `read_at` DATETIME(6) NULL COMMENT '已读时间',
            `delivered_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '投递时间',
            UNIQUE KEY `uidx_global_notice_user_notice_user_1` (`notice_id`, `user_id`),
            KEY `idx_global_notice_user_created_1` (`created_at`),
            KEY `idx_global_notice_user_updated_1` (`updated_at`),
            KEY `idx_global_notice_user_notice_id_1` (`notice_id`),
            KEY `idx_global_notice_user_user_id_1` (`user_id`),
            KEY `idx_global_notice_user_is_read_1` (`is_read`),
            KEY `idx_global_notice_user_read_at_1` (`read_at`),
            KEY `idx_global_notice_user_delivered_at_1` (`delivered_at`)
        ) CHARACTER SET utf8mb4;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `global_notice_user`;
        DROP TABLE IF EXISTS `global_notice`;
    """
