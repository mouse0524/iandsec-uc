from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE `menu`
        SET `icon` = 'material-symbols:auto-awesome-outline'
        WHERE `component` = '/skill-know/skills';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE `menu`
        SET `icon` = 'material-symbols:sparkles-outline'
        WHERE `component` = '/skill-know/skills';
    """
