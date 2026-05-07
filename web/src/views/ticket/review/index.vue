<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { NButton, NCard, NInput, NModal, NSelect, NPopconfirm, NSpace, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TicketDetailModal from '@/views/ticket/components/TicketDetailModal.vue'
import api from '@/api'
import { ticketStatusOptions, ticketStatusTextMap, ticketStatusTypeMap } from '@/views/ticket/components/ticket-meta'

defineOptions({ name: '工单审核' })

const $table = ref(null)
const queryItems = ref({ status: 'pending_review' })
const tableData = ref([])
const summaryStats = ref({
  pending_review: 0,
  cs_rejected: 0,
  tech_processing: 0,
})
const detailVisible = ref(false)
const currentTicket = ref({})
const commentVisible = ref(false)
const reviewAction = ref(true)
const pendingReviewRow = ref(null)
const reviewComment = ref('')
const selectedTechId = ref(null)
const rootCauseOptions = ref([])
const categoryOptions = ref([])
const projectPhaseOptions = ref([])
const techOptions = ref([])
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
  loadTicketMetaOptions()
  loadTechOptions()
  refreshSummaryStats()
})

async function loadTechOptions() {
  try {
    const res = await api.getUserList({ page: 1, page_size: 9999 })
    const rows = Array.isArray(res?.data) ? res.data : []
    techOptions.value = rows
      .filter((item) => Array.isArray(item.roles) && item.roles.some((role) => role?.name === '技术'))
      .map((item) => ({ label: item.alias || item.username, value: item.id }))
  } catch (error) {
    techOptions.value = []
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
  try {
    const res = await api.getPublicConfig()
    const config = res?.data || {}
    projectPhaseOptions.value = (config.ticket_project_phases || []).map((item) => ({ label: item, value: item }))
    categoryOptions.value = (config.ticket_categories || []).map((item) => ({ label: item, value: item }))
    rootCauseOptions.value = (config.ticket_root_causes || []).map((item) => ({ label: item, value: item }))
  } catch (error) {
    rootCauseOptions.value = []
    categoryOptions.value = []
    projectPhaseOptions.value = []
  }
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
  refreshSummaryStats()
}

async function openDetail(row) {
  const res = await api.getTicketById({ ticket_id: row.id })
  currentTicket.value = res.data
  detailVisible.value = true
}

function applyQuickFilter(status) {
  queryItems.value.status = status
  $table.value?.handleSearch()
}

function openReviewAction(row, approved) {
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
  { title: '标题', key: 'title', align: 'center', ellipsis: { tooltip: true } },
  { title: '项目阶段', key: 'project_phase', align: 'center' },
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
      return h('div', { class: 'action-buttons' }, buttons)
    },
  },
]
</script>

<template>
  <CommonPage title="工单审核" show-footer>
    <div class="ticket-review-page">
      <div class="hero-panel review-hero">
        <div>
          <div class="hero-kicker">Review Queue</div>
          <h2>工单审核台</h2>
          <p>客服在这里统一筛查提交内容、确认问题归类，并将有效问题流转给技术处理。</p>
        </div>
        <div class="hero-badge">客服视角</div>
      </div>

      <div class="summary-grid review-grid">
        <div v-for="item in summaryCards" :key="item.label" class="summary-card" :data-tone="item.tone">
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
          :get-data="api.getTicketList"
          @on-data-change="handleTableDataChange"
        >
          <template #queryBar>
            <QueryBarItem label="标题" :label-width="40">
              <NInput v-model:value="queryItems.title" clearable placeholder="输入标题" @keypress.enter="$table?.handleSearch()" />
            </QueryBarItem>
            <QueryBarItem label="分类" :label-width="40">
              <NSelect v-model:value="queryItems.category" :options="categoryOptions" clearable placeholder="选择分类" style="width: 180px" />
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
          </template>
        </CrudTable>
      </NCard>

      <TicketDetailModal v-model:visible="detailVisible" :ticket="currentTicket" />

      <NModal v-model:show="commentVisible" preset="card" style="width: 520px" :title="reviewAction ? '审核通过备注' : '驳回备注'">
        <NSelect
          v-if="reviewAction"
          v-model:value="selectedTechId"
          class="mb-12"
          :options="techOptions"
          clearable
          placeholder="请选择技术处理人（必填）"
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
    </div>
  </CommonPage>
</template>

<style scoped>
.ticket-review-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-radius: 14px;
  color: #111827;
  background: #fff;
  border: 1px solid #e5e7eb;
  box-shadow: none;
}

.review-hero {
  background: #fff;
}

.hero-kicker {
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.85;
}

.hero-panel h2 {
  margin: 0;
  font-size: 22px;
}

.hero-panel p {
  max-width: 620px;
  margin: 6px 0 0;
  line-height: 1.55;
  font-size: 13px;
  opacity: 0.92;
}

.hero-badge {
  padding: 6px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
}

.summary-grid {
  display: grid;
  gap: 14px;
}

.review-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.summary-card {
  padding: 16px 18px;
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
  background: linear-gradient(180deg, #fff7ed 0%, #ffffff 100%);
}

.summary-card[data-tone='error'] {
  background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%);
}

.summary-card[data-tone='info'] {
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
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

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

@media (max-width: 900px) {
  .review-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .hero-panel {
    padding: 18px;
  }

  .hero-panel h2 {
    font-size: 24px;
  }

  .hero-badge {
    display: none;
  }
}
</style>
