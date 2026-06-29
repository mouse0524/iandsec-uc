<script setup>
import { h, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NForm, NFormItem, NInput, NSelect, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import api from '@/api'

defineOptions({ name: '运维记录' })

const route = useRoute()
const $table = ref(null)
const modalVisible = ref(false)
const editingId = ref(null)
const projectOptions = ref([])
const activityTypeOptions = ref([])
const summary = ref({ total: 0, pending: 0, processing: 0, done: 0 })
const statusOptions = [
  { label: '待处理', value: '待处理' },
  { label: '处理中', value: '处理中' },
  { label: '已完成', value: '已完成' },
]
const queryItems = ref({
  project_id: route.query.project_id ? Number(route.query.project_id) : undefined,
})
const form = ref(defaultForm())

watch(
  () => route.query,
  (query) => {
    queryItems.value = { ...queryItems.value, project_id: query.project_id ? Number(query.project_id) : undefined }
    $table.value?.handleSearch()
  },
)

onMounted(async () => {
  await loadOptions()
  $table.value?.handleSearch()
})

function defaultForm() {
  return {
    project_id: queryItems.value.project_id || null,
    activity_type: null,
    title: '',
    content: '',
    status: '待处理',
    operator_id: null,
  }
}

async function loadOptions() {
  const [configRes, projectRes] = await Promise.all([
    api.getPublicConfig(),
    api.projectList({ page: 1, page_size: 9999 }),
  ])
  const types = configRes?.data?.project_activity_types?.length
    ? configRes.data.project_activity_types
    : ['迁移库', '重做系统', '运维', '其他']
  activityTypeOptions.value = types.map((item) => ({ label: item, value: item }))
  projectOptions.value = (projectRes?.data || []).map((item) => ({ label: item.project_name, value: item.id }))
}

async function getActivityList(params) {
  const res = await api.projectActivityList(params)
  summary.value = res?.summary || { total: 0, pending: 0, processing: 0, done: 0 }
  return res
}

function openCreate() {
  editingId.value = null
  form.value = { ...defaultForm(), activity_type: activityTypeOptions.value[0]?.value }
  modalVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.value = { ...defaultForm(), ...row }
  modalVisible.value = true
}

async function submitActivity() {
  if (!form.value.project_id || !form.value.activity_type || !form.value.title?.trim()) {
    $message.warning('请选择项目、运维类型并填写标题')
    return
  }
  if (editingId.value) {
    await api.projectActivityUpdate({ ...form.value, activity_id: editingId.value })
    $message.success('运维记录已更新')
  } else {
    await api.projectActivityCreate(form.value)
    $message.success('运维记录已创建')
  }
  modalVisible.value = false
  $table.value?.handleSearch()
}

const columns = [
  { title: '项目', key: 'project_name', align: 'center', width: 180 },
  { title: '运维类型', key: 'activity_type', align: 'center', width: 120 },
  { title: '标题', key: 'title', align: 'center', minWidth: 180 },
  {
    title: '状态',
    key: 'status',
    align: 'center',
    width: 110,
    render(row) {
      const type = row.status === '已完成' ? 'success' : row.status === '处理中' ? 'info' : 'warning'
      return h(NTag, { type, bordered: false }, { default: () => row.status })
    },
  },
  { title: '处理人', key: 'operator_name', align: 'center', width: 120, render: (row) => row.operator_name || '-' },
  { title: '开始时间', key: 'started_at', align: 'center', width: 170, render: (row) => row.started_at || '-' },
  { title: '完成时间', key: 'finished_at', align: 'center', width: 170, render: (row) => row.finished_at || '-' },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    fixed: 'right',
    width: 90,
    render(row) {
      return h(NButton, { size: 'small', type: 'primary', text: true, onClick: () => openEdit(row) }, { default: () => '编辑' })
    },
  },
]
</script>

<template>
  <CommonPage title="运维记录">
    <div class="summary-grid">
      <div class="summary-card">
        <span>运维总数</span>
        <strong>{{ summary.total || 0 }}</strong>
      </div>
      <div class="summary-card" data-tone="warning">
        <span>待处理</span>
        <strong>{{ summary.pending || 0 }}</strong>
      </div>
      <div class="summary-card" data-tone="info">
        <span>处理中</span>
        <strong>{{ summary.processing || 0 }}</strong>
      </div>
      <div class="summary-card" data-tone="success">
        <span>已完成</span>
        <strong>{{ summary.done || 0 }}</strong>
      </div>
    </div>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="getActivityList"
      :scroll-x="1160"
    >
      <template #queryBar>
        <QueryBarItem label="项目" :label-width="40">
          <NSelect v-model:value="queryItems.project_id" :options="projectOptions" clearable filterable style="width: 220px" />
        </QueryBarItem>
        <QueryBarItem label="类型" :label-width="40">
          <NSelect v-model:value="queryItems.activity_type" :options="activityTypeOptions" clearable style="width: 160px" />
        </QueryBarItem>
        <QueryBarItem label="状态" :label-width="40">
          <NSelect v-model:value="queryItems.status" :options="statusOptions" clearable style="width: 140px" />
        </QueryBarItem>
        <QueryBarItem label="" :label-width="0">
          <NButton type="primary" @click="openCreate">新增运维</NButton>
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      :title="editingId ? '编辑运维' : '新增运维'"
      @save="submitActivity"
    >
      <NForm label-placement="left" label-align="left" :label-width="80">
        <NFormItem label="项目"><NSelect v-model:value="form.project_id" :options="projectOptions" filterable /></NFormItem>
        <NFormItem label="运维类型"><NSelect v-model:value="form.activity_type" :options="activityTypeOptions" /></NFormItem>
        <NFormItem label="标题"><NInput v-model:value="form.title" /></NFormItem>
        <NFormItem label="状态"><NSelect v-model:value="form.status" :options="statusOptions" /></NFormItem>
        <NFormItem label="内容"><NInput v-model:value="form.content" type="textarea" :autosize="{ minRows: 4, maxRows: 8 }" /></NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>

<style scoped>
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
