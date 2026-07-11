<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NDropdown, NInput, NModal, NSelect, NSpace, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import RichTextEditor from '@/components/editor/RichTextEditor.vue'
import TicketEditModal from '@/views/ticket/components/TicketEditModal.vue'
import api from '@/api'
import { openAuthRouteInNewTab } from '@/utils'
import { ticketStatusOptions, ticketStatusTextMap, ticketStatusTypeMap } from '@/views/ticket/components/ticket-meta'

defineOptions({ name: '技术处理' })

const $table = ref(null)
const router = useRouter()
const queryItems = ref({ status: 'tech_processing' })
const tableData = ref([])
const summaryStats = ref({
  tech_processing: 0,
  field_verification: 0,
  pending_close: 0,
  done: 0,
  tech_rejected: 0,
})
const editVisible = ref(false)
const editingTicket = ref({})
const commentVisible = ref(false)
const assignVisible = ref(false)
const pendingActionRow = ref(null)
const pendingAssignRow = ref(null)
const pendingActionType = ref('finish')
const actionComment = ref('')
const assignTechId = ref(null)
const assignComment = ref('')
const rootCauseOptions = ref([])
const categoryOptions = ref([])
const issueTypeOptions = ref([])
const impactScopeOptions = ref([])
const projectPhaseOptions = ref([])
const selectedRootCause = ref(null)
const techOptions = ref([])
let ticketMetaPromise = null
const quickFilters = [
  { label: '处理中', value: 'tech_processing' },
  { label: '现场验证', value: 'field_verification' },
  { label: '待关闭', value: 'pending_close' },
  { label: '已关闭', value: 'done' },
  { label: '技术驳回', value: 'tech_rejected' },
]

const summaryCards = computed(() => {
  return [
    { label: '处理中', value: summaryStats.value.tech_processing || 0, tone: 'info' },
    { label: '现场验证', value: summaryStats.value.field_verification || 0, tone: 'warning' },
    { label: '待关闭', value: summaryStats.value.pending_close || 0, tone: 'success' },
    { label: '已关闭', value: summaryStats.value.done || 0, tone: 'success' },
    { label: '技术驳回', value: summaryStats.value.tech_rejected || 0, tone: 'error' },
  ]
})

onMounted(() => {
  $table.value?.handleSearch()
})

function handleTableDataChange(rows) {
  tableData.value = Array.isArray(rows) ? rows : []
}

async function loadTicketMetaOptions() {
  if (ticketMetaPromise) return ticketMetaPromise
  ticketMetaPromise = (async () => {
  try {
    const res = await api.getAppConfig()
    const config = res?.data || {}
    projectPhaseOptions.value = (config.ticket_project_phases || []).map((item) => ({ label: item, value: item }))
    issueTypeOptions.value = (config.ticket_issue_types || []).map((item) => ({ label: item, value: item }))
    impactScopeOptions.value = (config.ticket_impact_scopes || []).map((item) => ({ label: item, value: item }))
    categoryOptions.value = (config.ticket_categories || []).map((item) => ({ label: item, value: item }))
    rootCauseOptions.value = (config.ticket_root_causes || []).map((item) => ({ label: item, value: item }))
  } catch (error) {
    rootCauseOptions.value = []
    categoryOptions.value = []
    issueTypeOptions.value = []
    impactScopeOptions.value = []
    projectPhaseOptions.value = []
  }
  })()
  return ticketMetaPromise
}

async function loadTechOptions(keyword = '') {
  try {
    const res = await api.getUserList({ page: 1, page_size: 10, alias: keyword || undefined })
    const rows = Array.isArray(res?.data) ? res.data : []
    techOptions.value = rows
      .filter((item) => item.is_active !== false)
      .filter((item) => Array.isArray(item.roles) && item.roles.some((role) => role?.name === '技术'))
      .map((item) => ({ label: item.alias || item.username, value: item.id }))
  } catch (error) {
    techOptions.value = []
  }
}

function seedTechOption(row) {
  if (row.tech_id && row.tech_name && !techOptions.value.some((item) => item.value === row.tech_id)) {
    techOptions.value = [...techOptions.value, { label: row.tech_name, value: row.tech_id }]
  }
}

async function getTicketList(params) {
  const query = { ...(params || {}) }
  if (!query.status) {
    delete query.status
  }
  const res = await api.getTicketList(query)
  const stats = res?.status_summary || {}
  summaryStats.value = {
    tech_processing: Number(stats.tech_processing || 0),
    field_verification: Number(stats.field_verification || 0),
    pending_close: Number(stats.pending_close || 0),
    done: Number(stats.done || 0),
    tech_rejected: Number(stats.tech_rejected || 0),
  }
  return res
}

async function refreshSummaryStats() {
  try {
    const [processingRes, verificationRes, pendingCloseRes, doneRes, rejectedRes] = await Promise.all([
      api.getTicketList({ page: 1, page_size: 1, status: 'tech_processing' }),
      api.getTicketList({ page: 1, page_size: 1, status: 'field_verification' }),
      api.getTicketList({ page: 1, page_size: 1, status: 'pending_close' }),
      api.getTicketList({ page: 1, page_size: 1, status: 'done' }),
      api.getTicketList({ page: 1, page_size: 1, status: 'tech_rejected' }),
    ])
    summaryStats.value = {
      tech_processing: Number(processingRes?.total || 0),
      field_verification: Number(verificationRes?.total || 0),
      pending_close: Number(pendingCloseRes?.total || 0),
      done: Number(doneRes?.total || 0),
      tech_rejected: Number(rejectedRes?.total || 0),
    }
  } catch (error) {
    summaryStats.value = { tech_processing: 0, field_verification: 0, pending_close: 0, done: 0, tech_rejected: 0 }
  }
}

async function takeAction(row, action) {
  const transferToRd = isTransferToRdAction(row, action)
  await api.techActionTicket({
    ticket_id: row.id,
    action,
    comment: actionComment.value?.trim() || (transferToRd ? '技术转产研，进入测试过滤' : action === 'finish' ? '技术处理完成，等待关闭' : action === 'field_verify' ? '指派现场验证' : action === 'field_reject' ? '现场验证不通过，退回技术处理' : action === 'tech_reject' ? '技术驳回' : '处理进度更新'),
    root_cause: ['finish', 'field_verify'].includes(action) ? selectedRootCause.value : null,
  })
  $message.success(action === 'tech_note' ? '处理备注已记录' : transferToRd ? '已转入产研流程' : '处理操作已完成')
  commentVisible.value = false
  pendingActionRow.value = null
  actionComment.value = ''
  selectedRootCause.value = null
  $table.value?.handleSearch()
}

function getDetailHref(row) {
  return router.resolve({ path: '/ticket/detail', query: { ticket_id: row.id } }).href
}

function openDetail(row) {
  if (!row?.id) return
  openAuthRouteInNewTab(getDetailHref(row))
}

function applyQuickFilter(status) {
  queryItems.value.status = status
  $table.value?.handleSearch()
}

function openTechAction(row, action) {
  if (['finish', 'field_verify'].includes(action)) loadTicketMetaOptions()
  pendingActionRow.value = row
  pendingActionType.value = action
  actionComment.value = isTransferToRdAction(row, action) ? '技术转产研，进入测试过滤' : action === 'finish' ? '技术处理完成，等待关闭' : action === 'field_verify' ? '指派现场验证' : action === 'field_reject' ? '现场验证不通过，退回技术处理' : action === 'tech_reject' ? '技术驳回' : ''
  selectedRootCause.value = null
  commentVisible.value = true
}

async function openEdit(row) {
  await loadTicketMetaOptions()
  const res = await api.getTicketById({ ticket_id: row.id })
  editingTicket.value = res?.data || row
  editVisible.value = true
}

function handleEditSaved() {
  $table.value?.handleSearch()
}

async function closeTicket(row) {
  await api.closeTicket({ ticket_id: row.id, comment: '技术处理完成，关闭' })
  $message.success('技术已关闭工单')
  $table.value?.handleSearch()
}

function techActionModalTitle() {
  if (isTransferToRdAction(pendingActionRow.value, pendingActionType.value)) return '转产研备注'
  if (pendingActionType.value === 'finish') return '完成备注'
  if (pendingActionType.value === 'tech_note') return '处理进度备注'
  if (pendingActionType.value === 'field_verify') return '现场验证备注'
  if (pendingActionType.value === 'field_reject') return '验证不通过备注'
  return '驳回备注'
}

function techActionPlaceholder() {
  if (isTransferToRdAction(pendingActionRow.value, pendingActionType.value)) return '填写转产研说明、排查结论或复现信息，可直接粘贴图片'
  if (pendingActionType.value === 'finish') return '填写处理结果摘要，可直接粘贴图片'
  if (pendingActionType.value === 'tech_note') return '填写当前处理进度、排查结论或下一步计划，可直接粘贴图片'
  if (pendingActionType.value === 'field_verify') return '填写现场验证安排或说明，可直接粘贴图片'
  if (pendingActionType.value === 'field_reject') return '填写现场验证不通过原因，可直接粘贴图片'
  return '请填写驳回原因，可直接粘贴图片'
}

async function submitTechAction() {
  if (!pendingActionRow.value) return
  if (pendingActionType.value === 'tech_note' && !actionComment.value?.trim()) {
    $message.warning('请填写当前问题处理进度')
    return
  }
  if (['finish', 'field_verify'].includes(pendingActionType.value) && !selectedRootCause.value) {
    $message.warning(pendingActionType.value === 'field_verify' ? '转现场验证时必须选择问题根因' : isTransferToRdAction(pendingActionRow.value, pendingActionType.value) ? '转产研时必须选择问题根因' : '处理完成时必须选择问题根因')
    return
  }
  await takeAction(pendingActionRow.value, pendingActionType.value)
}

function openAssignAction(row) {
  loadTechOptions()
  seedTechOption(row)
  pendingAssignRow.value = row
  assignTechId.value = row.tech_id || null
  assignComment.value = ''
  assignVisible.value = true
}

async function submitAssignAction() {
  if (!pendingAssignRow.value) return
  if (!assignTechId.value) {
    $message.warning('请选择新的技术处理人')
    return
  }
  await api.assignTicketTech({
    ticket_id: pendingAssignRow.value.id,
    tech_id: assignTechId.value,
    comment: assignComment.value?.trim() || '技术处理页改派技术处理人',
  })
  $message.success('技术处理人已变更')
  assignVisible.value = false
  pendingAssignRow.value = null
  assignTechId.value = null
  assignComment.value = ''
  $table.value?.handleSearch()
}

function moreOptions(row) {
  const options = [
  ]
  if (row.status !== 'done') {
    options.push({ label: '编辑工单', key: 'edit-ticket' })
  }
  if (['tech_processing', 'field_verification'].includes(row.status)) {
    if (row.status === 'tech_processing') {
      options.push({ label: '指派现场验证', key: 'field-verify' })
    } else {
      options.push({ label: '验证不通过', key: 'field-reject' })
    }
    options.push(
      { label: '记录备注', key: 'tech-note' },
      { label: isTransferToRdAction(row, 'finish') ? '转产研' : '处理完成', key: 'finish' },
      { label: '技术驳回', key: 'tech-reject' },
      { label: '改派技术', key: 'assign-tech' },
    )
  }
  if (row.status === 'pending_close') {
    options.push({ label: '技术关闭', key: 'close-ticket' })
  }
  return options
}

function isTransferToRdAction(row, action) {
  return action === 'finish' && row?.status === 'tech_processing' && row?.issue_type === '现网问题'
}

function handleMoreAction(key, row) {
  if (key === 'edit-ticket') return openEdit(row)
  if (key === 'tech-note') return openTechAction(row, 'tech_note')
  if (key === 'field-verify') return openTechAction(row, 'field_verify')
  if (key === 'field-reject') return openTechAction(row, 'field_reject')
  if (key === 'finish') return openTechAction(row, 'finish')
  if (key === 'tech-reject') return openTechAction(row, 'tech_reject')
  if (key === 'assign-tech') return openAssignAction(row)
  if (key === 'close-ticket') return closeTicket(row)
}

const columns = [
  { title: '工单编号', key: 'ticket_no', align: 'center' },
  {
    title: '标题',
    key: 'title',
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return h(
        'a',
        {
          class: 'ticket-title-link',
          href: getDetailHref(row),
          target: '_blank',
          rel: 'noopener',
          onClick: (event) => {
            event.preventDefault()
            openDetail(row)
          },
        },
        row.title || '-'
      )
    },
  },
  {
    title: '联系人',
    key: 'contact_name',
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return row.contact_name || '-'
    },
  },
  {
    title: '手机号',
    key: 'phone',
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return row.phone || '-'
    },
  },
  { title: '项目阶段', key: 'project_phase', align: 'center' },
  { title: '跟踪', key: 'issue_type', align: 'center' },
  { title: '影响范围', key: 'impact_scope', align: 'center' },
  { title: '分类', key: 'category', align: 'center' },
  { title: '问题根因', key: 'root_cause', align: 'center', ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    align: 'center',
    render(row) {
      return h(
        NTag,
        { type: ticketStatusTypeMap[row.status] || 'default' },
        { default: () => ticketStatusTextMap[row.status] }
      )
    },
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 220,
    render(row) {
      const options = moreOptions(row)
      const buttons = [
        h(
          NButton,
          {
            size: 'small',
            type: 'info',
            onClick: () => openDetail(row),
          },
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
  <CommonPage title="技术处理" :show-header="false" show-footer>
    <div class="ticket-tech-page">
      <div class="summary-grid tech-grid">
        <div v-for="item in summaryCards" :key="item.label" class="summary-item" :data-tone="item.tone">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>

      <NSpace>
        <NButton
          v-for="item in quickFilters"
          :key="item.value"
          round
          :type="queryItems.status === item.value ? 'primary' : 'default'"
          :quaternary="queryItems.status !== item.value"
          @click="applyQuickFilter(item.value)"
        >
          {{ item.label }}
        </NButton>
      </NSpace>

      <NCard size="small" class="table-shell">
        <CrudTable
          ref="$table"
          v-model:query-items="queryItems"
          :columns="columns"
          :get-data="getTicketList"
          @on-data-change="handleTableDataChange"
        >
          <template #queryBar>
            <QueryBarItem label="项目名称" :label-width="64">
              <NInput v-model:value="queryItems.company_name" clearable placeholder="输入项目名称" @keypress.enter="$table?.handleSearch()" />
            </QueryBarItem>
            <QueryBarItem label="标题" :label-width="40">
              <NInput v-model:value="queryItems.title" clearable placeholder="输入标题" @keypress.enter="$table?.handleSearch()" />
            </QueryBarItem>
            <QueryBarItem label="分类" :label-width="40">
              <NSelect v-model:value="queryItems.category" :options="categoryOptions" clearable placeholder="选择分类" style="width: 180px" @focus="loadTicketMetaOptions" />
            </QueryBarItem>
            <QueryBarItem label="跟踪" :label-width="40">
              <NSelect
                v-model:value="queryItems.issue_type"
                :options="issueTypeOptions"
                clearable
                placeholder="选择跟踪"
                style="width: 180px"
                @focus="loadTicketMetaOptions"
              />
            </QueryBarItem>
            <QueryBarItem label="影响" :label-width="40">
              <NSelect
                v-model:value="queryItems.impact_scope"
                :options="impactScopeOptions"
                clearable
                placeholder="选择影响范围"
                style="width: 180px"
                @focus="loadTicketMetaOptions"
              />
            </QueryBarItem>
            <QueryBarItem label="阶段" :label-width="40">
              <NSelect
                v-model:value="queryItems.project_phase"
                :options="projectPhaseOptions"
                clearable
                placeholder="选择阶段"
                style="width: 180px"
                @focus="loadTicketMetaOptions"
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
                @focus="loadTicketMetaOptions"
              />
            </QueryBarItem>
          </template>
        </CrudTable>
      </NCard>

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
        v-model:show="commentVisible"
        preset="card"
        style="width: 760px; max-width: 92vw"
        :title="techActionModalTitle()"
      >
        <NSelect
          v-if="['finish', 'field_verify'].includes(pendingActionType)"
          v-model:value="selectedRootCause"
          class="mb-12"
          :options="rootCauseOptions"
          :clearable="false"
          placeholder="请选择问题根因"
          @focus="loadTicketMetaOptions"
        />
        <RichTextEditor
          v-model="actionComment"
          :placeholder="techActionPlaceholder()"
          :min-height="180"
          :max-height="320"
        />
        <div class="upload-tip" v-if="isTransferToRdAction(pendingActionRow, pendingActionType)">转产研时必须选择问题根因，备注框支持直接粘贴图片。</div>
        <div class="upload-tip" v-else-if="pendingActionType === 'finish'">技术完成时必须选择问题根因，备注框支持直接粘贴图片。</div>
        <div class="upload-tip" v-else-if="pendingActionType === 'field_verify'">转现场验证时必须选择问题根因，备注框支持直接粘贴图片。</div>
        <div class="upload-tip" v-else-if="pendingActionType === 'tech_note'">备注会记录到流转日志，不改变工单状态，支持直接粘贴图片。</div>
        <div class="upload-tip" v-else>备注框支持直接粘贴图片（与提交工单一致）。</div>
        <div class="modal-actions">
          <NButton @click="commentVisible = false">取消</NButton>
          <NButton type="primary" @click="submitTechAction">确认提交</NButton>
        </div>
      </NModal>

      <NModal v-model:show="assignVisible" preset="card" style="width: 520px" title="改派技术处理人">
        <NSelect
          v-model:value="assignTechId"
          class="mb-12"
          :options="techOptions"
          clearable
          filterable
          remote
          placeholder="请选择新的技术处理人"
          @focus="loadTechOptions"
          @search="loadTechOptions"
        />
        <NInput
          v-model:value="assignComment"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 5 }"
          placeholder="请填写改派备注"
        />
        <div class="modal-actions">
          <NButton @click="assignVisible = false">取消</NButton>
          <NButton type="primary" @click="submitAssignAction">确认改派</NButton>
        </div>
      </NModal>
    </div>
  </CommonPage>
</template>

<style scoped>
.ticket-tech-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.summary-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.04);
}

.summary-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 110px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #f8fafc;
  font-size: 12px;
}

.summary-item span {
  color: #6b7280;
}

.summary-item strong {
  color: #111827;
  font-size: 14px;
  line-height: 1;
}

.summary-item[data-tone='info'] {
  background: #eff6ff;
}

.summary-item[data-tone='success'] {
  background: #f0fdf4;
}

.summary-item[data-tone='error'] {
  background: #fff1f2;
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

.ticket-title-link {
  color: #2563eb;
  font-weight: 600;
  text-decoration: none;
}

.ticket-title-link:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

.upload-tip {
  margin-top: 8px;
  color: #6b7280;
  font-size: 12px;
}

</style>

