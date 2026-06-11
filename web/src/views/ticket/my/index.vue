<script setup>
import { computed, h, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NCard, NDropdown, NInput, NModal, NSelect, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import TicketDetailModal from '@/views/ticket/components/TicketDetailModal.vue'
import TicketEditModal from '@/views/ticket/components/TicketEditModal.vue'
import api from '@/api'
import { ticketStatusOptions, ticketStatusTextMap, ticketStatusTypeMap } from '@/views/ticket/components/ticket-meta'

defineOptions({ name: '我的工单' })

const $table = ref(null)
const route = useRoute()
const queryItems = ref({
  company_name: route.query.company_name || undefined,
  status: route.query.status || undefined,
  created_start: route.query.created_start || undefined,
  created_end: route.query.created_end || undefined,
  finished_start: route.query.finished_start || undefined,
  finished_end: route.query.finished_end || undefined,
})

watch(
  () => route.query,
  (query) => {
    queryItems.value = {
      ...queryItems.value,
      company_name: query.company_name || undefined,
      status: query.status || undefined,
      created_start: query.created_start || undefined,
      created_end: query.created_end || undefined,
      finished_start: query.finished_start || undefined,
      finished_end: query.finished_end || undefined,
    }
    $table.value?.handleSearch()
  }
)
const detailVisible = ref(false)
const detailLoading = ref(false)
const currentTicket = ref({})
const tableData = ref([])
const summaryStats = ref({
  total: 0,
  pending_review: 0,
  tech_processing: 0,
  pending_close: 0,
  done: 0,
  rejected: 0,
})
const editVisible = ref(false)
const editingTicket = ref({})
const fieldRejectVisible = ref(false)
const fieldRejectTicket = ref(null)
const fieldRejectComment = ref('')
const rootCauseOptions = ref([])
const categoryOptions = ref([])
const issueTypeOptions = ref([])
const impactScopeOptions = ref([])
const projectPhaseOptions = ref([])
const fallbackProjectPhases = ['售前', '实施', '售后']
const fallbackIssueTypes = ['现网问题', '现网需求', '产品建议']
const fallbackImpactScopes = ['全部', '偶现', '单台必现', '单台偶现']
const fallbackCategories = ['登录问题', '权限问题', '系统异常', '其他']
const fallbackRootCauses = ['代码缺陷', '配置错误', '环境异常', '数据问题', '操作不当', '第三方依赖']
const redmineStatusTextMap = {
  never: '未同步',
  success: '同步成功',
  failed: '同步失败',
  syncing: '同步中',
}

const summaryCards = computed(() => {
  const stats = summaryStats.value || {}
  return [
    { label: '当前总工单', value: stats.total || 0, tone: 'neutral' },
    { label: '审核中', value: stats.pending_review || 0, tone: 'warning' },
    { label: '技术处理中', value: stats.tech_processing || 0, tone: 'info' },
    { label: '待关闭', value: stats.pending_close || 0, tone: 'success' },
    { label: '已驳回', value: stats.rejected || 0, tone: 'error' },
    { label: '已关闭', value: stats.done || 0, tone: 'success' },
  ]
})

onMounted(() => {
  $table.value?.handleSearch()
  loadTicketMetaOptions()
})

function handleTableDataChange(rows) {
  tableData.value = Array.isArray(rows) ? rows : []
}

async function getMyTicketList(params = {}) {
  const res = await api.getTicketList(params)
  summaryStats.value = {
    total: Number(res?.status_summary?.total || 0),
    pending_review: Number(res?.status_summary?.pending_review || 0),
    tech_processing: Number(res?.status_summary?.tech_processing || 0),
    pending_close: Number(res?.status_summary?.pending_close || 0),
    done: Number(res?.status_summary?.done || 0),
    rejected: Number(res?.status_summary?.rejected || 0),
  }
  return res
}

function triggerDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

function formatExportTimestamp() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

async function exportTicketList() {
  const res = await api.exportTickets({ ...queryItems.value })
  const blob =
    res instanceof Blob
      ? res
      : new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  if (blob.type?.includes('application/json')) {
    const payload = JSON.parse(await blob.text())
    window.$message?.error(payload?.detail || payload?.msg || '导出失败')
    return
  }
  triggerDownload(blob, `tickets_${formatExportTimestamp()}.xlsx`)
}

async function loadTicketMetaOptions() {
  try {
    const res = await api.getPublicConfig()
    const config = res?.data || {}
    const projectPhases = config.ticket_project_phases?.length ? config.ticket_project_phases : fallbackProjectPhases
    const issueTypes = config.ticket_issue_types?.length ? config.ticket_issue_types : fallbackIssueTypes
    const impactScopes = config.ticket_impact_scopes?.length ? config.ticket_impact_scopes : fallbackImpactScopes
    const categories = config.ticket_categories?.length ? config.ticket_categories : fallbackCategories
    const rootCauses = config.ticket_root_causes?.length ? config.ticket_root_causes : fallbackRootCauses
    projectPhaseOptions.value = projectPhases.map((item) => ({ label: item, value: item }))
    issueTypeOptions.value = issueTypes.map((item) => ({ label: item, value: item }))
    impactScopeOptions.value = impactScopes.map((item) => ({ label: item, value: item }))
    categoryOptions.value = categories.map((item) => ({ label: item, value: item }))
    rootCauseOptions.value = rootCauses.map((item) => ({ label: item, value: item }))
  } catch (error) {
    rootCauseOptions.value = fallbackRootCauses.map((item) => ({ label: item, value: item }))
    categoryOptions.value = fallbackCategories.map((item) => ({ label: item, value: item }))
    issueTypeOptions.value = fallbackIssueTypes.map((item) => ({ label: item, value: item }))
    impactScopeOptions.value = fallbackImpactScopes.map((item) => ({ label: item, value: item }))
    projectPhaseOptions.value = fallbackProjectPhases.map((item) => ({ label: item, value: item }))
  }
}

async function openDetail(row) {
  currentTicket.value = row
  detailLoading.value = true
  detailVisible.value = true
  try {
    const res = await api.getTicketById({ ticket_id: row.id })
    if (currentTicket.value?.id === row.id) {
      currentTicket.value = res.data
    }
  } catch (error) {
    $message.error('加载工单详情失败')
  } finally {
    if (currentTicket.value?.id === row.id) {
      detailLoading.value = false
    }
  }
}

async function openEdit(row) {
  const detail = await api.getTicketById({ ticket_id: row.id })
  editingTicket.value = detail?.data || row
  editVisible.value = true
}

function handleEditSaved() {
  $table.value?.handleSearch()
}

async function closeTicket(row) {
  await api.closeTicket({ ticket_id: row.id, comment: '关闭工单' })
  $message.success('提出者已关闭工单')
  $table.value?.handleSearch()
}

async function handleFieldVerification(row, approved, comment = null) {
  await api.fieldVerificationTicket({
    ticket_id: row.id,
    approved,
    comment: comment || (approved ? '现场验证通过，关闭工单' : '现场验证不通过，退回技术处理'),
  })
  $message.success(approved ? '提出者已关闭工单' : '已退回技术处理')
  $table.value?.handleSearch()
}

function openFieldRejectModal(row) {
  fieldRejectTicket.value = row
  fieldRejectComment.value = ''
  fieldRejectVisible.value = true
}

async function submitFieldReject() {
  const comment = fieldRejectComment.value?.trim()
  if (!comment) {
    $message.warning('请填写退回备注')
    return
  }
  await handleFieldVerification(fieldRejectTicket.value, false, comment)
  fieldRejectVisible.value = false
  fieldRejectTicket.value = null
  fieldRejectComment.value = ''
}


function redmineDisplayStatus(row) {
  return row.redmine_status_name || redmineStatusTextMap[row.redmine_sync_status] || '-'
}

function redmineSyncTagType(row) {
  if (row.redmine_sync_status === 'failed') return 'error'
  if (row.redmine_sync_status === 'success') return 'success'
  if (row.redmine_sync_status === 'syncing') return 'info'
  return 'warning'
}

function moreOptions(row) {
  const options = []
  if (row.status !== 'done') {
    options.push({ label: '编辑工单', key: 'edit-ticket' })
  }
  if (row.status === 'pending_close') {
    options.push({ label: '关闭工单', key: 'close-ticket' })
  }
  if (row.status === 'field_verification') {
    options.push(
      { label: '关闭工单', key: 'field-approve' },
      { label: '退回技术', key: 'field-reject' }
    )
  }
  return options
}

function handleMoreAction(key, row) {
  if (key === 'edit-ticket') return openEdit(row)
  if (key === 'close-ticket') return closeTicket(row)
  if (key === 'field-approve') return handleFieldVerification(row, true)
  if (key === 'field-reject') return openFieldRejectModal(row)
}

const columns = [
  { title: '工单编号', key: 'ticket_no', align: 'center' },
  { title: '项目名称', key: 'company_name', align: 'center', ellipsis: { tooltip: true } },
  { title: '项目阶段', key: 'project_phase', align: 'center' },
  { title: '跟踪', key: 'issue_type', align: 'center' },
  { title: '影响范围', key: 'impact_scope', align: 'center' },
  { title: '问题分类', key: 'category', align: 'center' },
  { title: '标题', key: 'title', align: 'center', ellipsis: { tooltip: true } },
  { title: '问题根因', key: 'root_cause', align: 'center', ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    align: 'center',
    render(row) {
      return h(NTag, { type: ticketStatusTypeMap[row.status] || 'default' }, { default: () => ticketStatusTextMap[row.status] })
    },
  },
  {
    title: 'Redmine状态',
    key: 'redmine_status_name',
    align: 'center',
    render(row) {
      return h(
        NTag,
        { type: redmineSyncTagType(row), bordered: false },
        { default: () => redmineDisplayStatus(row) }
      )
    },
  },
  { title: '创建时间', key: 'created_at', align: 'center' },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 180,
    render(row) {
      const options = moreOptions(row)
      const buttons = [
        h(
          NButton,
          { size: 'small', type: 'info', onClick: () => openDetail(row) },
          { default: () => '详情' }
        ),
      ]
      if (options.length) {
        buttons.push(
          h(
            NDropdown,
            {
              trigger: 'click',
              options,
              onSelect: (key) => handleMoreAction(key, row),
            },
            {
              default: () => h(
                NButton,
                {
                  size: 'small',
                  color: '#7c3aed',
                  textColor: '#fff',
                },
                { default: () => '更多' }
              ),
            }
          )
        )
      }
      return h('div', { class: 'action-buttons' }, buttons)
    },
  },
]

</script>

<template>
  <CommonPage title="我的工单" show-footer>
    <div class="ticket-my-page">
      <div class="summary-grid">
        <div v-for="item in summaryCards" :key="item.label" class="summary-card" :data-tone="item.tone">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>

      <NCard size="small" class="table-shell">
        <CrudTable
          ref="$table"
          v-model:query-items="queryItems"
          :columns="columns"
          :get-data="getMyTicketList"
          @on-data-change="handleTableDataChange"
        >
          <template #queryBar>
            <QueryBarItem label="项目名称" :label-width="64">
              <NInput v-model:value="queryItems.company_name" clearable placeholder="输入项目名称" @keypress.enter="$table?.handleSearch()" />
            </QueryBarItem>
            <QueryBarItem label="标题" :label-width="40">
              <n-input v-model:value="queryItems.title" clearable placeholder="输入标题" @keypress.enter="$table?.handleSearch()" />
            </QueryBarItem>
            <QueryBarItem label="分类" :label-width="40">
              <NSelect v-model:value="queryItems.category" :options="categoryOptions" clearable placeholder="选择分类" style="width: 180px" />
            </QueryBarItem>
            <QueryBarItem label="跟踪" :label-width="40">
              <NSelect
                v-model:value="queryItems.issue_type"
                :options="issueTypeOptions"
                clearable
                placeholder="选择跟踪"
                style="width: 180px"
              />
            </QueryBarItem>
            <QueryBarItem label="影响" :label-width="40">
              <NSelect
                v-model:value="queryItems.impact_scope"
                :options="impactScopeOptions"
                clearable
                placeholder="选择影响范围"
                style="width: 180px"
              />
            </QueryBarItem>
            <QueryBarItem label="阶段" :label-width="40">
              <NSelect
                v-model:value="queryItems.project_phase"
                :options="projectPhaseOptions"
                clearable
                placeholder="选择阶段"
                style="width: 180px"
              />
            </QueryBarItem>
            <QueryBarItem label="状态" :label-width="40">
              <NSelect v-model:value="queryItems.status" :options="ticketStatusOptions" clearable placeholder="选择状态" style="width: 180px" />
            </QueryBarItem>
            <QueryBarItem label="根因" :label-width="40">
              <NSelect
                v-model:value="queryItems.root_cause"
                :options="rootCauseOptions"
                clearable
                placeholder="选择问题根因"
                style="width: 180px"
              />
            </QueryBarItem>
            <QueryBarItem label="" :label-width="0">
              <NButton type="primary" secondary @click="exportTicketList">导出</NButton>
            </QueryBarItem>
          </template>
        </CrudTable>
      </NCard>

      <TicketDetailModal v-model:visible="detailVisible" :ticket="currentTicket" :loading="detailLoading" />

      <TicketEditModal
        v-model:visible="editVisible"
        :ticket="editingTicket"
        :options="{
          projectPhases: projectPhaseOptions,
          issueTypes: issueTypeOptions,
          impactScopes: impactScopeOptions,
          categories: categoryOptions,
        }"
        @saved="handleEditSaved"
      />

      <NModal
        v-model:show="fieldRejectVisible"
        preset="card"
        title="退回技术"
        style="width: min(520px, 92vw)"
      >
        <NInput
          v-model:value="fieldRejectComment"
          type="textarea"
          placeholder="请填写现场验证不通过的原因或补充说明"
          :autosize="{ minRows: 4, maxRows: 8 }"
          maxlength="1000"
          show-count
        />
        <div class="modal-actions">
          <NButton @click="fieldRejectVisible = false">取消</NButton>
          <NButton type="warning" @click="submitFieldReject">确认退回</NButton>
        </div>
      </NModal>
    </div>
  </CommonPage>
</template>

<style scoped>
.ticket-my-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  min-width: 0;
  padding: 14px 12px;
  border-radius: 18px;
  border: 1px solid #ebeef5;
  background: #fff;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.05);
}

.summary-card span {
  display: block;
  color: #6b7280;
  font-size: 13px;
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  font-size: 28px;
  line-height: 1;
  color: #111827;
}

.summary-card[data-tone='warning'] {
  background: linear-gradient(180deg, #fffaf0 0%, #ffffff 100%);
}

.summary-card[data-tone='info'] {
  background: linear-gradient(180deg, #f3f8ff 0%, #ffffff 100%);
}

.summary-card[data-tone='error'] {
  background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%);
}

.summary-card[data-tone='success'] {
  background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%);
}

.table-shell {
  border-radius: 20px;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.edit-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.edit-alert {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #fde68a;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
  line-height: 1.5;
}

.edit-section {
  padding: 14px;
  border: 1px solid #ebeef5;
  border-radius: 14px;
  background: #ffffff;
}

.edit-section-head {
  margin-bottom: 8px;
}

.edit-section-head h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}

.edit-section-head p {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.edit-section-head.compact {
  margin-bottom: 10px;
}

.edit-grid {
  display: grid;
  gap: 10px 14px;
}

.edit-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.edit-grid.single-col {
  grid-template-columns: minmax(0, 1fr);
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

.upload-box {
  width: 100%;
}

.captcha-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.captcha-img {
  width: 120px;
  height: 34px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  background: #fff;
  object-fit: cover;
}

@media (max-width: 960px) {
  .summary-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 8px;
  }

  .summary-card {
    padding: 12px 8px;
  }

  .summary-card strong {
    font-size: 22px;
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .edit-grid.two-col {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
