<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { NButton, NCard, NInput, NModal, NSelect, NSpace, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import RichTextEditor from '@/components/editor/RichTextEditor.vue'
import TicketDetailModal from '@/views/ticket/components/TicketDetailModal.vue'
import api from '@/api'
import { ticketStatusOptions, ticketStatusTextMap, ticketStatusTypeMap } from '@/views/ticket/components/ticket-meta'

defineOptions({ name: '技术处理' })

const $table = ref(null)
const queryItems = ref({ status: 'tech_processing' })
const tableData = ref([])
const summaryStats = ref({
  tech_processing: 0,
  done: 0,
  tech_rejected: 0,
})
const detailVisible = ref(false)
const currentTicket = ref({})
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
const projectPhaseOptions = ref([])
const selectedRootCause = ref(null)
const techOptions = ref([])
const quickFilters = [
  { label: '处理中', value: 'tech_processing' },
  { label: '已完成', value: 'done' },
  { label: '技术驳回', value: 'tech_rejected' },
]

const summaryCards = computed(() => {
  return [
    { label: '处理中', value: summaryStats.value.tech_processing || 0, tone: 'info' },
    { label: '已完成', value: summaryStats.value.done || 0, tone: 'success' },
    { label: '技术驳回', value: summaryStats.value.tech_rejected || 0, tone: 'error' },
  ]
})

onMounted(() => {
  $table.value?.handleSearch()
  loadTicketMetaOptions()
  loadTechOptions()
  refreshSummaryStats()
})

function handleTableDataChange(rows) {
  tableData.value = Array.isArray(rows) ? rows : []
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

async function getTicketList(params) {
  const query = { ...(params || {}) }
  if (!query.status) {
    delete query.status
  }
  return api.getTicketList(query)
}

async function refreshSummaryStats() {
  try {
    const [processingRes, doneRes, rejectedRes] = await Promise.all([
      api.getTicketList({ page: 1, page_size: 1, status: 'tech_processing' }),
      api.getTicketList({ page: 1, page_size: 1, status: 'done' }),
      api.getTicketList({ page: 1, page_size: 1, status: 'tech_rejected' }),
    ])
    summaryStats.value = {
      tech_processing: Number(processingRes?.total || 0),
      done: Number(doneRes?.total || 0),
      tech_rejected: Number(rejectedRes?.total || 0),
    }
  } catch (error) {
    summaryStats.value = { tech_processing: 0, done: 0, tech_rejected: 0 }
  }
}

async function takeAction(row, action) {
  await api.techActionTicket({
    ticket_id: row.id,
    action,
    comment: actionComment.value?.trim() || (action === 'finish' ? '技术处理完成' : action === 'tech_reject' ? '技术驳回' : '处理中'),
    root_cause: action === 'finish' ? selectedRootCause.value : null,
  })
  $message.success('处理操作已完成')
  commentVisible.value = false
  pendingActionRow.value = null
  actionComment.value = ''
  selectedRootCause.value = null
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

function openTechAction(row, action) {
  pendingActionRow.value = row
  pendingActionType.value = action
  actionComment.value = action === 'finish' ? '技术处理完成' : '技术驳回'
  selectedRootCause.value = null
  commentVisible.value = true
}

async function submitTechAction() {
  if (!pendingActionRow.value) return
  if (pendingActionType.value === 'finish' && !selectedRootCause.value) {
    $message.warning('处理完成时必须选择问题根因')
    return
  }
  await takeAction(pendingActionRow.value, pendingActionType.value)
}

function openAssignAction(row) {
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
  refreshSummaryStats()
}

const columns = [
  { title: '工单编号', key: 'ticket_no', align: 'center' },
  { title: '标题', key: 'title', align: 'center', ellipsis: { tooltip: true } },
  { title: '项目阶段', key: 'project_phase', align: 'center' },
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
      if (row.status === 'tech_processing') {
        buttons.push(
          h(
            NButton,
            {
              size: 'small',
              type: 'success',
              onClick: () => openTechAction(row, 'finish'),
            },
            { default: () => '完成' }
          )
        )
        buttons.push(
          h(
            NButton,
            { size: 'small', type: 'error', onClick: () => openTechAction(row, 'tech_reject') },
            { default: () => '驳回' }
          )
        )
        buttons.push(
          h(
            NButton,
            { size: 'small', type: 'warning', onClick: () => openAssignAction(row) },
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
  <CommonPage title="技术处理" show-footer>
    <div class="ticket-tech-page">
      <div class="summary-grid tech-grid">
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
          :get-data="getTicketList"
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

      <NModal v-model:show="commentVisible" preset="card" style="width: 760px; max-width: 92vw" :title="pendingActionType === 'finish' ? '完成备注' : '驳回备注'">
        <NSelect
          v-if="pendingActionType === 'finish'"
          v-model:value="selectedRootCause"
          class="mb-12"
          :options="rootCauseOptions"
          :clearable="false"
          placeholder="请选择问题根因"
        />
        <RichTextEditor
          v-model="actionComment"
          :placeholder="pendingActionType === 'finish' ? '填写处理结果摘要，可直接粘贴图片' : '请填写驳回原因，可直接粘贴图片'"
          :min-height="180"
          :max-height="320"
        />
        <div class="upload-tip" v-if="pendingActionType === 'finish'">技术完成时必须选择问题根因，备注框支持直接粘贴图片。</div>
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
          placeholder="请选择新的技术处理人"
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
  display: grid;
  gap: 14px;
}

.tech-grid {
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

.summary-card[data-tone='info'] {
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
}

.summary-card[data-tone='success'] {
  background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%);
}

.summary-card[data-tone='error'] {
  background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%);
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

.upload-tip {
  margin-top: 8px;
  color: #6b7280;
  font-size: 12px;
}

@media (max-width: 900px) {
  .tech-grid {
    grid-template-columns: minmax(0, 1fr);
  }

}
</style>
