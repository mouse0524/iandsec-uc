<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { NButton, NCard, NDropdown, NInput, NModal, NSelect, NSpace, NTag, NTooltip } from 'naive-ui'
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
const detailLoading = ref(false)
const currentTicket = ref({})
const commentVisible = ref(false)
const assignVisible = ref(false)
const redmineVisible = ref(false)
const pendingActionRow = ref(null)
const pendingAssignRow = ref(null)
const pendingRedmineRow = ref(null)
const pendingActionType = ref('finish')
const actionComment = ref('')
const assignTechId = ref(null)
const assignComment = ref('')
const redmineLoadingMap = ref({})
const redmineForm = ref({
  project_id: null,
  tracker_id: null,
  priority_id: null,
  assigned_to_id: null,
  project_phase: '',
  os_value: '',
})
const rootCauseOptions = ref([])
const categoryOptions = ref([])
const issueTypeOptions = ref([])
const impactScopeOptions = ref([])
const projectPhaseOptions = ref([])
const selectedRootCause = ref(null)
const techOptions = ref([])
const redmineDefaultTrackerId = ref(null)
const redmineDefaultProjectId = ref(null)
const redmineDefaultPriorityId = ref(null)
const redmineDefaultAssignedToId = ref(null)
const redmineSyncVisibleFields = ref([])
const redmineSyncOptions = ref({})
const redmineProjectOptions = ref([])
const redmineTrackerOptionsFromApi = ref([])
const redminePriorityOptionsFromApi = ref([])
const redmineUserOptions = ref([])
const redmineOsOptions = ref([])
const redmineStatusTextMap = {
  never: '未同步',
  success: '同步成功',
  failed: '同步失败',
  syncing: '同步中',
}
const redmineTrackerOptions = computed(() => {
  if (redmineTrackerOptionsFromApi.value.length) return redmineTrackerOptionsFromApi.value
  return [
  { label: '现网问题', value: 8 },
  { label: '现网需求', value: 9 },
  ]
})
const redminePriorityOptions = computed(() => {
  if (redminePriorityOptionsFromApi.value.length) return redminePriorityOptionsFromApi.value
  return [
  { label: '建议', value: 1 },
  { label: '一般', value: 2 },
  { label: '严重', value: 3 },
  { label: '致命', value: 4 },
  ]
})
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
    comment: actionComment.value?.trim() || (action === 'finish' ? '技术处理完成' : action === 'tech_reject' ? '技术驳回' : '处理进度更新'),
    root_cause: action === 'finish' ? selectedRootCause.value : null,
  })
  $message.success(action === 'tech_note' ? '处理备注已记录' : '处理操作已完成')
  commentVisible.value = false
  pendingActionRow.value = null
  actionComment.value = ''
  selectedRootCause.value = null
  $table.value?.handleSearch()
  refreshSummaryStats()
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

function applyQuickFilter(status) {
  queryItems.value.status = status
  $table.value?.handleSearch()
}

function openTechAction(row, action) {
  pendingActionRow.value = row
  pendingActionType.value = action
  actionComment.value = action === 'finish' ? '技术处理完成' : action === 'tech_reject' ? '技术驳回' : ''
  selectedRootCause.value = null
  commentVisible.value = true
}

async function submitTechAction() {
  if (!pendingActionRow.value) return
  if (pendingActionType.value === 'tech_note' && !actionComment.value?.trim()) {
    $message.warning('请填写当前问题处理进度')
    return
  }
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

function setRedmineLoading(ticketId, loading) {
  redmineLoadingMap.value = {
    ...redmineLoadingMap.value,
    [ticketId]: loading,
  }
}

function redmineLoading(row) {
  return !!redmineLoadingMap.value[row.id]
}

function filterRedmineOptions(field, options) {
  const allowed = Array.isArray(redmineSyncOptions.value?.[field])
    ? redmineSyncOptions.value[field].map((item) => String(item))
    : []
  if (!allowed.length) return []
  return options.filter((item) => allowed.includes(String(item.value)))
}

function normalizeOptionText(value) {
  return String(value || '').trim().toLowerCase()
}

function findOptionByText(options, text) {
  const target = normalizeOptionText(text)
  if (!target) return null
  return options.find((item) => normalizeOptionText(item.value) === target)
    || options.find((item) => normalizeOptionText(item.label) === target)
    || options.find((item) => {
      const label = normalizeOptionText(item.label)
      return label && (label.includes(target) || target.includes(label))
    })
    || null
}

async function loadRedmineOptions() {
  if (redmineProjectOptions.value.length && redmineUserOptions.value.length && redmineTrackerOptionsFromApi.value.length && redminePriorityOptionsFromApi.value.length) return
  try {
    const res = await api.getRedmineMetadata()
    const projects = Array.isArray(res?.data?.projects) ? res.data.projects : []
    const trackers = Array.isArray(res?.data?.trackers) ? res.data.trackers : []
    const priorities = Array.isArray(res?.data?.priorities) ? res.data.priorities : []
    const users = Array.isArray(res?.data?.users) ? res.data.users : []
    const customFields = Array.isArray(res?.data?.custom_fields) ? res.data.custom_fields : []
    redmineDefaultProjectId.value = res?.data?.redmine_project_id || null
    redmineDefaultTrackerId.value = Number(res?.data?.redmine_tracker_id) || null
    redmineDefaultPriorityId.value = Number(res?.data?.redmine_priority_id) || null
    redmineDefaultAssignedToId.value = Number(res?.data?.redmine_assigned_to_id) || null
    redmineSyncVisibleFields.value = Array.isArray(res?.data?.redmine_sync_visible_fields)
      ? res.data.redmine_sync_visible_fields
      : []
    redmineSyncOptions.value = res?.data?.redmine_sync_options || {}
    redmineProjectOptions.value = filterRedmineOptions('project_id', projects
      .map((item) => ({ label: item.label || item.name || String(item.value || item.id), value: String(item.value || item.id) }))
      .filter((item) => item.value))
    redmineTrackerOptionsFromApi.value = filterRedmineOptions('tracker_id', trackers
      .map((item) => ({ label: item.label || item.name || String(item.id), value: Number(item.id) }))
      .filter((item) => item.value))
    redminePriorityOptionsFromApi.value = filterRedmineOptions('priority_id', priorities
      .map((item) => ({ label: item.label || item.name || String(item.id), value: Number(item.id) }))
      .filter((item) => item.value))
    redmineUserOptions.value = filterRedmineOptions('assigned_to_id', users
      .map((item) => ({ label: item.label || item.name || String(item.id), value: Number(item.id) }))
      .filter((item) => item.value))
    const osField = customFields.find((item) => Number(item.id) === Number(res?.data?.redmine_os_field_id))
      || customFields.find((item) => String(item.label || item.name || '').includes('操作系统'))
    redmineOsOptions.value = filterRedmineOptions('os', Array.isArray(osField?.possible_values) ? osField.possible_values : [])
  } catch (error) {
    redmineProjectOptions.value = []
    redmineTrackerOptionsFromApi.value = []
    redminePriorityOptionsFromApi.value = []
    redmineUserOptions.value = []
    redmineOsOptions.value = []
  }
}
function defaultRedmineTrackerId(row) {
  const issueType = String(row?.issue_type || '')
  const matched = findOptionByText(redmineTrackerOptions.value, issueType)
  if (matched) return matched.value

  const preferred = issueType.includes('需求') ? 9 : issueType.includes('建议') ? null : 8
  if (preferred && redmineTrackerOptions.value.some((item) => item.value === preferred)) return preferred
  return redmineTrackerOptions.value[0]?.value || null
}

function defaultRedmineProjectId() {
  return redmineProjectOptions.value[0]?.value || null
}

function defaultRedminePriorityId() {
  return redminePriorityOptions.value[0]?.value || null
}

function defaultRedmineAssignedToId() {
  return null
}

function defaultRedmineProjectPhase(row) {
  const matched = findOptionByText(redmineProjectPhaseOptions.value, row?.project_phase)
  if (matched) return matched.value
  return redmineProjectPhaseOptions.value[0]?.value || ''
}

async function openRedmineSync(row) {
  await loadRedmineOptions()
  pendingRedmineRow.value = row
  redmineForm.value = {
    project_id: defaultRedmineProjectId(),
    tracker_id: defaultRedmineTrackerId(row),
    priority_id: defaultRedminePriorityId(),
    assigned_to_id: defaultRedmineAssignedToId(),
    project_phase: defaultRedmineProjectPhase(row),
    os_value: '',
  }
  redmineVisible.value = true
}

async function pushRedmine(row, payload = {}) {
  setRedmineLoading(row.id, true)
  try {
    const res = await api.pushTicketRedmine({ ticket_id: row.id, ...payload })
    $message.success(res?.msg || 'Redmine????')
    $table.value?.handleSearch()
    if (currentTicket.value?.id === row.id) {
      currentTicket.value = res?.data || currentTicket.value
    }
  } finally {
    setRedmineLoading(row.id, false)
  }
}


function redmineFieldVisible(field) {
  return redmineSyncVisibleFields.value.includes(field)
}

const redmineProjectPhaseOptions = computed(() => filterRedmineOptions('project_phase', projectPhaseOptions.value))
const hasVisibleRedmineFields = computed(() => {
  return ['project_id', 'tracker_id', 'priority_id', 'assigned_to_id', 'project_phase', 'os'].some((field) => redmineFieldVisible(field))
})

async function submitRedmineSync() {
  if (!pendingRedmineRow.value) return
  const payload = {}
  if (redmineFieldVisible('project_id')) {
    if (!redmineForm.value.project_id) {
      $message.warning('请选择Redmine项目标识')
      return
    }
    payload.project_id = redmineForm.value.project_id
  }
  if (redmineFieldVisible('tracker_id')) {
    if (!redmineForm.value.tracker_id) {
      $message.warning('请选择Redmine跟踪')
      return
    }
    payload.tracker_id = redmineForm.value.tracker_id
  }
  if (redmineFieldVisible('priority_id')) {
    if (!redmineForm.value.priority_id) {
      $message.warning('请选择Redmine优先级')
      return
    }
    payload.priority_id = redmineForm.value.priority_id
  }
  if (redmineFieldVisible('assigned_to_id') && redmineForm.value.assigned_to_id) {
    payload.assigned_to_id = redmineForm.value.assigned_to_id
  }
  if (redmineFieldVisible('project_phase') && redmineForm.value.project_phase) {
    payload.project_phase = redmineForm.value.project_phase
  }
  if (redmineFieldVisible('os') && redmineForm.value.os_value) {
    payload.os_value = redmineForm.value.os_value
  }
  await pushRedmine(pendingRedmineRow.value, payload)
  redmineVisible.value = false
  pendingRedmineRow.value = null
}

async function pullRedmine(row) {
  setRedmineLoading(row.id, true)
  try {
    const res = await api.pullTicketRedmine({ ticket_id: row.id })
    $message.success(res?.msg || 'Redmine状态已更新')
    $table.value?.handleSearch()
    if (currentTicket.value?.id === row.id) {
      const detailRes = await api.getTicketById({ ticket_id: row.id })
      currentTicket.value = detailRes?.data || res?.data || currentTicket.value
    }
  } finally {
    setRedmineLoading(row.id, false)
  }
}

function openRedmine(row) {
  if (!row.redmine_issue_url) return
  window.open(row.redmine_issue_url, '_blank', 'noopener,noreferrer')
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

function renderRedmineCell(row) {
  const statusText = redmineDisplayStatus(row)
  const issueText = row.redmine_issue_id ? `#${row.redmine_issue_id}` : '未关联'
  const tooltipText = row.redmine_issue_id
    ? `Redmine ${issueText}，${statusText}`
    : `Redmine ${statusText}`
  const tags = row.redmine_issue_id
    ? [
        h(NTag, { type: redmineSyncTagType(row), bordered: false, size: 'small', class: 'redmine-tag' }, { default: () => issueText }),
        h(NTag, { type: redmineSyncTagType(row), bordered: false, size: 'small', class: 'redmine-tag' }, { default: () => statusText }),
      ]
    : [
        h(NTag, { type: redmineSyncTagType(row), bordered: false, size: 'small', class: 'redmine-tag' }, { default: () => statusText }),
      ]
  return h(
    NTooltip,
    { trigger: 'hover' },
    {
      trigger: () => h('div', { class: 'redmine-cell' }, tags),
      default: () => tooltipText,
    }
  )
}

function redmineMoreOptions(row) {
  const options = [
    { label: row.redmine_issue_id ? '更新Redmine' : '同步Redmine', key: 'push-redmine' },
  ]
  if (row.redmine_issue_id) {
    options.push({ label: '拉取Redmine', key: 'pull-redmine' })
    if (row.redmine_issue_url) {
      options.push({ label: '打开Redmine', key: 'open-redmine' })
    }
  }
  if (row.status === 'tech_processing') {
    options.push(
      { label: '记录备注', key: 'tech-note' },
      { label: '处理完成', key: 'finish' },
      { label: '技术驳回', key: 'tech-reject' },
      { label: '改派技术', key: 'assign-tech' },
    )
  }
  return options
}

function handleMoreAction(key, row) {
  if (key === 'push-redmine') return openRedmineSync(row)
  if (key === 'pull-redmine') return pullRedmine(row)
  if (key === 'open-redmine') return openRedmine(row)
  if (key === 'tech-note') return openTechAction(row, 'tech_note')
  if (key === 'finish') return openTechAction(row, 'finish')
  if (key === 'tech-reject') return openTechAction(row, 'tech_reject')
  if (key === 'assign-tech') return openAssignAction(row)
}

const columns = [
  { title: '工单编号', key: 'ticket_no', align: 'center' },
  { title: '标题', key: 'title', align: 'center', ellipsis: { tooltip: true } },
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
    title: 'Redmine',
    key: 'redmine_issue_id',
    align: 'center',
    width: 160,
    render(row) {
      return renderRedmineCell(row)
    },
  },
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
      const moreOptions = redmineMoreOptions(row)
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
      if (moreOptions.length) {
        buttons.push(
          h(
            NDropdown,
            {
              trigger: 'click',
              options: moreOptions,
              onSelect: (key) => handleMoreAction(key, row),
            },
            {
              default: () => h(
                NButton,
                {
                  size: 'small',
                  color: '#7c3aed',
                  textColor: '#fff',
                  loading: redmineLoading(row),
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
          </template>
        </CrudTable>
      </NCard>

      <TicketDetailModal v-model:visible="detailVisible" :ticket="currentTicket" :loading="detailLoading" />

      <NModal v-model:show="redmineVisible" preset="card" style="width: 520px" title="同步Redmine">
        <NAlert v-if="!hasVisibleRedmineFields" type="info" class="mb-12">
          当前未配置技术可选字段，本次同步将使用 Redmine 后台默认配置。
        </NAlert>
        <NSelect
          v-if="redmineFieldVisible('project_id')"
          v-model:value="redmineForm.project_id"
          class="mb-12"
          :options="redmineProjectOptions"
          :clearable="false"
          filterable
          placeholder="请选择Redmine项目标识"
        />
        <NSelect
          v-if="redmineFieldVisible('tracker_id')"
          v-model:value="redmineForm.tracker_id"
          class="mb-12"
          :options="redmineTrackerOptions"
          :clearable="false"
          placeholder="请选择Redmine跟踪"
        />
        <NSelect
          v-if="redmineFieldVisible('priority_id')"
          v-model:value="redmineForm.priority_id"
          class="mb-12"
          :options="redminePriorityOptions"
          :clearable="false"
          placeholder="请选择Redmine优先级"
        />
        <NSelect
          v-if="redmineFieldVisible('assigned_to_id')"
          v-model:value="redmineForm.assigned_to_id"
          class="mb-12"
          :options="redmineUserOptions"
          clearable
          placeholder="请选择Redmine指派人"
        />
        <NSelect
          v-if="redmineFieldVisible('project_phase')"
          v-model:value="redmineForm.project_phase"
          class="mb-12"
          :options="redmineProjectPhaseOptions"
          clearable
          placeholder="请选择项目阶段"
        />
        <NSelect
          v-if="redmineFieldVisible('os')"
          v-model:value="redmineForm.os_value"
          class="mb-12"
          :options="redmineOsOptions"
          clearable
          filterable
          placeholder="请选择操作系统"
        />
        <div class="modal-actions">
          <NButton @click="redmineVisible = false">取消</NButton>
          <NButton color="#7c3aed" text-color="#fff" :loading="pendingRedmineRow && redmineLoading(pendingRedmineRow)" @click="submitRedmineSync">
            确认同步
          </NButton>
        </div>
      </NModal>
      <NModal
        v-model:show="commentVisible"
        preset="card"
        style="width: 760px; max-width: 92vw"
        :title="pendingActionType === 'finish' ? '完成备注' : pendingActionType === 'tech_note' ? '处理进度备注' : '驳回备注'"
      >
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
          :placeholder="
            pendingActionType === 'finish'
              ? '填写处理结果摘要，可直接粘贴图片'
              : pendingActionType === 'tech_note'
                ? '填写当前处理进度、排查结论或下一步计划，可直接粘贴图片'
                : '请填写驳回原因，可直接粘贴图片'
          "
          :min-height="180"
          :max-height="320"
        />
        <div class="upload-tip" v-if="pendingActionType === 'finish'">技术完成时必须选择问题根因，备注框支持直接粘贴图片。</div>
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
  white-space: nowrap;
}

.redmine-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: default;
}

.redmine-tag {
  min-width: 68px;
  justify-content: center;
  font-size: 12px;
  line-height: 20px;
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
