<script setup>
import { onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NDivider,
  NDynamicTags,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSpace,
  NSwitch,
  NTabPane,
  NTabs,
  NUpload,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'
import { useAppStore } from '@/store'
import { sanitizeHtml } from '@/utils'

defineOptions({ name: '系统设置' })

const formRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const webdavTesting = ref(false)
const timeSyncChecking = ref(false)
const timeSyncSyncing = ref(false)
const timeSyncStatus = ref(null)
const logoUploading = ref(false)
const previewVisible = ref(false)
const appStore = useAppStore()
const form = ref({
  site_title: '安得和众用户服务中心',
  site_logo: '',
  allow_partner_register: true,
  allow_channel_register: true,
  allow_user_register: true,
  customer_service_auto_approve_register: false,
  ticket_attachment_extensions: ['zip', 'rar', 'png', 'jpg', 'gif'],
  ticket_project_phases: ['售前', '实施', '售后'],
  ticket_categories: ['登录问题', '权限问题', '系统异常', '其他'],
  customer_service_auto_approve_ticket: false,
  ticket_root_causes: ['代码缺陷', '配置错误', '环境异常', '数据问题', '操作不当', '第三方依赖'],
  ticket_description_templates: ['问题现象：\n复现步骤：\n期望结果：\n实际结果：\n影响范围：'],
  login_security_enabled: true,
  login_account_ip_fail_limit: 5,
  login_account_ip_lock_minutes: 60,
  login_ip_fail_limit: 20,
  login_ip_lock_minutes: 60,
  login_fail_window_minutes: 60,
  login_generic_error_enabled: true,
  user_token_expire_minutes: 60,
  inactive_user_auto_disable_enabled: true,
  inactive_user_auto_disable_days: 30,
  password_min_length: 8,
  password_required_categories: ['letter', 'digit'],
  time_sync_enabled: true,
  time_sync_server: 'ntp.aliyun.com',
  time_sync_interval_minutes: 60,
  time_sync_max_offset_seconds: 5,
  time_sync_timezone: 'Asia/Shanghai',
  ticket_notify_by_role: {
    用户: ['cs_rejected', 'tech_rejected', 'done'],
    代理商: ['cs_rejected', 'tech_rejected', 'done'],
    客服: ['pending_review'],
    技术: ['tech_processing'],
  },
  smtp_host: '',
  smtp_port: 465,
  smtp_username: '',
  smtp_password: '',
  smtp_sender: '',
  smtp_sender_name: '系统通知',
  smtp_use_tls: false,
  smtp_use_ssl: true,
  email_verify_subject: '代理商注册验证码',
  email_verify_is_html: true,
  email_verify_template: '您好，您的验证码是：{code}，{minutes}分钟内有效。',
  register_review_approve_subject: '注册审核结果通知',
  register_review_approve_is_html: true,
  register_review_approve_template:
    '您好，{contact_name}，您的{register_type}注册申请已审核通过，现可使用邮箱登录系统。',
  register_review_reject_subject: '注册审核结果通知',
  register_review_reject_is_html: true,
  register_review_reject_template:
    '您好，{contact_name}，您的{register_type}注册申请已驳回。驳回理由：{reason}',
  reset_password_subject: '密码重置验证码',
  reset_password_is_html: true,
  reset_password_template:
    '<div style="font-family:Arial,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;color:#1f2937;line-height:1.7;background:#f8fbff;border:1px solid #dbeafe;border-radius:12px;padding:16px 18px;"><h2 style="margin:0 0 12px;font-size:18px;color:#1d4ed8;">找回密码验证码</h2><p style="margin:0 0 10px;">您好，您正在进行密码重置操作，请使用以下验证码：</p><div style="display:inline-block;padding:10px 18px;border-radius:8px;background:#eff6ff;border:1px solid #bfdbfe;font-size:24px;font-weight:700;letter-spacing:4px;color:#1d4ed8;">{code}</div><p style="margin:12px 0 0;color:#6b7280;">验证码 {minutes} 分钟内有效，请勿泄露给他人。</p></div>',
  admin_reset_password_subject: '账号密码已重置',
  admin_reset_password_is_html: true,
  admin_reset_password_template:
    '<div style="font-family:Arial,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;color:#1f2937;line-height:1.7;background:#fffaf0;border:1px solid #fde68a;border-radius:12px;padding:16px 18px;"><h2 style="margin:0 0 12px;font-size:18px;color:#b45309;">账号密码已重置</h2><p style="margin:0 0 8px;">您好，<b>{username}</b>：</p><p style="margin:0 0 8px;">管理员已重置您的账号密码，请使用以下临时密码登录：</p><div style="display:inline-block;padding:10px 14px;border-radius:8px;background:#fff7ed;border:1px solid #fed7aa;font-size:20px;font-weight:700;color:#c2410c;">{password}</div><p style="margin:12px 0 0;color:#6b7280;">登录后请尽快在个人中心修改密码。</p></div>',
  ticket_notify_subject: '工单状态提醒：{ticket_no}',
  ticket_notify_is_html: true,
  ticket_notify_template:
    '<div style="font-family:Arial,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;color:#1f2937;line-height:1.7;background:#f8fbff;border:1px solid #dbeafe;border-radius:12px;padding:16px 18px;"><h2 style="margin:0 0 12px;font-size:18px;color:#1d4ed8;">工单状态提醒</h2><p style="margin:0 0 8px;">您好，<b>{name}</b>：</p><p style="margin:0 0 6px;">工单编号：<b>{ticket_no}</b></p><p style="margin:0 0 6px;">工单标题：{title}</p><p style="margin:0 0 6px;">当前状态：<b style="color:#1d4ed8;">{status}</b></p><p style="margin:0 0 6px;">操作人：{operator}</p><p style="margin:8px 0 0;color:#6b7280;">请及时登录系统处理。</p></div>',
  webdav_enabled: false,
  webdav_base_url: '',
  webdav_username: '',
  webdav_password: '',
  webdav_share_default_expire_hours: 168,
  webdav_signature_ttl: 600,
  webdav_max_upload_size: 50 * 1024 * 1024,
  webdav_signature_secret: '',
})

const previewParams = ref({
  contact_name: '张三',
  register_type: '用户',
  reason: '资料不完整，请补充设备机器码',
  code: '123456',
  minutes: 10,
  username: 'zhangsan',
  password: 'Tmp#8291',
})

const presetTemplates = {
  verifySubject: '【系统通知】邮箱验证码',
  verifyHtml: `
<div style="font-family:Arial,'PingFang SC','Microsoft YaHei',sans-serif;color:#1f2937;line-height:1.7;">
  <h2 style="margin:0 0 12px;font-size:18px;color:#0f4c81;">邮箱验证码</h2>
  <p style="margin:0 0 10px;">您好，验证码用于本次注册校验：</p>
  <div style="display:inline-block;padding:10px 18px;border-radius:8px;background:#eff6ff;border:1px solid #bfdbfe;font-size:24px;font-weight:700;letter-spacing:4px;color:#1d4ed8;">{code}</div>
  <p style="margin:12px 0 0;color:#6b7280;">验证码 {minutes} 分钟内有效，请勿泄露给他人。</p>
</div>
`.trim(),
  approveSubject: '【系统通知】注册审核通过',
  approveHtml: `
<div style="font-family:Arial,'PingFang SC','Microsoft YaHei',sans-serif;color:#1f2937;line-height:1.7;">
  <h2 style="margin:0 0 12px;font-size:18px;color:#15803d;">注册审核通过</h2>
  <p style="margin:0 0 8px;">您好，<b>{contact_name}</b>：</p>
  <p style="margin:0 0 8px;">您提交的 <b>{register_type}</b> 注册申请已审核通过。</p>
  <p style="margin:0;color:#374151;">现在可使用注册邮箱登录系统并提交工单。</p>
</div>
`.trim(),
  rejectSubject: '【系统通知】注册审核驳回',
  rejectHtml: `
<div style="font-family:Arial,'PingFang SC','Microsoft YaHei',sans-serif;color:#1f2937;line-height:1.7;">
  <h2 style="margin:0 0 12px;font-size:18px;color:#b91c1c;">注册审核驳回</h2>
  <p style="margin:0 0 8px;">您好，<b>{contact_name}</b>：</p>
  <p style="margin:0 0 8px;">您提交的 <b>{register_type}</b> 注册申请未通过审核。</p>
  <p style="margin:0 0 8px;">驳回理由：<span style="color:#b91c1c;font-weight:600;">{reason}</span></p>
  <p style="margin:0;color:#6b7280;">请根据提示完善信息后重新提交。</p>
</div>
`.trim(),
  resetPwdSubject: '【系统通知】找回密码验证码',
  resetPwdHtml:
    '<div style="font-family:Arial,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;color:#1f2937;line-height:1.7;background:#f8fbff;border:1px solid #dbeafe;border-radius:12px;padding:16px 18px;"><h2 style="margin:0 0 12px;font-size:18px;color:#1d4ed8;">找回密码验证码</h2><p style="margin:0 0 10px;">您好，您正在进行密码重置操作，请使用以下验证码：</p><div style="display:inline-block;padding:10px 18px;border-radius:8px;background:#eff6ff;border:1px solid #bfdbfe;font-size:24px;font-weight:700;letter-spacing:4px;color:#1d4ed8;">{code}</div><p style="margin:12px 0 0;color:#6b7280;">验证码 {minutes} 分钟内有效，请勿泄露给他人。</p></div>',
  adminResetSubject: '【系统通知】账号密码已重置',
  adminResetHtml:
    '<div style="font-family:Arial,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;color:#1f2937;line-height:1.7;background:#fffaf0;border:1px solid #fde68a;border-radius:12px;padding:16px 18px;"><h2 style="margin:0 0 12px;font-size:18px;color:#b45309;">账号密码已重置</h2><p style="margin:0 0 8px;">您好，<b>{username}</b>：</p><p style="margin:0 0 8px;">管理员已重置您的账号密码，请使用以下临时密码登录：</p><div style="display:inline-block;padding:10px 14px;border-radius:8px;background:#fff7ed;border:1px solid #fed7aa;font-size:20px;font-weight:700;color:#c2410c;">{password}</div><p style="margin:12px 0 0;color:#6b7280;">登录后请尽快在个人中心修改密码。</p></div>',
  ticketNotifySubject: '【系统通知】工单状态提醒',
  ticketNotifyHtml:
    '<div style="font-family:Arial,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;color:#1f2937;line-height:1.7;background:#f8fbff;border:1px solid #dbeafe;border-radius:12px;padding:16px 18px;"><h2 style="margin:0 0 12px;font-size:18px;color:#1d4ed8;">工单状态提醒</h2><p style="margin:0 0 8px;">您好，<b>{name}</b>：</p><p style="margin:0 0 6px;">工单编号：<b>{ticket_no}</b></p><p style="margin:0 0 6px;">工单标题：{title}</p><p style="margin:0 0 6px;">当前状态：<b style="color:#1d4ed8;">{status}</b></p><p style="margin:0 0 6px;">操作人：{operator}</p><p style="margin:8px 0 0;color:#6b7280;">请及时登录系统处理。</p></div>',
}

const ticketNotifyRoleOptions = {
  用户: [
    { label: '客服驳回', value: 'cs_rejected' },
    { label: '技术驳回', value: 'tech_rejected' },
    { label: '处理完成', value: 'done' },
  ],
  代理商: [
    { label: '客服驳回', value: 'cs_rejected' },
    { label: '技术驳回', value: 'tech_rejected' },
    { label: '处理完成', value: 'done' },
  ],
  客服: [{ label: '提交后待客服审核', value: 'pending_review' }],
  技术: [{ label: '通过后待技术处理', value: 'tech_processing' }],
}

const passwordCategoryOptions = [
  { label: '字母', value: 'letter' },
  { label: '数字', value: 'digit' },
  { label: '特殊字符', value: 'special' },
]

const ticketNotifyRoles = ['用户', '代理商', '客服', '技术']

function normalizeTicketNotifyByRole(raw = {}) {
  const normalized = {}
  ticketNotifyRoles.forEach((roleName) => {
    const allowed = new Set((ticketNotifyRoleOptions[roleName] || []).map((item) => item.value))
    const selected = Array.isArray(raw[roleName]) ? raw[roleName] : []
    normalized[roleName] = selected.filter((item) => allowed.has(item))
  })
  return normalized
}

const rules = {
  site_title: { required: true, message: '请输入网站标题', trigger: ['input', 'blur'] },
  ticket_categories: {
    required: true,
    validator: () => {
      if (!form.value.ticket_categories || form.value.ticket_categories.length === 0) {
        return new Error('请至少配置一个工单分类')
      }
      return true
    },
    trigger: ['change', 'blur'],
  },
  ticket_project_phases: {
    required: true,
    validator: () => {
      if (!form.value.ticket_project_phases || form.value.ticket_project_phases.length === 0) {
        return new Error('请至少配置一个项目阶段')
      }
      return true
    },
    trigger: ['change', 'blur'],
  },
  ticket_attachment_extensions: {
    required: true,
    validator: () => {
      const items = (form.value.ticket_attachment_extensions || []).filter((item) =>
        String(item || '').trim(),
      )
      if (items.length === 0) {
        return new Error('请至少配置一个允许上传类型')
      }
      return true
    },
    trigger: ['change', 'blur'],
  },
  ticket_root_causes: {
    required: true,
    validator: () => {
      const items = (form.value.ticket_root_causes || []).filter((item) =>
        String(item || '').trim(),
      )
      if (items.length === 0) {
        return new Error('请至少配置一个问题根因')
      }
      return true
    },
    trigger: ['change', 'blur'],
  },
  ticket_description_templates: {
    required: true,
    validator: () => {
      const items = (form.value.ticket_description_templates || []).filter((item) =>
        String(item || '').trim(),
      )
      if (items.length === 0) {
        return new Error('请至少配置一个问题描述模板')
      }
      return true
    },
    trigger: ['change', 'blur'],
  },
  login_account_ip_fail_limit: {
    required: true,
    type: 'number',
    min: 1,
    message: '请输入正确的账号+IP失败阈值',
    trigger: ['blur', 'change'],
  },
  login_account_ip_lock_minutes: {
    required: true,
    type: 'number',
    min: 1,
    message: '请输入正确的账号+IP锁定时长',
    trigger: ['blur', 'change'],
  },
  login_ip_fail_limit: {
    required: true,
    type: 'number',
    min: 1,
    message: '请输入正确的IP失败阈值',
    trigger: ['blur', 'change'],
  },
  login_ip_lock_minutes: {
    required: true,
    type: 'number',
    min: 1,
    message: '请输入正确的IP锁定时长',
    trigger: ['blur', 'change'],
  },
  login_fail_window_minutes: {
    required: true,
    type: 'number',
    min: 1,
    message: '请输入正确的失败统计窗口',
    trigger: ['blur', 'change'],
  },
  user_token_expire_minutes: {
    required: true,
    type: 'number',
    min: 1,
    message: '请输入正确的Token失效时间',
    trigger: ['blur', 'change'],
  },
  inactive_user_auto_disable_days: {
    required: true,
    type: 'number',
    min: 1,
    max: 3650,
    message: '请输入正确的未登录禁用天数',
    trigger: ['blur', 'change'],
  },
  password_min_length: {
    required: true,
    type: 'number',
    min: 8,
    message: '密码最小长度不能小于8',
    trigger: ['blur', 'change'],
  },
  password_required_categories: {
    required: true,
    validator: () => {
      const items = form.value.password_required_categories || []
      if (!items.length) return new Error('请至少选择一种密码类别')
      return true
    },
    trigger: ['change', 'blur'],
  },
  time_sync_server: {
    required: true,
    message: '请输入时间服务器地址',
    trigger: ['input', 'blur'],
  },
  time_sync_interval_minutes: {
    required: true,
    type: 'number',
    min: 1,
    message: '请输入正确的同步间隔',
    trigger: ['blur', 'change'],
  },
  time_sync_max_offset_seconds: {
    required: true,
    type: 'number',
    min: 1,
    message: '请输入正确的最大允许偏差',
    trigger: ['blur', 'change'],
  },
  time_sync_timezone: {
    required: true,
    message: '请输入系统时区',
    trigger: ['input', 'blur'],
  },
}

onMounted(() => {
  loadData()
})

async function loadData() {
  try {
    loading.value = true
    const res = await api.getSystemSettings()
    const legacyRegisterEnabled =
      typeof res.data?.allow_partner_register === 'boolean' ? res.data.allow_partner_register : true
    form.value = {
      ...form.value,
      ...res.data,
      allow_channel_register:
        typeof res.data?.allow_channel_register === 'boolean'
          ? res.data.allow_channel_register
          : legacyRegisterEnabled,
      allow_user_register:
        typeof res.data?.allow_user_register === 'boolean' ? res.data.allow_user_register : legacyRegisterEnabled,
      ticket_attachment_extensions: res.data?.ticket_attachment_extensions?.length
        ? res.data.ticket_attachment_extensions
        : form.value.ticket_attachment_extensions,
      ticket_project_phases: res.data?.ticket_project_phases?.length
        ? res.data.ticket_project_phases
        : form.value.ticket_project_phases,
      ticket_categories: res.data?.ticket_categories?.length
        ? res.data.ticket_categories
        : form.value.ticket_categories,
      ticket_description_templates: Array.isArray(res.data?.ticket_description_templates)
        ? res.data.ticket_description_templates
        : form.value.ticket_description_templates,
      ticket_notify_by_role: normalizeTicketNotifyByRole(
        res.data?.ticket_notify_by_role || form.value.ticket_notify_by_role,
      ),
    }
    const publicRes = await api.getPublicConfig()
    appStore.setSiteConfig(publicRes.data || {})
  } finally {
    loading.value = false
  }
}

function save() {
  formRef.value?.validate(async (err) => {
    if (err) return
    try {
      saving.value = true
      const payload = {
        ...form.value,
        allow_partner_register: form.value.allow_channel_register || form.value.allow_user_register,
        ticket_notify_by_role: normalizeTicketNotifyByRole(form.value.ticket_notify_by_role),
      }
      await api.updateSystemSettings(payload)
      $message.success('设置已保存并生效')
      const publicRes = await api.getPublicConfig()
      appStore.setSiteConfig(publicRes.data || {})
      await loadData()
    } finally {
      saving.value = false
    }
  })
}

async function testWebdavConnection() {
  try {
    webdavTesting.value = true
    const res = await api.testWebdavConnection({
      webdav_enabled: form.value.webdav_enabled,
      webdav_base_url: form.value.webdav_base_url,
      webdav_username: form.value.webdav_username,
      webdav_password: form.value.webdav_password,
    })
    $message.success(res?.msg || 'WebDAV连接成功')
  } finally {
    webdavTesting.value = false
  }
}

async function checkTimeSyncStatus() {
  try {
    timeSyncChecking.value = true
    const res = await api.getTimeSyncStatus()
    timeSyncStatus.value = res?.data || null
    if (timeSyncStatus.value?.within_tolerance) {
      $message.success('时间偏差在允许范围内')
    } else {
      $message.warning('时间偏差超过允许范围')
    }
  } finally {
    timeSyncChecking.value = false
  }
}

async function syncSystemTime() {
  try {
    timeSyncSyncing.value = true
    const res = await api.syncSystemTime()
    timeSyncStatus.value = res?.data || null
    $message.success(res?.msg || '时间同步完成')
  } finally {
    timeSyncSyncing.value = false
  }
}

async function uploadLogo({ file, onFinish, onError }) {
  try {
    logoUploading.value = true
    await api.uploadSiteLogo(file.file)
    const publicRes = await api.getPublicConfig()
    appStore.setSiteConfig(publicRes.data || {})
    const res = await api.getSystemSettings()
    form.value.site_logo = res.data?.site_logo || ''
    $message.success('Logo已上传并更新')
    onFinish()
  } catch (error) {
    onError()
  } finally {
    logoUploading.value = false
  }
}

function renderTemplate(template, params) {
  let content = template || ''
  Object.keys(params).forEach((key) => {
    content = content.replaceAll(`{${key}}`, params[key])
  })
  return content
}

function renderSafeTemplate(template, params) {
  return sanitizeHtml(renderTemplate(template, params))
}

function openPreview() {
  previewVisible.value = true
}

function addDescriptionTemplate() {
  form.value.ticket_description_templates.push('')
}

function removeDescriptionTemplate(index) {
  if ((form.value.ticket_description_templates || []).length <= 1) {
    $message.warning('至少保留一个问题描述模板')
    return
  }
  form.value.ticket_description_templates.splice(index, 1)
}

function applyPresetHtmlTemplates() {
  form.value.email_verify_subject = presetTemplates.verifySubject
  form.value.email_verify_template = presetTemplates.verifyHtml
  form.value.email_verify_is_html = true

  form.value.register_review_approve_subject = presetTemplates.approveSubject
  form.value.register_review_approve_template = presetTemplates.approveHtml
  form.value.register_review_approve_is_html = true

  form.value.register_review_reject_subject = presetTemplates.rejectSubject
  form.value.register_review_reject_template = presetTemplates.rejectHtml
  form.value.register_review_reject_is_html = true

  form.value.reset_password_subject = presetTemplates.resetPwdSubject
  form.value.reset_password_template = presetTemplates.resetPwdHtml
  form.value.reset_password_is_html = true

  form.value.admin_reset_password_subject = presetTemplates.adminResetSubject
  form.value.admin_reset_password_template = presetTemplates.adminResetHtml
  form.value.admin_reset_password_is_html = true

  form.value.ticket_notify_subject = presetTemplates.ticketNotifySubject
  form.value.ticket_notify_template = presetTemplates.ticketNotifyHtml
  form.value.ticket_notify_is_html = true

  $message.success('推荐模板已应用，请保存后生效')
}
</script>

<template>
  <CommonPage title="系统设置" show-footer>
    <n-spin :show="loading">
      <NForm ref="formRef" :model="form" :rules="rules" :label-width="120" label-placement="left">
        <NTabs type="line" animated>
          <NTabPane name="site" tab="站点配置">
            <NCard size="small" title="基础信息">
              <NFormItem label="网站标题" path="site_title">
                <NInput v-model:value="form.site_title" placeholder="请输入网站标题" />
              </NFormItem>
              <NFormItem label="网站Logo" path="site_logo">
                <div flex items-center gap-12>
                  <NUpload
                    :default-upload="false"
                    :custom-request="uploadLogo"
                    :max="1"
                    accept=".jpg,.jpeg,.png,.webp"
                  >
                    <NButton :loading="logoUploading">上传本地Logo</NButton>
                  </NUpload>
                  <img
                    v-if="appStore.siteLogo"
                    :src="appStore.siteLogo"
                    alt="logo"
                    style="height: 36px; width: 36px"
                  />
                </div>
              </NFormItem>
              <NFormItem label="开放渠道商注册">
                <NSwitch v-model:value="form.allow_channel_register" />
              </NFormItem>
              <NFormItem label="开放用户注册">
                <NSwitch v-model:value="form.allow_user_register" />
              </NFormItem>
              <NFormItem label="客服自动审批注册">
                <NSwitch v-model:value="form.customer_service_auto_approve_register" />
              </NFormItem>
            </NCard>
          </NTabPane>

          <NTabPane name="ticket" tab="工单配置">
            <NCard size="small" title="工单分类">
              <NFormItem label="附件类型" path="ticket_attachment_extensions">
                <NDynamicTags v-model:value="form.ticket_attachment_extensions" />
              </NFormItem>
              <NFormItem label="项目阶段" path="ticket_project_phases">
                <NDynamicTags v-model:value="form.ticket_project_phases" />
              </NFormItem>
              <NFormItem label="问题分类" path="ticket_categories">
                <NDynamicTags v-model:value="form.ticket_categories" />
              </NFormItem>
              <NFormItem label="客服自动审批工单">
                <NSwitch v-model:value="form.customer_service_auto_approve_ticket" />
              </NFormItem>
              <NFormItem label="问题根因" path="ticket_root_causes">
                <NDynamicTags v-model:value="form.ticket_root_causes" />
              </NFormItem>
              <NFormItem label="问题描述模板" path="ticket_description_templates">
                <div class="template-editor">
                  <div
                    v-for="(item, index) in form.ticket_description_templates"
                    :key="index"
                    class="template-item"
                  >
                    <NInput
                      v-model:value="form.ticket_description_templates[index]"
                      type="textarea"
                      :autosize="{ minRows: 3, maxRows: 6 }"
                      :placeholder="`模板 ${index + 1}`"
                    />
                    <NButton quaternary type="error" @click="removeDescriptionTemplate(index)"
                      >删除</NButton
                    >
                  </div>
                  <NButton dashed @click="addDescriptionTemplate">新增模板</NButton>
                </div>
              </NFormItem>
              <NDivider title-placement="left">工单提醒</NDivider>
              <NAlert type="info" class="mb-12">
                按角色配置提醒节点：用户/代理商（客服驳回、技术驳回、处理完成），客服（提交后待客服审核），技术（通过后待技术处理）。
              </NAlert>
              <NFormItem
                v-for="roleName in ticketNotifyRoles"
                :key="roleName"
                :label="`${roleName}提醒节点`"
              >
                <NCheckboxGroup v-model:value="form.ticket_notify_by_role[roleName]">
                  <div
                    style="
                      display: grid;
                      grid-template-columns: repeat(2, minmax(220px, 1fr));
                      gap: 8px 12px;
                    "
                  >
                    <NCheckbox
                      v-for="item in ticketNotifyRoleOptions[roleName]"
                      :key="item.value"
                      :value="item.value"
                    >
                      {{ item.label }}
                    </NCheckbox>
                  </div>
                </NCheckboxGroup>
              </NFormItem>
            </NCard>
          </NTabPane>

          <NTabPane name="login-security" tab="登录安全">
            <NCard size="small" title="登录失败锁定策略">
              <NAlert type="info" class="mb-12">
                推荐开启双层锁定：账号+IP 连续失败达到阈值后锁定，同时对异常来源 IP 做更高阈值拦截；普通用户超过配置天数未登录会自动禁用。
              </NAlert>
              <NFormItem label="启用登录安全">
                <NSwitch v-model:value="form.login_security_enabled" />
              </NFormItem>
              <NFormItem label="账号+IP失败阈值" path="login_account_ip_fail_limit">
                <NInputNumber v-model:value="form.login_account_ip_fail_limit" :min="1" :max="20" />
              </NFormItem>
              <NFormItem label="账号+IP锁定(分钟)" path="login_account_ip_lock_minutes">
                <NInputNumber
                  v-model:value="form.login_account_ip_lock_minutes"
                  :min="1"
                  :max="1440"
                />
              </NFormItem>
              <NFormItem label="IP失败阈值" path="login_ip_fail_limit">
                <NInputNumber v-model:value="form.login_ip_fail_limit" :min="1" :max="200" />
              </NFormItem>
              <NFormItem label="IP锁定(分钟)" path="login_ip_lock_minutes">
                <NInputNumber v-model:value="form.login_ip_lock_minutes" :min="1" :max="1440" />
              </NFormItem>
              <NFormItem label="统计窗口(分钟)" path="login_fail_window_minutes">
                <NInputNumber v-model:value="form.login_fail_window_minutes" :min="1" :max="1440" />
              </NFormItem>
              <NFormItem label="统一错误提示">
                <NSwitch v-model:value="form.login_generic_error_enabled" />
              </NFormItem>
              <NFormItem label="Token失效(分钟)" path="user_token_expire_minutes">
                <NInputNumber v-model:value="form.user_token_expire_minutes" :min="1" :max="43200" />
              </NFormItem>
              <NFormItem label="未登录自动禁用">
                <NSwitch v-model:value="form.inactive_user_auto_disable_enabled" />
              </NFormItem>
              <NFormItem label="未登录禁用天数" path="inactive_user_auto_disable_days">
                <NInputNumber
                  v-model:value="form.inactive_user_auto_disable_days"
                  :min="1"
                  :max="3650"
                  :disabled="!form.inactive_user_auto_disable_enabled"
                />
              </NFormItem>
              <NFormItem label="密码最小长度" path="password_min_length">
                <NInputNumber v-model:value="form.password_min_length" :min="8" :max="64" />
              </NFormItem>
              <NFormItem label="密码类别" path="password_required_categories">
                <NCheckboxGroup v-model:value="form.password_required_categories">
                  <NSpace>
                    <NCheckbox
                      v-for="item in passwordCategoryOptions"
                      :key="item.value"
                      :value="item.value"
                      >{{ item.label }}</NCheckbox
                    >
                  </NSpace>
                </NCheckboxGroup>
              </NFormItem>
            </NCard>
          </NTabPane>

          <NTabPane name="time-sync" tab="时间同步">
            <NCard size="small" title="时间服务器同步配置">
              <NAlert type="info" class="mb-12">
                容器默认共享宿主机系统时钟；这里用于统一配置时间服务器、同步间隔和时区，部署脚本或具备权限的同步服务可读取该配置执行校时。
              </NAlert>
              <NFormItem label="启用时间同步">
                <NSwitch v-model:value="form.time_sync_enabled" />
              </NFormItem>
              <NFormItem label="时间服务器" path="time_sync_server">
                <NInput v-model:value="form.time_sync_server" placeholder="例如 ntp.aliyun.com" />
              </NFormItem>
              <NFormItem label="同步间隔(分钟)" path="time_sync_interval_minutes">
                <NInputNumber
                  v-model:value="form.time_sync_interval_minutes"
                  :min="1"
                  :max="1440"
                />
              </NFormItem>
              <NFormItem label="允许偏差(秒)" path="time_sync_max_offset_seconds">
                <NInputNumber
                  v-model:value="form.time_sync_max_offset_seconds"
                  :min="1"
                  :max="3600"
                />
              </NFormItem>
              <NFormItem label="系统时区" path="time_sync_timezone">
                <NInput v-model:value="form.time_sync_timezone" placeholder="例如 Asia/Shanghai" />
              </NFormItem>
            </NCard>
          </NTabPane>

          <NTabPane name="mail" tab="发件配置">
            <NCard size="small" title="SMTP设置">
              <NFormItem label="SMTP主机">
                <NInput v-model:value="form.smtp_host" placeholder="例如 smtp.qq.com" />
              </NFormItem>
              <NFormItem label="SMTP端口">
                <NInputNumber v-model:value="form.smtp_port" :min="1" :max="65535" />
              </NFormItem>
              <NFormItem label="SMTP用户名">
                <NInput v-model:value="form.smtp_username" placeholder="可选，默认使用发件邮箱" />
              </NFormItem>
              <NFormItem label="SMTP密码">
                <NInput
                  v-model:value="form.smtp_password"
                  type="password"
                  show-password-on="mousedown"
                />
              </NFormItem>
              <NFormItem label="发件邮箱">
                <NInput v-model:value="form.smtp_sender" placeholder="例如 xxx@qq.com" />
              </NFormItem>
              <NFormItem label="发件人名称">
                <NInput v-model:value="form.smtp_sender_name" placeholder="系统通知" />
              </NFormItem>
              <NFormItem label="启用TLS">
                <NSwitch v-model:value="form.smtp_use_tls" />
              </NFormItem>
              <NFormItem label="启用SSL">
                <NSwitch v-model:value="form.smtp_use_ssl" />
              </NFormItem>
            </NCard>
          </NTabPane>

          <NTabPane name="webdav" tab="WebDAV管理">
            <NCard size="small" title="WebDAV统一配置">
              <NAlert type="info" class="mb-12">
                这里统一维护外发网盘 WebDAV 配置；密码显示为掩码，保持不变可直接保存。
              </NAlert>
              <NFormItem label="启用WebDAV">
                <NSwitch v-model:value="form.webdav_enabled" />
              </NFormItem>
              <NFormItem label="Base URL">
                <NInput
                  v-model:value="form.webdav_base_url"
                  placeholder="例如 https://webdav.example.com/webdav"
                />
              </NFormItem>
              <NFormItem label="用户名">
                <NInput v-model:value="form.webdav_username" placeholder="请输入WebDAV用户名" />
              </NFormItem>
              <NFormItem label="密码">
                <NInput
                  v-model:value="form.webdav_password"
                  type="password"
                  show-password-on="mousedown"
                  placeholder="保持不变可留******"
                />
              </NFormItem>
              <NFormItem label="默认分享时长(小时)">
                <NInputNumber
                  v-model:value="form.webdav_share_default_expire_hours"
                  :min="1"
                  :max="8760"
                />
              </NFormItem>
              <NFormItem label="签名有效期(秒)">
                <NInputNumber v-model:value="form.webdav_signature_ttl" :min="1" :max="86400" />
              </NFormItem>
              <NFormItem label="最大上传大小(Byte)">
                <NInputNumber
                  v-model:value="form.webdav_max_upload_size"
                  :min="1"
                  :max="1073741824"
                />
              </NFormItem>
              <NFormItem label="签名密钥">
                <NInput
                  v-model:value="form.webdav_signature_secret"
                  placeholder="用于外链签名校验（可选）"
                />
              </NFormItem>
              <NFormItem>
                <NButton type="primary" ghost :loading="webdavTesting" @click="testWebdavConnection"
                  >测试连接</NButton
                >
              </NFormItem>
            </NCard>
          </NTabPane>

          <NTabPane name="template" tab="邮件模板">
            <NAlert type="info" class="mb-12">
              验证码模板支持变量：{code}、{minutes}；审核模板支持变量：{contact_name}、{register_type}、{reason}；管理员重置通知支持变量：{username}、{password}、{email}；工单提醒支持变量：{name}、{ticket_no}、{title}、{status}、{operator}
            </NAlert>
            <div class="mb-12" flex items-center gap-12>
              <NButton type="primary" ghost @click="applyPresetHtmlTemplates"
                >一键应用推荐HTML模板</NButton
              >
              <NButton type="default" @click="openPreview">预览模板效果</NButton>
            </div>

            <NCard size="small" title="验证码邮件模板" class="mb-12">
              <NFormItem label="邮件标题">
                <NInput v-model:value="form.email_verify_subject" />
              </NFormItem>
              <NFormItem label="HTML格式">
                <NSwitch v-model:value="form.email_verify_is_html" />
              </NFormItem>
              <NFormItem label="邮件模板">
                <NInput
                  v-model:value="form.email_verify_template"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 8 }"
                  placeholder="支持变量 {code}、{minutes}"
                />
              </NFormItem>
            </NCard>

            <NCard size="small" title="找回密码验证码模板" class="mb-12">
              <NFormItem label="邮件标题">
                <NInput v-model:value="form.reset_password_subject" />
              </NFormItem>
              <NFormItem label="HTML格式">
                <NSwitch v-model:value="form.reset_password_is_html" />
              </NFormItem>
              <NFormItem label="邮件模板">
                <NInput
                  v-model:value="form.reset_password_template"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 8 }"
                  placeholder="支持变量 {code}、{minutes}"
                />
              </NFormItem>
            </NCard>

            <NCard size="small" title="注册审核通知模板">
              <NFormItem label="通过标题">
                <NInput v-model:value="form.register_review_approve_subject" />
              </NFormItem>
              <NFormItem label="通过HTML格式">
                <NSwitch v-model:value="form.register_review_approve_is_html" />
              </NFormItem>
              <NFormItem label="通过模板">
                <NInput
                  v-model:value="form.register_review_approve_template"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 8 }"
                />
              </NFormItem>
              <NFormItem label="驳回标题">
                <NInput v-model:value="form.register_review_reject_subject" />
              </NFormItem>
              <NFormItem label="驳回HTML格式">
                <NSwitch v-model:value="form.register_review_reject_is_html" />
              </NFormItem>
              <NFormItem label="驳回模板">
                <NInput
                  v-model:value="form.register_review_reject_template"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 8 }"
                />
              </NFormItem>
            </NCard>

            <NCard size="small" title="管理员重置密码通知模板">
              <NFormItem label="邮件标题">
                <NInput v-model:value="form.admin_reset_password_subject" />
              </NFormItem>
              <NFormItem label="HTML格式">
                <NSwitch v-model:value="form.admin_reset_password_is_html" />
              </NFormItem>
              <NFormItem label="邮件模板">
                <NInput
                  v-model:value="form.admin_reset_password_template"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 8 }"
                  placeholder="支持变量 {username}、{password}、{email}"
                />
              </NFormItem>
            </NCard>

            <NCard size="small" title="工单提醒模板">
              <NFormItem label="邮件标题">
                <NInput v-model:value="form.ticket_notify_subject" />
              </NFormItem>
              <NFormItem label="HTML格式">
                <NSwitch v-model:value="form.ticket_notify_is_html" />
              </NFormItem>
              <NFormItem label="邮件模板">
                <NInput
                  v-model:value="form.ticket_notify_template"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 8 }"
                  placeholder="支持变量 {name}、{ticket_no}、{title}、{status}、{operator}"
                />
              </NFormItem>
            </NCard>
          </NTabPane>
        </NTabs>

        <NFormItem class="mt-16">
          <NButton type="primary" :loading="saving" @click="save">保存设置</NButton>
        </NFormItem>
      </NForm>

      <NModal v-model:show="previewVisible" preset="card" title="模板预览" style="width: 760px">
        <NAlert type="info" class="mb-12">
          预览使用示例变量：姓名=张三、注册类型=用户、驳回理由=资料不完整、验证码=123456、分钟=10。
        </NAlert>

        <NDivider title-placement="left">验证码邮件</NDivider>
        <NFormItem label="标题">
          <NInput :value="form.email_verify_subject" readonly />
        </NFormItem>
        <NFormItem label="HTML格式">
          <NSwitch :value="form.email_verify_is_html" disabled />
        </NFormItem>
        <NFormItem label="内容">
          <NInput
            v-if="!form.email_verify_is_html"
            type="textarea"
            :value="renderTemplate(form.email_verify_template, previewParams)"
            :autosize="{ minRows: 3, maxRows: 6 }"
            readonly
          />
          <div
            v-else
            class="preview-html"
            v-html="renderSafeTemplate(form.email_verify_template, previewParams)"
          ></div>
        </NFormItem>

        <NDivider title-placement="left">找回密码验证码</NDivider>
        <NFormItem label="标题">
          <NInput :value="form.reset_password_subject" readonly />
        </NFormItem>
        <NFormItem label="HTML格式">
          <NSwitch :value="form.reset_password_is_html" disabled />
        </NFormItem>
        <NFormItem label="内容">
          <NInput
            v-if="!form.reset_password_is_html"
            type="textarea"
            :value="renderTemplate(form.reset_password_template, previewParams)"
            :autosize="{ minRows: 3, maxRows: 6 }"
            readonly
          />
          <div
            v-else
            class="preview-html"
            v-html="renderSafeTemplate(form.reset_password_template, previewParams)"
          ></div>
        </NFormItem>

        <NDivider title-placement="left">审核通过通知</NDivider>
        <NFormItem label="标题">
          <NInput :value="form.register_review_approve_subject" readonly />
        </NFormItem>
        <NFormItem label="HTML格式">
          <NSwitch :value="form.register_review_approve_is_html" disabled />
        </NFormItem>
        <NFormItem label="内容">
          <NInput
            v-if="!form.register_review_approve_is_html"
            type="textarea"
            :value="renderTemplate(form.register_review_approve_template, previewParams)"
            :autosize="{ minRows: 3, maxRows: 6 }"
            readonly
          />
          <div
            v-else
            class="preview-html"
            v-html="renderSafeTemplate(form.register_review_approve_template, previewParams)"
          ></div>
        </NFormItem>

        <NDivider title-placement="left">审核驳回通知</NDivider>
        <NFormItem label="标题">
          <NInput :value="form.register_review_reject_subject" readonly />
        </NFormItem>
        <NFormItem label="HTML格式">
          <NSwitch :value="form.register_review_reject_is_html" disabled />
        </NFormItem>
        <NFormItem label="内容">
          <NInput
            v-if="!form.register_review_reject_is_html"
            type="textarea"
            :value="renderTemplate(form.register_review_reject_template, previewParams)"
            :autosize="{ minRows: 3, maxRows: 6 }"
            readonly
          />
          <div
            v-else
            class="preview-html"
            v-html="renderSafeTemplate(form.register_review_reject_template, previewParams)"
          ></div>
        </NFormItem>

        <NDivider title-placement="left">管理员重置密码通知</NDivider>
        <NFormItem label="标题">
          <NInput :value="form.admin_reset_password_subject" readonly />
        </NFormItem>
        <NFormItem label="HTML格式">
          <NSwitch :value="form.admin_reset_password_is_html" disabled />
        </NFormItem>
        <NFormItem label="内容">
          <NInput
            v-if="!form.admin_reset_password_is_html"
            type="textarea"
            :value="renderTemplate(form.admin_reset_password_template, previewParams)"
            :autosize="{ minRows: 3, maxRows: 6 }"
            readonly
          />
          <div
            v-else
            class="preview-html"
            v-html="renderSafeTemplate(form.admin_reset_password_template, previewParams)"
          ></div>
        </NFormItem>

        <NDivider title-placement="left">工单提醒</NDivider>
        <NFormItem label="标题">
          <NInput :value="form.ticket_notify_subject" readonly />
        </NFormItem>
        <NFormItem label="HTML格式">
          <NSwitch :value="form.ticket_notify_is_html" disabled />
        </NFormItem>
        <NFormItem label="内容">
          <NInput
            v-if="!form.ticket_notify_is_html"
            type="textarea"
            :value="renderTemplate(form.ticket_notify_template, previewParams)"
            :autosize="{ minRows: 3, maxRows: 6 }"
            readonly
          />
          <div
            v-else
            class="preview-html"
            v-html="renderSafeTemplate(form.ticket_notify_template, previewParams)"
          ></div>
        </NFormItem>
      </NModal>
    </n-spin>
  </CommonPage>
</template>

<style scoped>
.template-editor {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.template-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.home-page-item {
  display: grid;
  grid-template-columns: minmax(160px, 220px) minmax(240px, 1fr) auto;
  gap: 12px;
  align-items: start;
}

.template-item :deep(.n-input) {
  flex: 1;
}

.home-page-item :deep(.n-base-selection) {
  width: 100%;
}

.preview-html {
  width: 100%;
  min-height: 80px;
  padding: 10px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fafafa;
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(260px, 1fr));
  gap: 4px 18px;
}

.mt-12 {
  margin-top: 12px;
}

@media (max-width: 900px) {
  .model-grid {
    grid-template-columns: 1fr;
  }
}
</style>
