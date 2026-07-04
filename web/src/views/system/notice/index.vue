<script setup>
import { computed, h, ref } from 'vue'
import { NButton, NCard, NCheckbox, NCheckboxGroup, NInput, NSelect, NTag, NSwitch } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import api from '@/api'
import { sanitizeHtml } from '@/utils'

defineOptions({ name: '全局通知' })

const $table = ref(null)
const queryItems = ref({})
const roleOptions = ref([])
const userOptions = ref([])
const sending = ref(false)
const form = ref({
  title: '',
  target_type: 'all',
  target_role_ids: [],
  target_user_ids: [],
  delivery_channels: ['site'],
  is_html: true,
  content_html: '',
})
const previewHtmlVisible = ref(false)
const previewHtmlContent = ref('')
const presetHtml =
  '<div style="font-family:Arial,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;color:#1f2937;line-height:1.75;background:#f8fbff;border:1px solid #dbeafe;border-radius:12px;padding:16px 18px;"><h2 style="margin:0 0 10px;font-size:18px;color:#1d4ed8;">系统通知</h2><p style="margin:0 0 8px;">您好，<b>{name}</b>：</p><p style="margin:0;">这里填写通知正文内容，支持 HTML 格式排版。</p></div>'

const targetTypeOptions = [
  { label: '全员', value: 'all' },
  { label: '指定角色', value: 'roles' },
  { label: '指定用户', value: 'users' },
]

const targetTypeTextMap = {
  all: '全员',
  roles: '指定角色',
  users: '指定用户',
}

const deliveryChannelTextMap = {
  site: '站内通知',
  email: '邮件通知',
}

const deliveryChannelTypeMap = {
  site: 'info',
  email: 'success',
}

const plainTextLen = computed(() => String(form.value.content_html || '').replace(/<[^>]*>/g, '').trim().length)

async function loadRoleOptions(keyword = '') {
  const res = await api.getRoleList({ page: 1, page_size: 10, role_name: keyword || undefined })
  roleOptions.value = (res?.data || []).map((item) => ({ label: item.name, value: item.id }))
}

async function loadUserOptions(keyword = '') {
  const res = await api.getUserList({ page: 1, page_size: 10, alias: keyword || undefined })
  userOptions.value = (res?.data || [])
    .filter((item) => item.is_active !== false)
    .map((item) => ({ label: item.alias || item.username, value: item.id }))
}

async function sendNotice() {
  if (!plainTextLen.value) {
    $message.warning('请填写通知内容')
    return
  }
  if (plainTextLen.value > 2000) {
    $message.warning('通知内容纯文本长度不能超过2000')
    return
  }
  if (!form.value.delivery_channels.length) {
    $message.warning('请至少选择一种通知方式')
    return
  }
  if (form.value.target_type === 'roles' && !form.value.target_role_ids.length) {
    $message.warning('请选择目标角色')
    return
  }
  if (form.value.target_type === 'users' && !form.value.target_user_ids.length) {
    $message.warning('请选择目标用户')
    return
  }
  try {
    sending.value = true
    const res = await api.createNotice({
      ...form.value,
      content_html: form.value.content_html,
    })
    const data = res?.data || {}
    $message.success(
      `通知发送成功，覆盖 ${data.recipient_count || 0} 人，站内 ${data.site_recipient_count || 0} 人，邮件 ${data.email_recipient_count || 0} 人`
    )
    form.value = {
      title: '',
      target_type: 'all',
      target_role_ids: [],
      target_user_ids: [],
      delivery_channels: ['site'],
      is_html: true,
      content_html: '',
    }
    $table.value?.handleSearch()
  } finally {
    sending.value = false
  }
}

function applyDefaultTemplate() {
  if (!form.value.content_html?.trim()) {
    form.value.content_html = presetHtml
    form.value.is_html = true
    return
  }
  form.value.content_html = `${form.value.content_html}\n\n${presetHtml}`
  form.value.is_html = true
}

function openPreview() {
  if (!form.value.content_html?.trim()) {
    $message.warning('请先输入通知内容')
    return
  }
  previewHtmlContent.value = form.value.content_html
  previewHtmlVisible.value = true
}

function handleSearch() {
  $table.value?.handleSearch()
}

setTimeout(() => {
  $table.value?.handleSearch()
}, 0)

const columns = [
  { title: '发送时间', key: 'created_at', align: 'center', width: 160 },
  { title: '标题', key: 'title', align: 'center', width: 180, render: (row) => row.title || '系统通知' },
  {
    title: '发送范围',
    key: 'target_type',
    align: 'center',
    width: 140,
    render(row) {
      return h(NTag, { type: row.target_type === 'all' ? 'success' : row.target_type === 'roles' ? 'warning' : 'info' }, { default: () => targetTypeTextMap[row.target_type] || row.target_type })
    },
  },
  {
    title: '目标角色',
    key: 'target_role_names',
    align: 'center',
    width: 220,
    render(row) {
      return (row.target_role_names || []).join('、') || '-'
    },
  },
  {
    title: '通知方式',
    key: 'delivery_channels',
    align: 'center',
    width: 180,
    render(row) {
      const channels = row.delivery_channels?.length ? row.delivery_channels : ['site']
      return h(
        'div',
        { class: 'channel-tags' },
        channels.map((item) =>
          h(
            NTag,
            { size: 'small', type: deliveryChannelTypeMap[item] || 'default', bordered: false },
            { default: () => deliveryChannelTextMap[item] || item }
          )
        )
      )
    },
  },
  {
    title: '内容预览',
    key: 'content_html',
    align: 'left',
    render(row) {
      return h('div', { class: 'content-preview', innerHTML: sanitizeHtml(row.content_html || '') })
    },
  },
]
</script>

<template>
  <CommonPage title="全局通知" show-footer>
    <div class="notice-page">
      <div class="notice-hero">
        <div>
          <div class="hero-kicker">Announcement Center</div>
          <h2>全局通知中心</h2>
          <p>面向全员、角色或指定用户发送系统级通知，支持富文本消息，并保留历史记录用于审计追溯。</p>
        </div>
        <div class="hero-badge">最长2000字</div>
      </div>

      <NCard title="发送通知" size="small" class="send-card">
        <div class="form-grid">
          <NInput v-model:value="form.title" placeholder="通知标题（可选）" maxlength="100" />
          <NSelect v-model:value="form.target_type" :options="targetTypeOptions" />
          <div class="channel-checks">
            <span>通知方式</span>
            <NCheckboxGroup v-model:value="form.delivery_channels">
              <NCheckbox value="site">站内通知</NCheckbox>
              <NCheckbox value="email">邮件通知</NCheckbox>
            </NCheckboxGroup>
          </div>
          <div class="html-switch-wrap">
            <span>HTML格式</span>
            <NSwitch v-model:value="form.is_html" />
          </div>
          <NSelect
            v-if="form.target_type === 'roles'"
            v-model:value="form.target_role_ids"
            :options="roleOptions"
            multiple
            filterable
            remote
            placeholder="搜索角色"
            @focus="loadRoleOptions"
            @search="loadRoleOptions"
          />
          <NSelect
            v-if="form.target_type === 'users'"
            v-model:value="form.target_user_ids"
            :options="userOptions"
            multiple
            filterable
            remote
            placeholder="搜索用户姓名"
            @focus="loadUserOptions"
            @search="loadUserOptions"
          />
        </div>
        <div class="mt-12">
          <NInput v-model:value="form.content_html" type="textarea" :autosize="{ minRows: 6, maxRows: 10 }" placeholder="支持HTML，纯文本长度不超过2000" />
          <div class="len-tip" :class="{ 'is-warn': plainTextLen >= 1900, 'is-danger': plainTextLen >= 2000 }">纯文本长度：{{ plainTextLen }}/2000</div>
        </div>
        <div class="mt-12" flex justify-end>
          <NButton class="mr-10" @click="applyDefaultTemplate">应用默认HTML模板</NButton>
          <NButton class="mr-10" ghost type="primary" @click="openPreview">预览内容</NButton>
          <NButton type="primary" :loading="sending" @click="sendNotice">立即发送</NButton>
        </div>
      </NCard>

      <NCard title="通知记录" size="small" class="mt-16 record-card">
        <CrudTable ref="$table" v-model:query-items="queryItems" :columns="columns" :get-data="api.getNoticeList">
          <template #queryBar>
            <QueryBarItem label="标题" :label-width="40">
              <NInput v-model:value="queryItems.title" clearable placeholder="输入标题" @keypress.enter="handleSearch" />
            </QueryBarItem>
          </template>
        </CrudTable>
      </NCard>

      <NModal v-model:show="previewHtmlVisible" preset="card" title="通知内容预览" style="width: 760px">
        <div class="preview-zone" v-if="form.is_html" v-html="sanitizeHtml(previewHtmlContent)"></div>
        <NInput v-else type="textarea" :value="previewHtmlContent" :autosize="{ minRows: 8, maxRows: 16 }" readonly />
      </NModal>
    </div>
  </CommonPage>
</template>

<style scoped>
.notice-page { display: flex; flex-direction: column; gap: 14px; }

.notice-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px;
  border-radius: 14px;
  color: #111827;
  background: #fff;
  border: 1px solid #e5e7eb;
  box-shadow: none;
}

.hero-kicker {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.86;
}

.notice-hero h2 {
  margin: 0;
  font-size: 30px;
}

.notice-hero p {
  margin: 10px 0 0;
  max-width: 660px;
  line-height: 1.72;
  opacity: 0.92;
}

.hero-badge {
  padding: 10px 14px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 13px;
  font-weight: 600;
}

.send-card,
.record-card {
  border-radius: 14px;
}

.html-switch-wrap {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  min-height: 34px;
  background: #fff;
}

.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.channel-checks {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  min-height: 34px;
  background: #fff;
}
.channel-tags { display: inline-flex; flex-wrap: wrap; justify-content: center; gap: 6px; }
.len-tip { margin-top: 6px; color: #6b7280; font-size: 12px; text-align: right; }
.len-tip.is-warn { color: #d97706; }
.len-tip.is-danger { color: #dc2626; }
.content-preview {
  max-height: 120px;
  overflow: hidden;
  line-height: 1.6;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}

.preview-zone {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px;
  min-height: 120px;
  background: #fff;
}

@media (max-width: 960px) {
  .notice-hero {
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }
  .notice-hero h2 {
    font-size: 24px;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
