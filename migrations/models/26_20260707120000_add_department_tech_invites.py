from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `dept` ADD COLUMN `tech_ids` JSON NULL;
        ALTER TABLE `partner_registration` ADD COLUMN `invite_code` VARCHAR(32) NULL;
        CREATE TABLE IF NOT EXISTS `partner_invite` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `code` VARCHAR(32) NOT NULL UNIQUE,
            `created_by` BIGINT NOT NULL,
            `used_by` BIGINT NULL,
            `used_at` DATETIME(6) NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY `idx_partner_invite_code` (`code`),
            KEY `idx_partner_invite_created_by` (`created_by`),
            KEY `idx_partner_invite_used_by` (`used_by`)
        );
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `partner_invite`;
        ALTER TABLE `partner_registration` DROP COLUMN `invite_code`;
        ALTER TABLE `dept` DROP COLUMN `tech_ids`;
    """
