<script setup>
import { computed, h, onMounted, ref } from 'vue'
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
import TicketDetailModal from '@/views/ticket/components/TicketDetailModal.vue'
import { ticketStatusTextMap, ticketStatusTypeMap } from '@/views/ticket/components/ticket-meta'
import api from '@/api'

defineOptions({ name: '项目列表' })

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
const fileList = ref([])
const workOrderVisible = ref(false)
const workOrderProject = ref(null)
const activeWorkOrderTab = ref('issues')
const workOrderLoading = ref(false)
const workOrders = ref({ issues: [], requirements: [], activities: [] })
const workOrderTotals = ref({ issues: 0, requirements: 0, activities: 0 })
const workOrderPages = ref({ issues: 1, requirements: 1, activities: 1 })
const workOrderPageSize = 10
const ticketDetailVisible = ref(false)
const ticketDetailLoading = ref(false)
const currentTicket = ref({})
const activityDetailVisible = ref(false)
const currentActivity = ref({})
const defaultSummary = { total: 0, presale: 0, pending: 0, implementing: 0, pending_acceptance: 0, accepted: 0, lost: 0 }
const summary = ref({ ...defaultSummary })
const form = ref(defaultForm())

onMounted(async () => {
  await loadOptions()
  $table.value?.handleSearch()
})

function defaultForm() {
  return {
    project_name: '',
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
    status: null,
    assignee_id: null,
    attachment_ids: [],
    remark: '',
  }
}

async function loadOptions() {
  const [configRes, userRes] = await Promise.all([
    api.getPublicConfig(),
    api.getUserList({ page: 1, page_size: 9999 }),
  ])
  const config = configRes?.data || {}
  const products = config.project_products?.length ? config.project_products : ['安得卫士']
  const statuses = config.project_statuses?.length
    ? config.project_statuses
    : ['售前', '待实施', '实施中', '待验收', '已验收', '丢单']
  const regions = config.project_regions?.length ? config.project_regions : ['华东', '华南', '华北', '华中', '西南', '西北']
  const serverVersions = config.project_server_versions?.length ? config.project_server_versions : ['5.6.1']
  const clientVersions = config.project_client_versions?.length ? config.project_client_versions : ['2.25']
  productOptions.value = products.map((item) => ({ label: item, value: item }))
  statusOptions.value = statuses.map((item) => ({ label: item, value: item }))
  regionOptions.value = regions.map((item) => ({ label: item, value: item }))
  serverVersionOptions.value = serverVersions.map((item) => ({ label: item, value: item }))
  clientVersionOptions.value = clientVersions.map((item) => ({ label: item, value: item }))
  userOptions.value = (userRes?.data || [])
    .filter((item) => item.is_active !== false)
    .filter((item) => Array.isArray(item.roles) && item.roles.some((role) => role?.name === '技术'))
    .map((item) => ({ label: item.alias || item.username, value: item.id }))
  agentOptions.value = (userRes?.data || [])
    .filter((item) => item.is_active !== false)
    .filter((item) => Array.isArray(item.roles) && item.roles.some((role) => ['代理商', '渠道商'].includes(role?.name)))
    .map((item) => ({ label: item.company_name || item.alias || item.username, value: item.id }))
}

async function getProjectList(params) {
  const res = await api.projectList(params)
  summary.value = res?.summary || { ...defaultSummary }
  return res
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

function formatDate(value) {
  return value ? String(value).slice(0, 10) : '-'
}

function openCreate() {
  editingId.value = null
  readonly.value = false
  form.value = {
    ...defaultForm(),
    product_points: productOptions.value[0]?.value ? [{ product_name: productOptions.value[0].value, points: 0 }] : [],
    region: regionOptions.value[0]?.value || null,
    status: statusOptions.value[0]?.value,
  }
  fileList.value = []
  modalVisible.value = true
}

function openProject(row, isReadonly) {
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

async function openTicketDetail(row) {
  currentTicket.value = row
  ticketDetailVisible.value = true
  ticketDetailLoading.value = true
  try {
    const res = await api.getTicketById({ ticket_id: row.id })
    if (currentTicket.value?.id === row.id) currentTicket.value = res.data
  } finally {
    ticketDetailLoading.value = false
  }
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
]

const columns = [
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
  { title: '服务器版本', key: 'server_version', align: 'center', width: 130, render: (row) => row.server_version || '-' },
  { title: '客户端版本', key: 'client_version', align: 'center', width: 130, render: (row) => row.client_version || '-' },
  { title: '客户对接人', key: 'customer_contact', align: 'center', width: 130 },
  { title: '维保时间', key: 'maintenance_time', align: 'center', width: 120, render: (row) => formatDate(row.maintenance_time) },
  { title: '状态', key: 'status', align: 'center', width: 110, render: (row) => row.status || '-' },
  { title: '负责人', key: 'assignee_name', align: 'center', width: 120, render: (row) => row.assignee_name || '-' },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    fixed: 'right',
    width: 190,
    render(row) {
      return [
        h(NButton, { size: 'small', type: 'primary', text: true, onClick: () => openDetail(row) }, { default: () => '详情' }),
        h(NButton, { size: 'small', type: 'warning', text: true, style: 'margin-left: 10px', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: 'info', text: true, style: 'margin-left: 10px', onClick: () => openWorkOrders(row) }, { default: () => '工单' }),
      ]
    },
  },
]
</script>

<template>
  <CommonPage title="项目管理">
    <div class="summary-grid">
      <div class="summary-card">
        <span>项目总数</span>
        <strong>{{ summary.total || 0 }}</strong>
      </div>
      <div class="summary-card" data-tone="warning">
        <span>售前</span>
        <strong>{{ summary.presale || 0 }}</strong>
      </div>
      <div class="summary-card" data-tone="warning">
        <span>待实施</span>
        <strong>{{ summary.pending || 0 }}</strong>
      </div>
      <div class="summary-card" data-tone="info">
        <span>实施中</span>
        <strong>{{ summary.implementing || 0 }}</strong>
      </div>
      <div class="summary-card" data-tone="info">
        <span>待验收</span>
        <strong>{{ summary.pending_acceptance || 0 }}</strong>
      </div>
      <div class="summary-card" data-tone="success">
        <span>已验收</span>
        <strong>{{ summary.accepted || 0 }}</strong>
      </div>
      <div class="summary-card" data-tone="error">
        <span>丢单</span>
        <strong>{{ summary.lost || 0 }}</strong>
      </div>
    </div>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="getProjectList"
      :scroll-x="1870"
    >
      <template #queryBar>
        <QueryBarItem label="项目名称" :label-width="64">
          <NInput v-model:value="queryItems.project_name" clearable placeholder="输入项目名称" />
        </QueryBarItem>
        <QueryBarItem label="状态" :label-width="40">
          <NSelect v-model:value="queryItems.status" :options="statusOptions" clearable style="width: 160px" />
        </QueryBarItem>
        <QueryBarItem label="区域" :label-width="40">
          <NSelect v-model:value="queryItems.region" :options="regionOptions" clearable style="width: 140px" />
        </QueryBarItem>
        <QueryBarItem label="所属代理商" :label-width="72">
          <NSelect v-model:value="queryItems.agent_id" :options="agentOptions" clearable filterable style="width: 180px" />
        </QueryBarItem>
        <QueryBarItem label="负责人" :label-width="48">
          <NSelect v-model:value="queryItems.assignee_id" :options="userOptions" clearable filterable style="width: 160px" />
        </QueryBarItem>
        <QueryBarItem label="" :label-width="0">
          <NButton type="primary" @click="openCreate">新增项目</NButton>
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      :title="readonly ? '项目详情' : editingId ? '编辑项目' : '新增项目'"
      width="760px"
      :show-footer="!readonly"
      @save="submitProject"
    >
      <div class="project-modal-head">
        <div>
          <div class="modal-eyebrow">{{ readonly ? 'PROJECT DETAIL' : editingId ? 'PROJECT EDIT' : 'PROJECT CREATE' }}</div>
          <div class="modal-project-name">{{ form.project_name || '未命名项目' }}</div>
        </div>
        <div class="modal-tags">
          <NTag v-if="form.region" size="small" round>{{ form.region }}</NTag>
          <NTag v-if="form.status" size="small" round type="info">{{ form.status }}</NTag>
        </div>
      </div>
      <NForm class="project-form" label-placement="top">
        <div class="form-section">
          <div class="section-title"><span>基础信息</span></div>
          <div class="form-grid">
            <NFormItem label="项目名称" class="span-2"><NInput v-model:value="form.project_name" :disabled="readonly" /></NFormItem>
            <NFormItem label="区域"><NSelect v-model:value="form.region" :options="regionOptions" clearable :disabled="readonly" /></NFormItem>
            <NFormItem label="所属代理商"><NSelect v-model:value="form.agent_id" :options="agentOptions" clearable filterable :disabled="readonly" /></NFormItem>
            <NFormItem label="项目状态"><NSelect v-model:value="form.status" :options="statusOptions" :disabled="readonly" /></NFormItem>
            <NFormItem label="服务器版本"><NSelect v-model:value="form.server_version" :options="serverVersionOptions" clearable filterable :disabled="readonly" /></NFormItem>
            <NFormItem label="客户端版本"><NSelect v-model:value="form.client_version" :options="clientVersionOptions" clearable filterable :disabled="readonly" /></NFormItem>
            <NFormItem label="开始时间"><NDatePicker v-model:value="form.start_time" type="date" clearable style="width: 100%" :disabled="readonly" /></NFormItem>
            <NFormItem label="结束时间"><NDatePicker v-model:value="form.end_time" type="date" clearable style="width: 100%" :disabled="readonly" /></NFormItem>
            <NFormItem label="维保时间"><NDatePicker v-model:value="form.maintenance_time" type="date" clearable style="width: 100%" :disabled="readonly" /></NFormItem>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title"><span>产品点数</span></div>
          <NFormItem label="使用产品">
            <NSelect v-model:value="selectedProducts" :options="productOptions" multiple clearable :disabled="readonly" />
          </NFormItem>
          <div v-if="form.product_points.length" class="points-grid">
            <NFormItem v-for="item in form.product_points" :key="item.product_name" :label="`${item.product_name}点数`">
              <NInputNumber v-model:value="item.points" :min="0" style="width: 100%" :disabled="readonly" />
            </NFormItem>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title"><span>对接信息</span></div>
          <div class="form-grid">
            <NFormItem label="负责人"><NSelect v-model:value="form.assignee_id" :options="userOptions" clearable filterable :disabled="readonly" /></NFormItem>
            <NFormItem label="客户对接人"><NInput v-model:value="form.customer_contact" :disabled="readonly" /></NFormItem>
            <NFormItem label="联系电话"><NInput v-model:value="form.customer_phone" :disabled="readonly" /></NFormItem>
            <NFormItem label="联系邮箱"><NInput v-model:value="form.customer_email" :disabled="readonly" /></NFormItem>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title"><span>备注</span></div>
          <NFormItem label="备注">
            <NInput v-model:value="form.remark" type="textarea" :autosize="{ minRows: 3, maxRows: 5 }" :disabled="readonly" />
          </NFormItem>
        </div>

        <div class="form-section">
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
          <NTabPane name="activities" :tab="`运维单 (${workOrderTotals.activities})`">
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

    <TicketDetailModal v-model:visible="ticketDetailVisible" :ticket="currentTicket" :loading="ticketDetailLoading" />

    <CrudModal v-model:visible="activityDetailVisible" title="运维详情" :show-footer="false" width="640px">
      <div class="activity-detail">
        <div><span>标题</span><strong>{{ currentActivity.title || '-' }}</strong></div>
        <div><span>运维类型</span><strong>{{ currentActivity.activity_type || '-' }}</strong></div>
        <div><span>处理人</span><strong>{{ currentActivity.operator_name || '-' }}</strong></div>
        <div><span>处理时间</span><strong>{{ currentActivity.started_at || '-' }}</strong></div>
        <div class="span-2"><span>内容</span><p>{{ currentActivity.content || '-' }}</p></div>
      </div>
    </CrudModal>
  </CommonPage>
</template>

<style scoped>
.actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.project-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin: -4px 0 18px;
  padding: 16px 18px;
  border: 1px solid #e6edf7;
  border-radius: 8px;
  background: linear-gradient(135deg, #f7fbff 0%, #ffffff 58%, #f7fff9 100%);
}

.modal-eyebrow {
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
  line-height: 1;
}

.modal-project-name {
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.3;
}

.modal-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  max-width: 220px;
}

.project-form {
  max-height: 68vh;
  overflow-y: auto;
  padding: 0 4px 2px 0;
}

.form-section {
  padding: 14px 16px 2px;
  border: 1px solid #edf1f7;
  border-radius: 8px;
  background: #fff;
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
  background: #18a058;
  content: '';
}

.form-grid,
.points-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
  row-gap: 2px;
}

.span-2 {
  grid-column: 1 / -1;
}

.activity-detail {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 18px;
}

.activity-detail span {
  display: block;
  margin-bottom: 6px;
  color: #6b7280;
}

.activity-detail strong,
.activity-detail p {
  margin: 0;
  color: #111827;
  white-space: pre-wrap;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.summary-card {
  min-width: 0;
  padding: 14px 16px;
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

.summary-card[data-tone='success'] {
  background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%);
}

.summary-card[data-tone='info'] {
  background: linear-gradient(180deg, #f3f8ff 0%, #ffffff 100%);
}

.summary-card[data-tone='error'] {
  background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%);
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
