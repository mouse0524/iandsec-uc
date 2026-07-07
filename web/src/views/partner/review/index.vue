<script setup>
import { computed, h, onMounted, ref, watch } from 'vue'
import { NButton, NInput, NInputGroup, NTag, NModal, NForm, NFormItem, NSelect, NTabs, NTabPane } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { useUserStore } from '@/store'

defineOptions({ name: '注册审核' })

const userStore = useUserStore()
const $table = ref(null)
const activeTab = ref('pending')
const queryItems = ref({ reviewed: false, register_type: 'all', keyword: '' })
const rejectModalVisible = ref(false)
const rejectSubmitting = ref(false)
const rejectingRow = ref(null)
const rejectFormRef = ref(null)
const rejectForm = ref({
  reason: '',
})
const inviteLink = ref('')
const inviteLoading = ref(false)
const inviteCopied = ref(false)
let inviteCopiedTimer = 0
const canCreateInvite = computed(() => (userStore.role || []).some((role) => role?.name === '技术'))

const statusTextMap = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
}

const registerTypeTextMap = {
  channel: '渠道商',
  user: '用户',
}

const registerTypeOptions = [
  { label: '全部类型', value: 'all' },
  { label: '渠道商', value: 'channel' },
  { label: '用户', value: 'user' },
]

function handleRegisterTypeChange(value) {
  queryItems.value.register_type = value || 'all'
  $table.value?.handleSearch()
}

watch(
  () => queryItems.value.register_type,
  (value) => {
    if (value === undefined || value === null || value === '') {
      queryItems.value.register_type = 'all'
    }
  }
)

onMounted(() => {
  $table.value?.handleSearch()
})

function buildInviteLink(code) {
  return `${window.location.origin}/login?invite_code=${encodeURIComponent(code)}`
}

async function createInviteLink() {
  inviteLoading.value = true
  try {
    const res = await api.createPartnerInvite()
    inviteLink.value = res?.data?.link || (res?.data?.code ? buildInviteLink(res.data.code) : '')
    inviteCopied.value = false
    if (inviteLink.value) $message.success('邀请链接已生成')
  } finally {
    inviteLoading.value = false
  }
}

async function copyText(text) {
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  const success = document.execCommand('copy')
  textarea.remove()
  if (!success) throw new Error('copy failed')
}

async function copyInviteLink() {
  if (!inviteLink.value) return
  try {
    await copyText(inviteLink.value)
    inviteCopied.value = true
    window.clearTimeout(inviteCopiedTimer)
    inviteCopiedTimer = window.setTimeout(() => {
      inviteCopied.value = false
    }, 1800)
    $message.success('邀请链接已复制')
  } catch (error) {
    $message.error('复制失败，请手动选中链接复制')
  }
}

function handleTabChange(tab) {
  activeTab.value = tab
  queryItems.value.reviewed = tab === 'reviewed'
  queryItems.value.keyword = ''
  $table.value?.handleSearch()
}

async function review(row, approved) {
  await api.reviewPartnerRegister({
    id: row.id,
    approved,
    comment: approved ? '审核通过' : '审核驳回',
  })
  $message.success('审核已完成，通知邮件已发送')
  $table.value?.handleSearch()
}

function openRejectModal(row) {
  rejectingRow.value = row
  rejectForm.value.reason = ''
  rejectModalVisible.value = true
}

function submitReject() {
  rejectFormRef.value?.validate(async (err) => {
    if (err) return
    try {
      rejectSubmitting.value = true
      await api.reviewPartnerRegister({
        id: rejectingRow.value.id,
        approved: false,
        comment: rejectForm.value.reason,
      })
      $message.success('驳回已提交，通知邮件已发送')
      rejectModalVisible.value = false
      $table.value?.handleSearch()
    } finally {
      rejectSubmitting.value = false
    }
  })
}

const baseColumns = [
  { title: '提交时间', key: 'created_at', align: 'center' },
  {
    title: '注册类型',
    key: 'register_type',
    align: 'center',
    render(row) {
      return registerTypeTextMap[row.register_type] || '-'
    },
  },
  { title: '公司名称', key: 'company_name', align: 'center' },
  { title: '联系人', key: 'contact_name', align: 'center' },
  { title: '邮箱', key: 'email', align: 'center' },
  { title: '手机号', key: 'phone', align: 'center' },
  { title: '设备机器码', key: 'hardware_id', align: 'center', render: (row) => row.hardware_id || '-' },
  {
    title: '状态',
    key: 'status',
    align: 'center',
    render(row) {
      const type = row.status === 'pending' ? 'warning' : row.status === 'approved' ? 'success' : 'error'
      return h(NTag, { type }, { default: () => statusTextMap[row.status] || row.status })
    },
  },
  {
    title: '审核时间',
    key: 'reviewed_at',
    align: 'center',
    render(row) {
      return row.reviewed_at || '-'
    },
  },
  {
    title: '驳回理由',
    key: 'review_comment',
    align: 'center',
    render(row) {
      if (row.status === 'rejected') {
        return row.review_comment || '-'
      }
      return '-'
    },
  },
]

const actionColumn = {
  title: '操作',
  key: 'actions',
  align: 'center',
  render(row) {
    if (row.status !== 'pending') return '-'
    return [
      h(
        NButton,
        {
          size: 'small',
          type: 'primary',
          style: 'margin-right: 8px',
          onClick: () => review(row, true),
        },
        { default: () => '通过' }
      ),
      h(
        NButton,
        { size: 'small', type: 'error', onClick: () => openRejectModal(row) },
        {
          default: () => '驳回',
        }
      ),
    ]
  },
}

const columns = computed(() => {
  if (activeTab.value === 'reviewed') {
    return baseColumns
  }
  return [...baseColumns, actionColumn]
})
</script>

<template>
  <CommonPage title="注册审核" show-footer>
    <NTabs type="line" :value="activeTab" @update:value="handleTabChange" mb-12>
      <NTabPane name="pending" tab="待审核" />
      <NTabPane name="reviewed" tab="已审核" />
    </NTabs>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getPartnerRegisterList"
    >
      <template #queryBar>
        <QueryBarItem v-if="canCreateInvite" label="" :label-width="0">
          <div class="invite-tools">
            <NButton type="primary" :loading="inviteLoading" @click="createInviteLink">
              <template #icon>
                <TheIcon icon="material-symbols:add-link-rounded" :size="18" />
              </template>
              {{ inviteLink ? '重新生成' : '生成邀请链接' }}
            </NButton>
            <NInputGroup v-if="inviteLink" class="invite-link-group">
              <NInput
                v-model:value="inviteLink"
                class="invite-link"
                readonly
                placeholder="邀请链接"
              />
              <NButton type="primary" secondary class="copy-button" @click="copyInviteLink">
                <template #icon>
                  <TheIcon
                    :icon="inviteCopied ? 'material-symbols:check-rounded' : 'material-symbols:content-copy-outline-rounded'"
                    :size="18"
                  />
                </template>
                {{ inviteCopied ? '已复制' : '复制' }}
              </NButton>
            </NInputGroup>
          </div>
        </QueryBarItem>
        <QueryBarItem label="注册类型" :label-width="60">
          <NSelect
            v-model:value="queryItems.register_type"
            :options="registerTypeOptions"
            placeholder="全部注册类型"
            style="width: 180px"
            @update:value="handleRegisterTypeChange"
          />
        </QueryBarItem>
        <QueryBarItem label="关键词" :label-width="50">
          <NInput
            v-model:value="queryItems.keyword"
            clearable
            placeholder="公司/联系人/邮箱/手机号"
            @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <NModal v-model:show="rejectModalVisible" preset="card" title="驳回注册申请" style="width: 520px">
      <NForm ref="rejectFormRef" :model="rejectForm" :rules="{ reason: { required: true, message: '请填写驳回理由', trigger: ['blur', 'input'] } }">
        <NFormItem label="驳回理由" path="reason">
          <NInput v-model:value="rejectForm.reason" type="textarea" placeholder="请输入驳回理由（将通过邮件通知用户）" />
        </NFormItem>
      </NForm>
      <template #footer>
        <div flex justify-end>
          <NButton @click="rejectModalVisible = false">取消</NButton>
          <NButton ml-12 type="error" :loading="rejectSubmitting" @click="submitReject">提交驳回</NButton>
        </div>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.invite-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-width: min(720px, 100%);
}

.invite-link-group {
  width: min(560px, calc(100vw - 320px));
  min-width: 320px;
  overflow: hidden;
  border-radius: 6px;
  box-shadow: inset 0 0 0 1px rgba(24, 160, 88, .12);
}

.invite-link :deep(.n-input__input-el) {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
}

.copy-button {
  min-width: 86px;
}

@media (max-width: 768px) {
  .invite-tools,
  .invite-link-group {
    width: 100%;
    min-width: 0;
  }
}
</style>
