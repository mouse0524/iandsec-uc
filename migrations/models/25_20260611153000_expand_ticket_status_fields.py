from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `ticket` MODIFY COLUMN `status` VARCHAR(32) NOT NULL DEFAULT 'pending_review';
        ALTER TABLE `ticket_action_log` MODIFY COLUMN `action` VARCHAR(32) NOT NULL;
        ALTER TABLE `ticket_action_log` MODIFY COLUMN `from_status` VARCHAR(32) NULL;
        ALTER TABLE `ticket_action_log` MODIFY COLUMN `to_status` VARCHAR(32) NOT NULL;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `ticket` MODIFY COLUMN `status` VARCHAR(32) NOT NULL DEFAULT 'pending_review';
        ALTER TABLE `ticket_action_log` MODIFY COLUMN `action` VARCHAR(32) NOT NULL;
        ALTER TABLE `ticket_action_log` MODIFY COLUMN `from_status` VARCHAR(32) NULL;
        ALTER TABLE `ticket_action_log` MODIFY COLUMN `to_status` VARCHAR(32) NOT NULL;
    """
