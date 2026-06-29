<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NDatePicker, NForm, NFormItem, NInput, NInputNumber, NSelect } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import api from '@/api'

defineOptions({ name: '项目列表' })

const router = useRouter()
const $table = ref(null)
const modalVisible = ref(false)
const editingId = ref(null)
const readonly = ref(false)
const queryItems = ref({})
const productOptions = ref([])
const statusOptions = ref([])
const regionOptions = ref([])
const userOptions = ref([])
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
    server_version: '',
    client_version: '',
    start_time: null,
    end_time: null,
    customer_contact: '',
    customer_phone: '',
    customer_email: '',
    status: null,
    assignee_id: null,
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
  productOptions.value = products.map((item) => ({ label: item, value: item }))
  statusOptions.value = statuses.map((item) => ({ label: item, value: item }))
  regionOptions.value = regions.map((item) => ({ label: item, value: item }))
  userOptions.value = (userRes?.data || [])
    .filter((item) => item.is_active !== false)
    .filter((item) => Array.isArray(item.roles) && item.roles.some((role) => role?.name === '技术'))
    .map((item) => ({ label: item.alias || item.username, value: item.id }))
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

function openCreate() {
  editingId.value = null
  readonly.value = false
  form.value = {
    ...defaultForm(),
    product_points: productOptions.value[0]?.value ? [{ product_name: productOptions.value[0].value, points: 0 }] : [],
    region: regionOptions.value[0]?.value || null,
    status: statusOptions.value[0]?.value,
  }
  modalVisible.value = true
}

function openProject(row, isReadonly) {
  editingId.value = row.id
  readonly.value = isReadonly
  form.value = {
    ...defaultForm(),
    ...row,
    start_time: row.start_time ? Date.parse(row.start_time) : null,
    end_time: row.end_time ? Date.parse(row.end_time) : null,
  }
  modalVisible.value = true
}

function openDetail(row) {
  openProject(row, true)
}

function openEdit(row) {
  openProject(row, false)
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

function jumpTickets(row, issueType) {
  router.push({ path: '/ticket/my', query: { company_name: row.project_name, issue_type: issueType } })
}

function jumpActivities(row) {
  router.push({ path: '/project/activity', query: { project_id: row.id } })
}

const columns = [
  { title: '区域', key: 'region', align: 'center', width: 90, render: (row) => row.region || '-' },
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
  { title: '状态', key: 'status', align: 'center', width: 110, render: (row) => row.status || '-' },
  { title: '负责人', key: 'assignee_name', align: 'center', width: 120, render: (row) => row.assignee_name || '-' },
  {
    title: '问题单',
    key: 'issue_count',
    align: 'center',
    width: 90,
    render(row) {
      return h(NButton, { text: true, type: 'primary', onClick: () => jumpTickets(row, '现网问题') }, { default: () => row.issue_count || 0 })
    },
  },
  {
    title: '需求单',
    key: 'requirement_count',
    align: 'center',
    width: 90,
    render(row) {
      return h(NButton, { text: true, type: 'primary', onClick: () => jumpTickets(row, '现网需求') }, { default: () => row.requirement_count || 0 })
    },
  },
  {
    title: '运维单',
    key: 'activity_count',
    align: 'center',
    width: 90,
    render(row) {
      return h(NButton, { text: true, type: 'primary', onClick: () => jumpActivities(row) }, { default: () => row.activity_count || 0 })
    },
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    fixed: 'right',
    width: 150,
    render(row) {
      return h('div', { class: 'actions' }, [
        h(NButton, { size: 'small', type: 'info', ghost: true, onClick: () => openDetail(row) }, { default: () => '详情' }),
        h(NButton, { size: 'small', type: 'primary', ghost: true, onClick: () => openEdit(row) }, { default: () => '编辑' }),
      ])
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
      :scroll-x="1600"
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
      <NForm class="project-form" label-placement="top">
        <div class="form-section">
          <div class="section-title">基础信息</div>
          <div class="form-grid">
            <NFormItem label="项目名称" class="span-2"><NInput v-model:value="form.project_name" :disabled="readonly" /></NFormItem>
            <NFormItem label="区域"><NSelect v-model:value="form.region" :options="regionOptions" clearable :disabled="readonly" /></NFormItem>
            <NFormItem label="项目状态"><NSelect v-model:value="form.status" :options="statusOptions" :disabled="readonly" /></NFormItem>
            <NFormItem label="服务器版本"><NInput v-model:value="form.server_version" :disabled="readonly" /></NFormItem>
            <NFormItem label="客户端版本"><NInput v-model:value="form.client_version" :disabled="readonly" /></NFormItem>
            <NFormItem label="开始时间"><NDatePicker v-model:value="form.start_time" type="date" clearable style="width: 100%" :disabled="readonly" /></NFormItem>
            <NFormItem label="结束时间"><NDatePicker v-model:value="form.end_time" type="date" clearable style="width: 100%" :disabled="readonly" /></NFormItem>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title">产品点数</div>
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
          <div class="section-title">对接信息</div>
          <div class="form-grid">
            <NFormItem label="负责人"><NSelect v-model:value="form.assignee_id" :options="userOptions" clearable filterable :disabled="readonly" /></NFormItem>
            <NFormItem label="客户对接人"><NInput v-model:value="form.customer_contact" :disabled="readonly" /></NFormItem>
            <NFormItem label="联系电话"><NInput v-model:value="form.customer_phone" :disabled="readonly" /></NFormItem>
            <NFormItem label="联系邮箱"><NInput v-model:value="form.customer_email" :disabled="readonly" /></NFormItem>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title">备注</div>
          <NFormItem label="备注">
            <NInput v-model:value="form.remark" type="textarea" :autosize="{ minRows: 3, maxRows: 5 }" :disabled="readonly" />
          </NFormItem>
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

.project-form {
  max-height: 68vh;
  overflow-y: auto;
  padding-right: 4px;
}

.form-section + .form-section {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #eef0f4;
}

.section-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.form-grid,
.points-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
}

.span-2 {
  grid-column: 1 / -1;
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
