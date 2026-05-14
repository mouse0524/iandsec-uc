from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `user` ADD COLUMN `token_version` INT NOT NULL DEFAULT 0 COMMENT '令牌版本';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `user` DROP COLUMN `token_version`;
    """
