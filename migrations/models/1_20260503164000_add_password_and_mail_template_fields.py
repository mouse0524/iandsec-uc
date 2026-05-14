from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `system_setting` ADD `password_min_length` INT NOT NULL COMMENT '密码最小长度' DEFAULT 8;
        ALTER TABLE `system_setting` ADD `password_min_category_count` INT NOT NULL COMMENT '密码最少字符类别数' DEFAULT 2;
        ALTER TABLE `system_setting` ADD `ticket_mail_notify_statuses` JSON NOT NULL COMMENT '工单状态触发邮件通知';
        ALTER TABLE `system_setting` ADD `reset_password_subject` VARCHAR(200) NOT NULL COMMENT '找回密码验证码邮件主题' DEFAULT '密码重置验证码';
        ALTER TABLE `system_setting` ADD `reset_password_is_html` BOOL NOT NULL COMMENT '找回密码验证码模板是否HTML' DEFAULT 0;
        ALTER TABLE `system_setting` ADD `reset_password_template` LONGTEXT NOT NULL COMMENT '找回密码验证码邮件模板';
        ALTER TABLE `system_setting` ADD `admin_reset_password_subject` VARCHAR(200) NOT NULL COMMENT '管理员重置密码通知邮件主题' DEFAULT '账号密码已重置';
        ALTER TABLE `system_setting` ADD `admin_reset_password_is_html` BOOL NOT NULL COMMENT '管理员重置密码通知是否HTML' DEFAULT 0;
        ALTER TABLE `system_setting` ADD `admin_reset_password_template` LONGTEXT NOT NULL COMMENT '管理员重置密码通知邮件模板';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `system_setting` DROP COLUMN `admin_reset_password_template`;
        ALTER TABLE `system_setting` DROP COLUMN `admin_reset_password_is_html`;
        ALTER TABLE `system_setting` DROP COLUMN `admin_reset_password_subject`;
        ALTER TABLE `system_setting` DROP COLUMN `reset_password_template`;
        ALTER TABLE `system_setting` DROP COLUMN `reset_password_is_html`;
        ALTER TABLE `system_setting` DROP COLUMN `reset_password_subject`;
        ALTER TABLE `system_setting` DROP COLUMN `ticket_mail_notify_statuses`;
        ALTER TABLE `system_setting` DROP COLUMN `password_min_category_count`;
        ALTER TABLE `system_setting` DROP COLUMN `password_min_length`;
    """
