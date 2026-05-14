from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `system_setting_item` (
            `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            `section` VARCHAR(50) NOT NULL UNIQUE COMMENT '配置分组',
            `data` JSON NOT NULL COMMENT '分组配置JSON',
            KEY `idx_system_sett_item_created_1` (`created_at`),
            KEY `idx_system_sett_item_updated_1` (`updated_at`),
            KEY `idx_system_sett_item_section_1` (`section`)
        ) CHARACTER SET utf8mb4;

        INSERT INTO `system_setting_item` (`section`, `data`)
        SELECT 'site', JSON_OBJECT(
            'site_title', `site_title`,
            'site_logo', `site_logo`,
            'allow_partner_register', `allow_partner_register`
        )
        FROM `system_setting`
        ORDER BY `id` ASC
        LIMIT 1
        ON DUPLICATE KEY UPDATE `data` = VALUES(`data`);

        INSERT INTO `system_setting_item` (`section`, `data`)
        SELECT 'ticket', JSON_OBJECT(
            'ticket_attachment_extensions', `ticket_attachment_extensions`,
            'ticket_project_phases', `ticket_project_phases`,
            'ticket_categories', `ticket_categories`,
            'ticket_root_causes', `ticket_root_causes`,
            'ticket_description_templates', `ticket_description_templates`
        )
        FROM `system_setting`
        ORDER BY `id` ASC
        LIMIT 1
        ON DUPLICATE KEY UPDATE `data` = VALUES(`data`);

        INSERT INTO `system_setting_item` (`section`, `data`)
        SELECT 'login_security', JSON_OBJECT(
            'login_security_enabled', `login_security_enabled`,
            'login_account_ip_fail_limit', `login_account_ip_fail_limit`,
            'login_account_ip_lock_minutes', `login_account_ip_lock_minutes`,
            'login_ip_fail_limit', `login_ip_fail_limit`,
            'login_ip_lock_minutes', `login_ip_lock_minutes`,
            'login_fail_window_minutes', `login_fail_window_minutes`,
            'login_generic_error_enabled', `login_generic_error_enabled`,
            'password_min_length', `password_min_length`,
            'password_required_categories', JSON_ARRAY('letter', 'digit')
        )
        FROM `system_setting`
        ORDER BY `id` ASC
        LIMIT 1
        ON DUPLICATE KEY UPDATE `data` = VALUES(`data`);

        INSERT INTO `system_setting_item` (`section`, `data`)
        SELECT 'ticket_notify', JSON_OBJECT(
            'ticket_notify_by_role', JSON_OBJECT(
                '用户', JSON_ARRAY('cs_rejected', 'tech_rejected', 'done'),
                '代理商', JSON_ARRAY('cs_rejected', 'tech_rejected', 'done'),
                '客服', JSON_ARRAY('pending_review'),
                '技术', JSON_ARRAY('tech_processing')
            )
        )
        FROM `system_setting`
        ORDER BY `id` ASC
        LIMIT 1
        ON DUPLICATE KEY UPDATE `data` = VALUES(`data`);

        INSERT INTO `system_setting_item` (`section`, `data`)
        SELECT 'mail', JSON_OBJECT(
            'smtp_host', `smtp_host`,
            'smtp_port', `smtp_port`,
            'smtp_username', `smtp_username`,
            'smtp_password', `smtp_password`,
            'smtp_sender', `smtp_sender`,
            'smtp_sender_name', `smtp_sender_name`,
            'smtp_use_tls', `smtp_use_tls`,
            'smtp_use_ssl', `smtp_use_ssl`
        )
        FROM `system_setting`
        ORDER BY `id` ASC
        LIMIT 1
        ON DUPLICATE KEY UPDATE `data` = VALUES(`data`);

        INSERT INTO `system_setting_item` (`section`, `data`)
        SELECT 'mail_template', JSON_OBJECT(
            'email_verify_subject', `email_verify_subject`,
            'email_verify_is_html', `email_verify_is_html`,
            'email_verify_template', `email_verify_template`,
            'register_review_approve_subject', `register_review_approve_subject`,
            'register_review_approve_is_html', `register_review_approve_is_html`,
            'register_review_approve_template', `register_review_approve_template`,
            'register_review_reject_subject', `register_review_reject_subject`,
            'register_review_reject_is_html', `register_review_reject_is_html`,
            'register_review_reject_template', `register_review_reject_template`,
            'reset_password_subject', `reset_password_subject`,
            'reset_password_is_html', `reset_password_is_html`,
            'reset_password_template', `reset_password_template`,
            'admin_reset_password_subject', `admin_reset_password_subject`,
            'admin_reset_password_is_html', `admin_reset_password_is_html`,
            'admin_reset_password_template', `admin_reset_password_template`,
            'ticket_notify_subject', '工单状态提醒：{ticket_no}',
            'ticket_notify_is_html', 0,
            'ticket_notify_template', '您好，{name}：\n工单编号：{ticket_no}\n工单标题：{title}\n当前状态：{status}\n操作人：{operator}\n请及时登录系统处理。'
        )
        FROM `system_setting`
        ORDER BY `id` ASC
        LIMIT 1
        ON DUPLICATE KEY UPDATE `data` = VALUES(`data`);

        INSERT INTO `system_setting_item` (`section`, `data`)
        SELECT 'webdav', JSON_OBJECT(
            'webdav_enabled', `webdav_enabled`,
            'webdav_base_url', `webdav_base_url`,
            'webdav_username', `webdav_username`,
            'webdav_password', `webdav_password`,
            'webdav_share_default_expire_hours', `webdav_share_default_expire_hours`,
            'webdav_signature_secret', `webdav_signature_secret`
        )
        FROM `system_setting`
        ORDER BY `id` ASC
        LIMIT 1
        ON DUPLICATE KEY UPDATE `data` = VALUES(`data`);
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `system_setting_item`;
    """
