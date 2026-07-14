from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `issue_workflow_transition` ALTER COLUMN `author_allowed` SET DEFAULT 1;
        ALTER TABLE `issue_workflow_transition` ALTER COLUMN `assignee_required` SET DEFAULT 1;
        DROP TABLE IF EXISTS `rd_task`;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `issue_workflow_transition` ALTER COLUMN `author_allowed` SET DEFAULT 0;
        ALTER TABLE `issue_workflow_transition` ALTER COLUMN `assignee_required` SET DEFAULT 0;"""
