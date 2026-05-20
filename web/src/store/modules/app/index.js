import { defineStore } from 'pinia'
import { useDark } from '@vueuse/core'
import { lStorage } from '@/utils'
import i18n from '~/i18n'

const currentLocale = lStorage.get('locale')
const { locale } = i18n.global

const isDark = useDark()
export const useAppStore = defineStore('app', {
  state() {
    return {
      collapsed: false,
      fullScreen: true,
      /** keepAlive路由的key，重新赋值可重置keepAlive */
      aliveKeys: {},
      isDark,
      locale: currentLocale || 'en',
      siteTitle: import.meta.env.VITE_TITLE || '安得和众用户服务中心',
      siteLogo: '',
      allowPartnerRegister: true,
      allowChannelRegister: true,
      allowUserRegister: true,
      ticketAttachmentExtensions: ['zip', 'rar', 'png', 'jpg', 'gif'],
      ticketProjectPhases: ['售前', '实施', '售后'],
      ticketCategories: ['登录问题', '权限问题', '系统异常', '其他'],
      ticketDescriptionTemplates: ['问题现象：\n复现步骤：\n期望结果：\n实际结果：\n影响范围：'],
      loginSecurityEnabled: true,
      loginAccountIpFailLimit: 5,
      loginAccountIpLockMinutes: 60,
      loginIpFailLimit: 20,
      loginIpLockMinutes: 60,
      loginFailWindowMinutes: 60,
      loginGenericErrorEnabled: true,
      passwordMinLength: 8,
      passwordRequiredCategories: ['letter', 'digit'],
    }
  },
  actions: {
    async reloadPage() {
      document.documentElement.scrollTo({ left: 0, top: 0 })
    },
    switchCollapsed() {
      this.collapsed = !this.collapsed
    },
    setCollapsed(collapsed) {
      this.collapsed = collapsed
    },
    setFullScreen(fullScreen) {
      this.fullScreen = fullScreen
    },
    setAliveKeys(key, val) {
      this.aliveKeys[key] = val
    },
    /** 设置暗黑模式 */
    setDark(isDark) {
      this.isDark = isDark
    },
    /** 切换/关闭 暗黑模式 */
    toggleDark() {
      this.isDark = !this.isDark
    },
    setLocale(newLocale) {
      this.locale = newLocale
      locale.value = newLocale
      lStorage.set('locale', newLocale)
    },
    setSiteConfig(config = {}) {
      this.siteTitle = config.site_title || this.siteTitle
      this.siteLogo = config.site_logo || ''
      const legacyRegisterEnabled =
        typeof config.allow_partner_register === 'boolean' ? config.allow_partner_register : this.allowPartnerRegister
      this.allowChannelRegister =
        typeof config.allow_channel_register === 'boolean' ? config.allow_channel_register : legacyRegisterEnabled
      this.allowUserRegister =
        typeof config.allow_user_register === 'boolean' ? config.allow_user_register : legacyRegisterEnabled
      this.allowPartnerRegister = this.allowChannelRegister || this.allowUserRegister
      if (Array.isArray(config.ticket_attachment_extensions) && config.ticket_attachment_extensions.length > 0) {
        this.ticketAttachmentExtensions = config.ticket_attachment_extensions
      }
      if (Array.isArray(config.ticket_project_phases) && config.ticket_project_phases.length > 0) {
        this.ticketProjectPhases = config.ticket_project_phases
      }
      if (Array.isArray(config.ticket_categories) && config.ticket_categories.length > 0) {
        this.ticketCategories = config.ticket_categories
      }
      if (Array.isArray(config.ticket_description_templates) && config.ticket_description_templates.length > 0) {
        this.ticketDescriptionTemplates = config.ticket_description_templates
      }
      this.loginSecurityEnabled = typeof config.login_security_enabled === 'boolean' ? config.login_security_enabled : this.loginSecurityEnabled
      this.loginAccountIpFailLimit = config.login_account_ip_fail_limit || this.loginAccountIpFailLimit
      this.loginAccountIpLockMinutes = config.login_account_ip_lock_minutes || this.loginAccountIpLockMinutes
      this.loginIpFailLimit = config.login_ip_fail_limit || this.loginIpFailLimit
      this.loginIpLockMinutes = config.login_ip_lock_minutes || this.loginIpLockMinutes
      this.loginFailWindowMinutes = config.login_fail_window_minutes || this.loginFailWindowMinutes
      this.loginGenericErrorEnabled =
        typeof config.login_generic_error_enabled === 'boolean'
          ? config.login_generic_error_enabled
          : this.loginGenericErrorEnabled
      this.passwordMinLength = config.password_min_length || this.passwordMinLength
      if (Array.isArray(config.password_required_categories) && config.password_required_categories.length > 0) {
        this.passwordRequiredCategories = config.password_required_categories
      }
    },
  },
})
