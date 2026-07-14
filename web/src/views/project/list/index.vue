<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton,
  NDataTable,
  NDatePicker,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
  NTabPane,
  NTabs,
  NTag,
  NUpload,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import { ticketStatusTextMap, ticketStatusTypeMap } from '@/views/ticket/components/ticket-meta'
import { useUserStore } from '@/store'
import api from '@/api'
import { openAuthRouteInNewTab } from '@/utils'

defineOptions({ name: '项目列表' })

const remarkActivityType = '备注'
const userStore = useUserStore()
const router = useRouter()
const $table = ref(null)
const modalVisible = ref(false)
const editingId = ref(null)
const readonly = ref(false)
const queryItems = ref({})
const productOptions = ref([])
const statusOptions = ref([])
const regionOptions = ref([])
const serverVersionOptions = ref([])
const clientVersionOptions = ref([])
const userOptions = ref([])
const agentOptions = ref([])
const uploadLoading = ref(false)
const importLoading = ref(false)
const fileList = ref([])
const checkedProjectIds = ref([])
const batchModalVisible = ref(false)
const batchForm = ref(defaultBatchForm())
const workOrderVisible = ref(false)
const workOrderProject = ref(null)
const activeWorkOrderTab = ref('issues')
const workOrderLoading = ref(false)
const workOrders = ref({ issues: [], requirements: [], activities: [] })
const workOrderTotals = ref({ issues: 0, requirements: 0, activities: 0 })
const workOrderPages = ref({ issues: 1, requirements: 1, activities: 1 })
const workOrderPageSize = 10
const activityDetailVisible = ref(false)
const currentActivity = ref({})
const remarkTimeline = ref([])
const remarkForm = ref(defaultRemarkForm())
const remarkTimelineRows = computed(() => {
  const rows = []
  if (form.value.remark?.trim()) {
    rows.push({
      id: 'project-remark',
      activity_type: '原备注',
      content: form.value.remark,
      started_at: form.value.created_at,
      creator_name: form.value.creator_name,
    })
  }
  return rows.concat(remarkTimeline.value)
})
const activityForm = computed(() => ({
  ...currentActivity.value,
  started_at: currentActivity.value?.started_at ? Date.parse(currentActivity.value.started_at) : null,
}))
const defaultSummary = { total: 0, presale: 0, pending: 0, implementing: 0, pending_acceptance: 0, accepted: 0, lost: 0, product_points: [] }
const summary = ref({ ...defaultSummary })
const form = ref(defaultForm())
let optionsPromise = null

onMounted(async () => {
  await loadOptions()
  $table.value?.handleSearch()
})

function defaultForm() {
  return {
    project_name: '',
    created_at: '',
    product_points: [],
    region: null,
    agent_id: null,
    server_version: '',
    client_version: '',
    start_time: null,
    end_time: null,
    maintenance_time: null,
    customer_contact: '',
    customer_phone: '',
    customer_email: '',
    creator_name: '',
    status: null,
    assignee_id: null,
    attachment_ids: [],
    remark: '',
  }
}

function defaultBatchForm() {
  return {
    region: null,
    status: null,
    assignee_id: null,
  }
}

function defaultRemarkForm() {
  return {
    content: '',
  }
}

async function loadOptions() {
  if (optionsPromise) return optionsPromise
  optionsPromise = (async () => {
    const configRes = await api.getAppConfig()
    const config = configRes?.data || {}
    const products = config.project_products?.length ? config.project_products : ['安得卫士']
    const statuses = config.project_statuses?.length
      ? config.project_statuses
      : ['售前', '待实施', '实施中', '待验收', '已验收', '关闭']
    const regions = config.project_regions?.length ? config.project_regions : ['华东', '华南', '华北', '华中', '西南', '西北']
    const serverVersions = config.project_server_versions?.length ? config.project_server_versions : ['5.6.1']
    const clientVersions = config.project_client_versions?.length ? config.project_client_versions : ['2.25']
    productOptions.value = products.map((item) => ({ label: item, value: item }))
    statusOptions.value = statuses.map((item) => ({ label: item, value: item }))
    regionOptions.value = regions.map((item) => ({ label: item, value: item }))
    serverVersionOptions.value = serverVersions.map((item) => ({ label: item, value: item }))
    clientVersionOptions.value = clientVersions.map((item) => ({ label: item, value: item }))
  })()
  return optionsPromise
}

async function loadAgentOptions(keyword = '') {
  if (!keyword) return
  const res = await api.getDepts({ name: keyword })
  agentOptions.value = channelDeptOptions(res?.data || [])
}

async function loadUserOptions(keyword = '') {
  try {
    const res = await api.getUserList({ page: 1, page_size: 10, alias: keyword || undefined })
    userOptions.value = (res?.data || [])
      .filter((item) => item.is_active !== false)
      .filter((item) => Array.isArray(item.roles) && item.roles.some((role) => role?.name === '技术'))
      .map((item) => ({ label: item.alias || item.username, value: item.id }))
  } catch (error) {
    userOptions.value = []
  }
}

function seedAssigneeOption(row) {
  if (row.assignee_id && row.assignee_name && !userOptions.value.some((item) => item.value === row.assignee_id)) {
    userOptions.value = [...userOptions.value, { label: row.assignee_name, value: row.assignee_id }]
  }
}

function seedAgentOption(row) {
  if (row.agent_id && row.agent_name && !agentOptions.value.some((item) => item.value === row.agent_id)) {
    agentOptions.value = [...agentOptions.value, { label: row.agent_name, value: row.agent_id }]
  }
}

function channelDeptOptions(rows) {
  const channel = (rows || []).find((item) => item.name === '渠道部门')
  return (channel?.children || []).map((item) => ({ label: item.name, value: item.id }))
}

async function getProjectList(params) {
  const res = await api.projectList(params)
  summary.value = normalizeSummary(res?.summary)
  return res
}

function normalizeSummary(value) {
  const next = { ...defaultSummary, ...(value || {}) }
  next.product_points = Array.isArray(next.product_points) ? next.product_points : []
  return next
}

const selectedProducts = computed({
  get() {
    return (form.value.product_points || []).map((item) => item.product_name)
  },
  set(values) {
    const oldPoints = Object.fromEntries((form.value.product_points || []).map((item) => [item.product_name, item.points]))
    form.value.product_points = (values || []).map((name) => ({
      product_name: name,
      points: Number(oldPoints[name] || 0),
    }))
  },
})

function formatDateTime(value) {
  if (!value) return '-'
  if (typeof value === 'number') {
    const d = new Date(value)
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  }
  return String(value)
}

async function openCreate() {
  await Promise.all([loadOptions(), loadUserOptions()])
  editingId.value = null
  readonly.value = false
  form.value = {
    ...defaultForm(),
    created_at: Date.now(),
    product_points: productOptions.value[0]?.value ? [{ product_name: productOptions.value[0].value, points: 0 }] : [],
    region: regionOptions.value[0]?.value || null,
    status: statusOptions.value[0]?.value,
  }
  fileList.value = []
  modalVisible.value = true
}

function openProject(row, isReadonly) {
  loadOptions()
  seedAgentOption(row)
  seedAssigneeOption(row)
  const attachments = Array.isArray(row.attachments) ? row.attachments : []
  editingId.value = row.id
  readonly.value = isReadonly
  form.value = {
    ...defaultForm(),
    ...row,
    start_time: row.start_time ? Date.parse(row.start_time) : null,
    end_time: row.end_time ? Date.parse(row.end_time) : null,
    maintenance_time: row.maintenance_time ? Date.parse(row.maintenance_time) : null,
    attachment_ids: attachments.map((item) => Number(item.id)).filter((id) => id > 0),
  }
  fileList.value = attachments.map((item) => ({
    id: String(item.id),
    name: item.origin_name || `附件${item.id}`,
    status: 'finished',
    attachmentId: Number(item.id),
  }))
  remarkForm.value = defaultRemarkForm()
  loadRemarkTimeline(row.id)
  modalVisible.value = true
}

function openDetail(row) {
  openProject(row, true)
}

function openEdit(row) {
  openProject(row, false)
}

function openActivityDetail(row) {
  currentActivity.value = row
  activityDetailVisible.value = true
}

async function deleteActivity(row) {
  await api.projectActivityDelete({ activity_id: row.id })
  $message.success('项目日志已删除')
  await loadWorkOrders(workOrderProject.value, 'activities')
  $table.value?.handleSearch()
}

async function loadRemarkTimeline(projectId = editingId.value) {
  if (!projectId) {
    remarkTimeline.value = []
    return
  }
  const res = await api.projectActivityList({ page: 1, page_size: 100, project_id: projectId, activity_type: remarkActivityType })
  remarkTimeline.value = res?.data || []
}

async function submitRemarkTimeline() {
  if (readonly.value) return
  if (!editingId.value || !remarkForm.value.content?.trim()) {
    $message.warning('请填写备注')
    return
  }
  await api.projectActivityCreate({
    project_id: editingId.value,
    activity_type: remarkActivityType,
    title: remarkForm.value.content,
    content: remarkForm.value.content,
    status: '已完成',
    operator_id: userStore.userId || null,
    started_at: new Date().toISOString(),
  })
  $message.success('项目日志已添加')
  remarkForm.value.content = ''
  await loadRemarkTimeline()
  if (workOrderVisible.value && workOrderProject.value?.id === editingId.value) {
    await loadWorkOrders(workOrderProject.value, 'activities')
  }
  $table.value?.handleSearch()
}

async function submitProject() {
  if (readonly.value) return
  if (!form.value.project_name?.trim() || !form.value.product_points?.length) {
    $message.warning('请填写项目名称并选择使用产品')
    return
  }
  const payload = {
    ...form.value,
    product_points: (form.value.product_points || []).map((item) => ({
      product_name: item.product_name,
      points: Number(item.points || 0),
    })),
    start_time: form.value.start_time ? new Date(form.value.start_time).toISOString() : null,
    end_time: form.value.end_time ? new Date(form.value.end_time).toISOString() : null,
    maintenance_time: form.value.maintenance_time ? new Date(form.value.maintenance_time).toISOString() : null,
  }
  delete payload.created_at
  if (editingId.value) {
    await api.projectUpdate({ ...payload, project_id: editingId.value })
    $message.success('项目已更新')
  } else {
    await api.projectCreate(payload)
    $message.success('项目已创建')
  }
  modalVisible.value = false
  $table.value?.handleSearch()
}

async function customUpload({ file, onFinish, onError }) {
  try {
    uploadLoading.value = true
    const res = await api.uploadProjectAttachment(file.file)
    const attachmentId = Number(res?.data?.id || 0)
    if (!attachmentId) throw new Error('missing attachment id')
    file.attachmentId = attachmentId
    if (!form.value.attachment_ids.includes(attachmentId)) {
      form.value.attachment_ids.push(attachmentId)
    }
    onFinish()
  } catch {
    onError()
  } finally {
    uploadLoading.value = false
  }
}

async function customImport({ file, onFinish, onError }) {
  try {
    importLoading.value = true
    const res = await api.importProjects(file.file)
    const data = res?.data || {}
    const errors = Array.isArray(data.errors) ? data.errors : []
    const failed = errors.length
    if (failed) {
      console.error('[project.import] failed rows', errors)
      $message.warning(
        `导入完成：新增 ${data.created || 0}，更新 ${data.updated || 0}，失败 ${failed}。${errors
          .slice(0, 3)
          .map((item) => `第${item.row}行：${item.error}`)
          .join('；')}`,
      )
    } else {
      $message.success(`导入完成：新增 ${data.created || 0}，更新 ${data.updated || 0}，失败 0`)
    }
    await loadOptions()
    $table.value?.handleSearch()
    onFinish()
  } catch {
    onError()
  } finally {
    importLoading.value = false
  }
}

function handleChecked(rowKeys) {
  checkedProjectIds.value = rowKeys
}

async function openBatchUpdate() {
  if (!checkedProjectIds.value.length) {
    $message.warning('请先选择项目')
    return
  }
  await Promise.all([loadOptions(), loadUserOptions()])
  batchForm.value = defaultBatchForm()
  batchModalVisible.value = true
}

async function submitBatchUpdate() {
  const payload = {
    project_ids: checkedProjectIds.value,
    ...Object.fromEntries(Object.entries(batchForm.value).filter(([, value]) => value !== null && value !== '')),
  }
  if (Object.keys(payload).length <= 1) {
    $message.warning('请选择要修改的内容')
    return
  }
  const res = await api.projectBatchUpdate(payload)
  $message.success(`已修改 ${res?.data?.count || 0} 个项目`)
  batchModalVisible.value = false
  checkedProjectIds.value = []
  $table.value?.handleSearch()
}

async function deleteProjects(projectIds) {
  const ids = (projectIds || []).map(Number).filter((id) => id > 0)
  if (!ids.length) {
    $message.warning('请先选择项目')
    return
  }
  const res = await api.projectBatchDelete({ project_ids: ids })
  $message.success(`已删除 ${res?.data?.count || 0} 个项目`)
  checkedProjectIds.value = []
  $table.value?.handleSearch()
}

function handleRemove({ file }) {
  const attachmentId = Number(file?.attachmentId || 0)
  if (attachmentId > 0) {
    form.value.attachment_ids = form.value.attachment_ids.filter((id) => id !== attachmentId)
  }
}

async function downloadAttachment(file) {
  const attachmentId = Number(file?.attachmentId || file?.id || 0)
  if (!attachmentId) return
  const res = await api.downloadProjectAttachment({ attachment_id: attachmentId })
  const blob = res instanceof Blob ? res : new Blob([res])
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = file.name || 'download'
  a.click()
  URL.revokeObjectURL(url)
}

async function openWorkOrders(row) {
  workOrderProject.value = row
  activeWorkOrderTab.value = 'issues'
  workOrders.value = { issues: [], requirements: [], activities: [] }
  workOrderTotals.value = { issues: 0, requirements: 0, activities: 0 }
  workOrderPages.value = { issues: 1, requirements: 1, activities: 1 }
  workOrderVisible.value = true
  await loadWorkOrders(row)
}

async function loadWorkOrders(row, type = null) {
  if (!row) return
  workOrderLoading.value = true
  try {
    const loaders = {
      issues: () => api.getTicketList({ page: workOrderPages.value.issues, page_size: workOrderPageSize, company_name: row.project_name, issue_type: '现网问题' }),
      requirements: () => api.getTicketList({ page: workOrderPages.value.requirements, page_size: workOrderPageSize, company_name: row.project_name, issue_type: '现网需求' }),
      activities: () => api.projectActivityList({ page: workOrderPages.value.activities, page_size: workOrderPageSize, project_id: row.id }),
    }
    const types = type ? [type] : ['issues', 'requirements', 'activities']
    const responses = await Promise.all(types.map((item) => loaders[item]()))
    const nextOrders = { ...workOrders.value }
    const nextTotals = { ...workOrderTotals.value }
    types.forEach((item, index) => {
      nextOrders[item] = responses[index]?.data || []
      nextTotals[item] = responses[index]?.total || 0
    })
    workOrders.value = nextOrders
    workOrderTotals.value = nextTotals
  } finally {
    workOrderLoading.value = false
  }
}

function workOrderPagination(type) {
  return {
    page: workOrderPages.value[type],
    pageSize: workOrderPageSize,
    itemCount: workOrderTotals.value[type],
    prefix: ({ itemCount }) => `共 ${itemCount} 条`,
    onChange: (page) => {
      workOrderPages.value[type] = page
      loadWorkOrders(workOrderProject.value, type)
    },
  }
}

function getTicketDetailHref(row) {
  return router.resolve({ path: '/ticket/detail', query: { ticket_id: row.id } }).href
}

function openTicketDetail(row) {
  if (!row?.id) return
  openAuthRouteInNewTab(getTicketDetailHref(row))
}

const ticketColumns = [
  { title: '工单编号', key: 'ticket_no', align: 'center', width: 130, ellipsis: { tooltip: true } },
  {
    title: '标题',
    key: 'title',
    align: 'center',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => h(NButton, { text: true, type: 'primary', onClick: () => openTicketDetail(row) }, { default: () => row.title || '-' }),
  },
  {
    title: '状态',
    key: 'status',
    align: 'center',
    width: 120,
    render: (row) => h(NTag, { type: ticketStatusTypeMap[row.status] || 'default' }, { default: () => ticketStatusTextMap[row.status] || row.status || '-' }),
  },
  { title: '处理人', key: 'tech_name', align: 'center', width: 110, render: (row) => row.tech_name || '-' },
  { title: '创建时间', key: 'created_at', align: 'center', width: 170, render: (row) => row.created_at || '-' },
]

const activityColumns = [
  { title: '运维类型', key: 'activity_type', align: 'center', width: 120, ellipsis: { tooltip: true } },
  {
    title: '标题',
    key: 'title',
    align: 'center',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => h(NButton, { text: true, type: 'primary', onClick: () => openActivityDetail(row) }, { default: () => row.title || '-' }),
  },
  { title: '处理人', key: 'operator_name', align: 'center', width: 110, render: (row) => row.operator_name || '-' },
  { title: '处理时间', key: 'started_at', align: 'center', width: 170, render: (row) => row.started_at || '-' },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    fixed: 'right',
    width: 90,
    render(row) {
      return h(
        NPopconfirm,
        { onPositiveClick: () => deleteActivity(row) },
        {
          trigger: () => h(NButton, { size: 'small', type: 'error', text: true }, { default: () => '删除' }),
          default: () => '删除后不可恢复，是否继续？',
        }
      )
    },
  },
]

const columns = [
  { type: 'selection', fixed: 'left', width: 48 },
  { title: '区域', key: 'region', align: 'center', width: 90, render: (row) => row.region || '-' },
  { title: '所属代理商', key: 'agent_name', align: 'center', width: 150, render: (row) => row.agent_name || '-' },
  {
    title: '项目名称',
    key: 'project_name',
    align: 'center',
    width: 180,
    render(row) {
      return h(NButton, { text: true, type: 'primary', onClick: () => openDetail(row) }, { default: () => row.project_name || '-' })
    },
  },
  {
    title: '使用产品/点数',
    key: 'product_points',
    align: 'center',
    width: 220,
    render(row) {
      return (row.product_points || []).map((item) => `${item.product_name}：${item.points || 0}`).join('；') || '-'
    },
  },
  { title: '状态', key: 'status', align: 'center', width: 110, render: (row) => row.status || '-' },
  { title: '负责人', key: 'assignee_name', align: 'center', width: 120, render: (row) => row.assignee_name || '-' },
  { title: '创建时间', key: 'created_at', align: 'center', width: 170, render: (row) => row.created_at || '-' },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    fixed: 'right',
    width: 180,
    render(row) {
      return [
        h(NButton, { size: 'small', type: 'primary', text: true, onClick: () => openDetail(row) }, { default: () => '详情' }),
        h(NButton, { size: 'small', type: 'warning', text: true, style: 'margin-left: 6px', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: 'info', text: true, style: 'margin-left: 6px', onClick: () => openWorkOrders(row) }, { default: () => '工单' }),
        h(
          NPopconfirm,
          { onPositiveClick: () => deleteProjects([row.id]) },
          {
            trigger: () => h(NButton, { size: 'small', type: 'error', text: true, style: 'margin-left: 6px' }, { default: () => '删除' }),
            default: () => '删除后不可恢复，是否继续？',
          }
        ),
      ]
    },
  },
]
</script>

<template>
  <CommonPage title="项目管理" :show-header="false">
    <div class="summary-grid">
      <div class="summary-row product-summary">
        <span class="summary-label product-summary-title">使用产品/点数汇总</span>
        <div class="product-summary-list">
          <div v-for="item in summary.product_points.slice(0, 8)" :key="item.product_name" class="product-summary-item">
            <span class="product-summary-name">{{ item.product_name }}</span>
            <span class="product-summary-count">{{ item.points || 0 }}</span>
          </div>
          <span v-if="!summary.product_points?.length" class="product-summary-empty">暂无</span>
        </div>
      </div>
      <div class="summary-row">
        <div class="summary-item">
          <span class="summary-label">项目总数</span>
          <strong>{{ summary.total || 0 }}</strong>
        </div>
        <div class="summary-item" data-tone="warning">
          <span class="summary-label">售前</span>
          <strong>{{ summary.presale || 0 }}</strong>
        </div>
        <div class="summary-item" data-tone="warning">
          <span class="summary-label">待实施</span>
          <strong>{{ summary.pending || 0 }}</strong>
        </div>
        <div class="summary-item" data-tone="info">
          <span class="summary-label">实施中</span>
          <strong>{{ summary.implementing || 0 }}</strong>
        </div>
        <div class="summary-item" data-tone="info">
          <span class="summary-label">待验收</span>
          <strong>{{ summary.pending_acceptance || 0 }}</strong>
        </div>
        <div class="summary-item" data-tone="success">
          <span class="summary-label">已验收</span>
          <strong>{{ summary.accepted || 0 }}</strong>
        </div>
        <div class="summary-item" data-tone="error">
          <span class="summary-label">关闭</span>
          <strong>{{ summary.lost || 0 }}</strong>
        </div>
      </div>
    </div>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="getProjectList"
      :scroll-x="1568"
      @on-checked="handleChecked"
    >
      <template #queryBar>
        <QueryBarItem label="项目名称" :label-width="64">
          <NInput v-model:value="queryItems.project_name" clearable placeholder="输入项目名称" />
        </QueryBarItem>
        <QueryBarItem label="状态" :label-width="40">
          <NSelect v-model:value="queryItems.status" :options="statusOptions" clearable style="width: 160px" @focus="loadOptions" />
        </QueryBarItem>
        <QueryBarItem label="区域" :label-width="40">
          <NSelect v-model:value="queryItems.region" :options="regionOptions" clearable style="width: 140px" @focus="loadOptions" />
        </QueryBarItem>
        <QueryBarItem label="所属代理商" :label-width="72">
          <NSelect
            v-model:value="queryItems.agent_id"
            :options="agentOptions"
            clearable
            filterable
            remote
            style="width: 180px"
            @search="loadAgentOptions"
          />
        </QueryBarItem>
        <QueryBarItem label="负责人" :label-width="48">
          <NSelect
            v-model:value="queryItems.assignee_id"
            :options="userOptions"
            clearable
            filterable
            remote
            style="width: 160px"
            @focus="loadUserOptions"
            @search="loadUserOptions"
          />
        </QueryBarItem>
        <QueryBarItem label="使用产品" :label-width="64">
          <NSelect v-model:value="queryItems.product_name" :options="productOptions" clearable filterable style="width: 160px" @focus="loadOptions" />
        </QueryBarItem>
        <QueryBarItem label="服务器版本" :label-width="72">
          <NSelect v-model:value="queryItems.server_version" :options="serverVersionOptions" clearable filterable style="width: 160px" @focus="loadOptions" />
        </QueryBarItem>
        <QueryBarItem label="客户端版本" :label-width="72">
          <NSelect v-model:value="queryItems.client_version" :options="clientVersionOptions" clearable filterable style="width: 160px" @focus="loadOptions" />
        </QueryBarItem>
        <QueryBarItem label="" :label-width="0">
          <div class="toolbar-actions">
            <NButton type="primary" @click="openCreate">新增项目</NButton>
            <NUpload
              accept=".xlsx"
              :show-file-list="false"
              :custom-request="customImport"
            >
              <NButton type="info" :loading="importLoading">批量导入</NButton>
            </NUpload>
            <NButton type="warning" :disabled="!checkedProjectIds.length" @click="openBatchUpdate">批量修改</NButton>
            <NPopconfirm @positive-click="deleteProjects(checkedProjectIds)">
              <template #trigger>
                <NButton type="error" :disabled="!checkedProjectIds.length">批量删除</NButton>
              </template>
              删除选中的项目后不可恢复，是否继续？
            </NPopconfirm>
          </div>
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      :title="readonly ? '项目详情' : editingId ? '编辑项目' : '新增项目'"
      width="min(1280px, 96vw)"
      :show-footer="!readonly"
      @save="submitProject"
    >
      <div class="project-modal-head">
        <div>
          <div class="modal-eyebrow">{{ readonly ? '项目详情' : editingId ? '编辑项目' : '创建项目' }}</div>
          <div class="modal-project-name">{{ form.project_name || '填写项目名称' }}</div>
        </div>
        <div class="modal-tags">
          <NTag v-if="form.region" size="small" round>{{ form.region }}</NTag>
          <NTag v-if="form.status" size="small" round type="info">{{ form.status }}</NTag>
        </div>
      </div>
      <NForm class="project-form project-editor-form" label-placement="top">
        <div class="project-editor-body">
          <div class="form-section primary-section">
            <div class="section-title"><span>基础信息</span></div>
            <div class="form-grid">
              <NFormItem label="项目名称" class="span-full project-name-field"><NInput v-model:value="form.project_name" placeholder="请输入完整项目名称" :disabled="readonly" /></NFormItem>
              <NFormItem label="创建时间"><NInput :value="formatDateTime(form.created_at)" disabled /></NFormItem>
              <NFormItem v-if="readonly" label="创建人"><NInput :value="form.creator_name || '-'" disabled /></NFormItem>
              <NFormItem label="区域"><NSelect v-model:value="form.region" :options="regionOptions" clearable placeholder="选择区域" :disabled="readonly" /></NFormItem>
              <NFormItem label="所属代理商"><NSelect v-model:value="form.agent_id" :options="agentOptions" clearable filterable remote placeholder="搜索代理商" :disabled="readonly" @search="loadAgentOptions" /></NFormItem>
              <NFormItem label="项目状态"><NSelect v-model:value="form.status" :options="statusOptions" placeholder="选择状态" :disabled="readonly" /></NFormItem>
              <NFormItem label="服务器版本"><NSelect v-model:value="form.server_version" :options="serverVersionOptions" clearable filterable placeholder="选择服务器版本" :disabled="readonly" /></NFormItem>
              <NFormItem label="客户端版本"><NSelect v-model:value="form.client_version" :options="clientVersionOptions" clearable filterable placeholder="选择客户端版本" :disabled="readonly" /></NFormItem>
              <NFormItem label="开始时间"><NDatePicker v-model:value="form.start_time" type="date" clearable style="width: 100%" :disabled="readonly" /></NFormItem>
              <NFormItem label="结束时间"><NDatePicker v-model:value="form.end_time" type="date" clearable style="width: 100%" :disabled="readonly" /></NFormItem>
              <NFormItem label="维保时间"><NDatePicker v-model:value="form.maintenance_time" type="date" clearable style="width: 100%" :disabled="readonly" /></NFormItem>
            </div>
          </div>

          <div class="project-editor-main">
            <div class="form-section product-section">
              <div class="section-title"><span>产品点数</span></div>
              <NFormItem label="使用产品">
                <NSelect v-model:value="selectedProducts" :options="productOptions" multiple clearable placeholder="选择使用产品" :disabled="readonly" />
              </NFormItem>
              <div v-if="form.product_points.length" class="points-grid">
                <NFormItem v-for="item in form.product_points" :key="item.product_name" :label="`${item.product_name}点数`">
                  <NInputNumber v-model:value="item.points" :min="0" style="width: 100%" :disabled="readonly" />
                </NFormItem>
              </div>
            </div>

            <div class="form-section contact-section">
              <div class="section-title"><span>对接信息</span></div>
              <div class="form-grid contact-grid">
                <NFormItem label="负责人"><NSelect v-model:value="form.assignee_id" :options="userOptions" clearable filterable remote placeholder="搜索负责人" :disabled="readonly" @focus="loadUserOptions" @search="loadUserOptions" /></NFormItem>
                <NFormItem label="客户对接人"><NInput v-model:value="form.customer_contact" placeholder="请输入客户对接人" :disabled="readonly" /></NFormItem>
                <NFormItem label="联系电话"><NInput v-model:value="form.customer_phone" placeholder="请输入联系电话" :disabled="readonly" /></NFormItem>
                <NFormItem label="联系邮箱"><NInput v-model:value="form.customer_email" placeholder="请输入联系邮箱" :disabled="readonly" /></NFormItem>
              </div>
            </div>
          </div>

          <div class="project-editor-side">
            <div class="form-section remark-section">
              <div class="section-title"><span>项目日志</span></div>
              <div v-if="editingId" class="remark-timeline">
                <div v-if="!readonly" class="remark-add">
                  <NInput
                    v-model:value="remarkForm.content"
                    class="remark-input"
                    type="textarea"
                    placeholder="填写本次项目日志"
                    :autosize="{ minRows: 2, maxRows: 4 }"
                  />
                  <NButton class="remark-submit" type="primary" @click="submitRemarkTimeline">添加日志</NButton>
                </div>
                <div v-if="remarkTimelineRows.length" class="remark-list">
                  <div v-for="item in remarkTimelineRows" :key="item.id" class="remark-item">
                    <div class="remark-meta">
                      <NTag size="small" type="info">{{ item.activity_type || '-' }}</NTag>
                      <span>{{ item.started_at || item.created_at || '-' }}</span>
                      <span>{{ item.operator_name || item.creator_name || '-' }}</span>
                    </div>
                    <div class="remark-content">{{ item.content || item.title || '-' }}</div>
                  </div>
                </div>
                <div v-else class="remark-empty">暂无项目日志</div>
              </div>
              <NFormItem v-else label="项目日志">
                <NInput v-model:value="form.remark" type="textarea" placeholder="记录项目背景、当前进展或注意事项" :autosize="{ minRows: 2, maxRows: 4 }" />
              </NFormItem>
            </div>

            <div class="form-section attachment-section">
              <div class="section-title"><span>附件</span></div>
              <NFormItem label="项目附件">
                <NUpload
                  v-model:file-list="fileList"
                  :custom-request="customUpload"
                  :disabled="readonly"
                  :show-remove-button="!readonly"
                  @remove="handleRemove"
                >
                  <NButton :loading="uploadLoading" :disabled="readonly">上传附件</NButton>
                </NUpload>
              </NFormItem>
              <div v-if="fileList.length" class="attachment-list">
                <NButton
                  v-for="file in fileList"
                  :key="file.id"
                  text
                  type="primary"
                  @click="downloadAttachment(file)"
                >
                  {{ file.name }}
                </NButton>
              </div>
            </div>
          </div>
        </div>
      </NForm>
    </CrudModal>

    <CrudModal
      v-model:visible="batchModalVisible"
      title="批量修改项目"
      width="520px"
      @save="submitBatchUpdate"
    >
      <NForm class="project-form" label-placement="top">
        <NFormItem label="区域"><NSelect v-model:value="batchForm.region" :options="regionOptions" clearable /></NFormItem>
        <NFormItem label="状态"><NSelect v-model:value="batchForm.status" :options="statusOptions" clearable /></NFormItem>
        <NFormItem label="负责人"><NSelect v-model:value="batchForm.assignee_id" :options="userOptions" clearable filterable remote @focus="loadUserOptions" @search="loadUserOptions" /></NFormItem>
      </NForm>
    </CrudModal>

    <NDrawer v-model:show="workOrderVisible" placement="right" :width="920">
      <NDrawerContent :title="`${workOrderProject?.project_name || '-'} - 工单汇总`" closable>
        <NTabs v-model:value="activeWorkOrderTab" type="line" animated>
          <NTabPane name="issues" :tab="`问题单 (${workOrderTotals.issues})`">
            <NDataTable
              :columns="ticketColumns"
              :data="workOrders.issues"
              :loading="workOrderLoading"
              :pagination="workOrderPagination('issues')"
              remote
              size="small"
            />
          </NTabPane>
          <NTabPane name="requirements" :tab="`需求单 (${workOrderTotals.requirements})`">
            <NDataTable
              :columns="ticketColumns"
              :data="workOrders.requirements"
              :loading="workOrderLoading"
              :pagination="workOrderPagination('requirements')"
              remote
              size="small"
            />
          </NTabPane>
          <NTabPane name="activities" :tab="`项目日志 (${workOrderTotals.activities})`">
            <NDataTable
              :columns="activityColumns"
              :data="workOrders.activities"
              :loading="workOrderLoading"
              :pagination="workOrderPagination('activities')"
              remote
              size="small"
            />
          </NTabPane>
        </NTabs>
      </NDrawerContent>
    </NDrawer>

    <CrudModal v-model:visible="activityDetailVisible" title="项目日志详情" :show-footer="false" width="760px">
      <div class="project-modal-head">
        <div>
          <div class="modal-eyebrow">OPS DETAIL</div>
          <div class="modal-project-name">{{ currentActivity.title || '未命名项目日志' }}</div>
        </div>
        <div class="modal-tags">
          <NTag v-if="currentActivity.activity_type" size="small" round type="info">{{ currentActivity.activity_type }}</NTag>
        </div>
      </div>
      <NForm class="project-form" label-placement="top">
        <div class="form-section">
          <div class="section-title"><span>基础信息</span></div>
          <div class="form-grid">
            <NFormItem label="项目"><NInput :value="currentActivity.project_name || '-'" disabled /></NFormItem>
            <NFormItem label="运维类型"><NInput :value="currentActivity.activity_type || '-'" disabled /></NFormItem>
            <NFormItem label="标题" class="span-2"><NInput :value="currentActivity.title || '-'" disabled /></NFormItem>
          </div>
        </div>
        <div class="form-section">
          <div class="section-title"><span>处理信息</span></div>
          <div class="form-grid">
            <NFormItem label="处理人"><NInput :value="currentActivity.operator_name || '-'" disabled /></NFormItem>
            <NFormItem label="处理时间"><NDatePicker :value="activityForm.started_at" type="datetime" disabled clearable style="width: 100%" /></NFormItem>
          </div>
        </div>
        <div class="form-section">
          <div class="section-title"><span>项目日志内容</span></div>
          <NFormItem label="内容"><NInput :value="currentActivity.content || '-'" type="textarea" disabled :autosize="{ minRows: 4, maxRows: 8 }" /></NFormItem>
        </div>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>

<style scoped>
.actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
}

.project-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin: -4px 0 16px;
  padding: 18px 20px;
  border: 1px solid #cfe3ff;
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(255, 255, 255, 0) 42%),
    linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.modal-eyebrow {
  margin-bottom: 8px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

.modal-project-name {
  color: #0f172a;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.3;
  word-break: break-word;
}

.modal-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  max-width: 220px;
}

.project-form {
  max-height: 72vh;
  overflow-y: auto;
  padding: 0 4px 2px 0;
}

.project-editor-form {
  max-height: none;
  overflow-y: visible;
}

.project-editor-form .form-section {
  padding: 14px;
}

.project-editor-form .form-section + .form-section {
  margin-top: 0;
}

.project-editor-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

.project-editor-main,
.project-editor-side {
  display: contents;
}

.project-editor-form .section-title {
  margin-bottom: 12px;
}

.project-editor-form .form-grid,
.project-editor-form .points-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  column-gap: 14px;
  row-gap: 12px;
}

.project-editor-form .span-2 {
  grid-column: span 2;
}

.project-editor-form .span-full {
  grid-column: 1 / -1;
}

.project-editor-form :deep(.n-form-item-feedback-wrapper) {
  min-height: 0;
}

.form-section {
  padding: 16px 18px 4px;
  border: 1px solid #edf1f7;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.03);
}

.primary-section {
  border-color: #cfe3ff;
  background: #fbfdff;
}

.product-section {
  border-color: #d9e8ff;
  background: #fbfdff;
}

.contact-section {
  border-color: #e1e7f0;
  background: #fff;
}

.remark-section {
  border-color: #d5eadf;
  background: #fbfffd;
}

.attachment-section {
  border-color: #e1e7f0;
  background: #fcfdff;
}

.project-editor-side .section-title {
  margin-bottom: 8px;
}

.form-section + .form-section {
  margin-top: 14px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.section-title::before {
  width: 4px;
  height: 14px;
  border-radius: 999px;
  background: #2563eb;
  content: '';
}

.form-grid,
.points-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
  row-gap: 2px;
}

.project-name-field :deep(.n-input) {
  background: #fff;
}

.project-name-field :deep(.n-input__input-el) {
  font-size: 16px;
  font-weight: 600;
}

.span-2 {
  grid-column: 1 / -1;
}

.remark-timeline {
  margin-top: 4px;
}

.remark-add {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 96px;
  gap: 8px;
  align-items: flex-start;
  padding: 12px;
  border: 1px solid #d5eadf;
  border-radius: 8px;
  background: #f6fffa;
}

.remark-input :deep(.n-input) {
  background: #fff;
}

.remark-submit {
  width: 96px;
  min-height: 54px;
  align-self: stretch;
}

.remark-list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.remark-item {
  padding: 10px 12px;
  border: 1px solid #edf1f7;
  border-radius: 8px;
  background: #fbfdff;
}

.remark-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
}

.remark-content {
  color: #1f2937;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.remark-empty {
  margin-top: 10px;
  color: #94a3b8;
  font-size: 13px;
}

.attachment-section :deep(.n-upload-file-list) {
  margin-top: 6px;
}

.attachment-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.summary-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.summary-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
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

.summary-label {
  color: #6b7280;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.4;
}

.summary-item strong {
  color: #111827;
  font-size: 14px;
  line-height: 1;
}

.product-summary {
  align-items: center;
}

.product-summary-list {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.product-summary-title {
  flex: 0 0 auto;
}

.product-summary-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.08);
  font-size: 12px;
  line-height: 1.4;
}

.product-summary-name {
  overflow: hidden;
  max-width: 120px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-summary-count {
  color: #111827;
  font-size: 12px;
  font-weight: 600;
}

.product-summary-empty {
  color: #9ca3af;
  font-size: 12px;
}

.summary-item[data-tone='warning'] {
  background: #fff7ed;
}

.summary-item[data-tone='success'] {
  background: #f0fdf4;
}

.summary-item[data-tone='info'] {
  background: #eff6ff;
}

.summary-item[data-tone='error'] {
  background: #fff1f2;
}

@media (max-width: 900px) {
  .project-editor-body {
    grid-template-columns: minmax(0, 1fr);
  }

  .product-section {
    grid-column: auto;
  }
}

@media (max-width: 640px) {
  .project-modal-head {
    flex-direction: column;
  }

  .form-grid,
  .points-grid,
  .project-editor-form .form-grid,
  .project-editor-form .points-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .project-editor-form .span-2 {
    grid-column: 1 / -1;
  }

  .project-editor-form .span-full {
    grid-column: 1 / -1;
  }

  .remark-add {
    grid-template-columns: minmax(0, 1fr);
  }

  .remark-submit {
    width: 100%;
    min-height: 40px;
  }

  .product-summary {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }
}
</style>
