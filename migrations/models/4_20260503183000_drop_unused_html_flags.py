from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE `system_setting_item`
        SET `data` = JSON_REMOVE(`data`, '$.admin_reset_password_is_html', '$.ticket_notify_is_html')
        WHERE `section` = 'mail_template';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE `system_setting_item`
        SET `data` = JSON_SET(`data`, '$.admin_reset_password_is_html', false, '$.ticket_notify_is_html', false)
        WHERE `section` = 'mail_template';
    """
