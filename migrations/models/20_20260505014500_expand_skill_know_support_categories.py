from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `sk_skill` MODIFY COLUMN `category` VARCHAR(32) NOT NULL DEFAULT 'prompt' COMMENT '技能分类';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `sk_skill` MODIFY COLUMN `category` VARCHAR(9) NOT NULL DEFAULT 'prompt' COMMENT '技能分类';
    """
