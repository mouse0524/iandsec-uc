<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NInput, NModal, NSelect, NPopconfirm, NSpace, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TicketEditModal from '@/views/ticket/components/TicketEditModal.vue'
import api from '@/api'
import { openAuthRouteInNewTab } from '@/utils'
import { ticketStatusOptions, ticketStatusTextMap, ticketStatusTypeMap } from '@/views/ticket/components/ticket-meta'

defineOptions({ name: '工单审核' })

const $table = ref(null)
const router = useRouter()
const queryItems = ref({ status: 'pending_review' })
const tableData = ref([])
const summaryStats = ref({
  pending_review: 0,
  cs_rejected: 0,
  tech_processing: 0,
})
const editVisible = ref(false)
const editingTicket = ref({})
const commentVisible = ref(false)
const assignVisible = ref(false)
const reviewAction = ref(true)
const pendingReviewRow = ref(null)
const pendingAssignRow = ref(null)
const reviewComment = ref('')
const selectedTechId = ref(null)
const assignTechId = ref(null)
const assignComment = ref('')
const rootCauseOptions = ref([])
const categoryOptions = ref([])
const issueTypeOptions = ref([])
const impactScopeOptions = ref([])
const projectPhaseOptions = ref([])
const techOptions = ref([])
let ticketMetaPromise = null
const quickFilters = [
  { label: '待审核', value: 'pending_review' },
  { label: '已驳回', value: 'cs_rejected' },
  { label: '流转技术', value: 'tech_processing' },
]

const summaryCards = computed(() => {
  return [
    { label: '待审核工单', value: summaryStats.value.pending_review || 0, tone: 'warning' },
    { label: '已驳回', value: summaryStats.value.cs_rejected || 0, tone: 'error' },
    { label: '已流转技术', value: summaryStats.value.tech_processing || 0, tone: 'info' },
  ]
})

onMounted(() => {
  $table.value?.handleSearch()
})

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

function handleTableDataChange(rows) {
  tableData.value = Array.isArray(rows) ? rows : []
}

async function refreshSummaryStats() {
  try {
    const [pendingRes, rejectedRes, techRes] = await Promise.all([
      api.getTicketList({ page: 1, page_size: 1, status: 'pending_review' }),
      api.getTicketList({ page: 1, page_size: 1, status: 'cs_rejected' }),
      api.getTicketList({ page: 1, page_size: 1, status: 'tech_processing' }),
    ])
    summaryStats.value = {
      pending_review: Number(pendingRes?.total || 0),
      cs_rejected: Number(rejectedRes?.total || 0),
      tech_processing: Number(techRes?.total || 0),
    }
  } catch (error) {
    summaryStats.value = { pending_review: 0, cs_rejected: 0, tech_processing: 0 }
  }
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

async function getReviewTicketList(params) {
  const res = await api.getTicketList(params)
  const stats = res?.status_summary || {}
  summaryStats.value = {
    pending_review: Number(stats.pending_review || 0),
    cs_rejected: Number(stats.cs_rejected || 0),
    tech_processing: Number(stats.tech_processing || 0),
  }
  return res
}

async function review(row, approved) {
  if (approved && !selectedTechId.value) {
    $message.warning('审核通过时请先指派技术处理人')
    return
  }
  await api.reviewTicket({
    ticket_id: row.id,
    approved,
    comment: reviewComment.value?.trim() || (approved ? '审核通过' : '客服驳回'),
    tech_id: approved ? selectedTechId.value : null,
  })
  $message.success('审核操作已完成')
  commentVisible.value = false
  pendingReviewRow.value = null
  reviewComment.value = ''
  selectedTechId.value = null
  $table.value?.handleSearch()
}

function getDetailHref(row) {
  return router.resolve({ path: '/ticket/detail', query: { ticket_id: row.id } }).href
}

function openDetail(row) {
  if (!row?.id) return
  openAuthRouteInNewTab(getDetailHref(row))
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

function applyQuickFilter(status) {
  queryItems.value.status = status
  $table.value?.handleSearch()
}

async function openReviewAction(row, approved) {
  if (approved) await loadTechOptions()
  pendingReviewRow.value = row
  reviewAction.value = approved
  reviewComment.value = approved ? '审核通过' : '客服驳回'
  selectedTechId.value = null
  commentVisible.value = true
}

async function submitReviewAction() {
  if (!pendingReviewRow.value) return
  await review(pendingReviewRow.value, reviewAction.value)
}

async function openAssignAction(row) {
  await loadTechOptions()
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
    comment: assignComment.value?.trim() || '变更技术处理人',
  })
  $message.success('技术处理人已变更')
  assignVisible.value = false
  pendingAssignRow.value = null
  assignTechId.value = null
  assignComment.value = ''
  $table.value?.handleSearch()
}

const columns = [
  { title: '工单编号', key: 'ticket_no', align: 'center' },
  {
    title: '提交人',
    key: 'submitter_name',
    align: 'center',
    render(row) {
      return row.submitter_name || row.submitter_id || '-'
    },
  },
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
      return h(NTag, { type: ticketStatusTypeMap[row.status] || 'default' }, { default: () => ticketStatusTextMap[row.status] })
    },
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 300,
    render(row) {
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
      if (row.status === 'pending_review') {
        buttons.push(
          h(
            NButton,
            {
              size: 'small',
              type: 'success',
              onClick: () => openReviewAction(row, true),
            },
            { default: () => '通过' }
          )
        )
        buttons.push(
          h(
            NButton,
            { size: 'small', type: 'error', onClick: () => openReviewAction(row, false) },
            { default: () => '驳回' }
          )
        )
      }
      if (row.status === 'tech_processing') {
        buttons.push(
          h(
            NButton,
            {
              size: 'small',
              type: 'warning',
              onClick: () => openAssignAction(row),
            },
            { default: () => '改派技术' }
          )
        )
      }
      return h('div', { class: 'action-buttons' }, buttons)
    },
  },
]
</script>

<template>
  <CommonPage title="工单审核" :show-header="false" show-footer>
    <div class="ticket-review-page">
      <div class="summary-grid review-grid">
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
          :get-data="getReviewTicketList"
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

      <NModal v-model:show="commentVisible" preset="card" style="width: 520px" :title="reviewAction ? '审核通过备注' : '驳回备注'">
        <NSelect
          v-if="reviewAction"
          v-model:value="selectedTechId"
          class="mb-12"
          :options="techOptions"
          clearable
          filterable
          remote
          placeholder="请选择技术处理人（必填）"
          @focus="loadTechOptions"
          @search="loadTechOptions"
        />
        <NInput
          v-model:value="reviewComment"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 6 }"
          :placeholder="reviewAction ? '可填写审核说明' : '请填写驳回原因'"
        />
        <div class="modal-actions">
          <NButton @click="commentVisible = false">取消</NButton>
          <NButton type="primary" @click="submitReviewAction">确认提交</NButton>
        </div>
      </NModal>

      <NModal v-model:show="assignVisible" preset="card" style="width: 520px" title="变更技术处理人">
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
          placeholder="可填写改派原因"
        />
        <div class="modal-actions">
          <NButton @click="assignVisible = false">取消</NButton>
          <NButton type="primary" @click="submitAssignAction">确认变更</NButton>
        </div>
      </NModal>
    </div>
  </CommonPage>
</template>

<style scoped>
.ticket-review-page {
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

.summary-item[data-tone='warning'] {
  background: #fff7ed;
}

.summary-item[data-tone='error'] {
  background: #fff1f2;
}

.summary-item[data-tone='info'] {
  background: #eff6ff;
}

.table-shell {
  border-radius: 20px;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: nowrap;
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

</style>

