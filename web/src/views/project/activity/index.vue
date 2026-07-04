<script setup>
import { h, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NDatePicker, NForm, NFormItem, NInput, NPopconfirm, NSelect, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import { useUserStore } from '@/store'
import api from '@/api'

defineOptions({ name: '运维记录' })

const route = useRoute()
const userStore = useUserStore()
const $table = ref(null)
const modalVisible = ref(false)
const editingId = ref(null)
const readonly = ref(false)
const projectOptions = ref([])
const activityTypeOptions = ref(['迁移库', '重做系统', '运维', '其他'].map((item) => ({ label: item, value: item })))
const userOptions = ref([])
let activityTypesPromise = null
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
    started_at: null,
  }
}

function loadActivityTypes() {
  if (!activityTypesPromise) {
    activityTypesPromise = api.getAppConfig().then((res) => {
      const types = res?.data?.project_activity_types?.length
        ? res.data.project_activity_types
        : activityTypeOptions.value.map((item) => item.value)
      activityTypeOptions.value = types.map((item) => ({ label: item, value: item }))
    })
  }
  return activityTypesPromise
}

function loadProjectOptions(keyword = '') {
  return api.projectList({ page: 1, page_size: 10, project_name: keyword || undefined }).then((res) => {
    projectOptions.value = (res?.data || []).map((item) => ({ label: item.project_name, value: item.id }))
  })
}

function loadUserOptions(keyword = '') {
  return api.getUserList({ page: 1, page_size: 10, alias: keyword || undefined }).then((res) => {
    userOptions.value = (res?.data || [])
      .filter((item) => item.is_active !== false)
      .filter((item) => Array.isArray(item.roles) && item.roles.some((role) => role?.name === '技术'))
      .map((item) => ({ label: item.alias || item.username, value: item.id, username: item.username }))
  })
}

function ensureFormOptions() {
  return Promise.all([loadActivityTypes(), loadProjectOptions(), loadUserOptions()])
}

function seedRowOptions(row) {
  if (row.project_id && row.project_name && !projectOptions.value.some((item) => item.value === row.project_id)) {
    projectOptions.value = [...projectOptions.value, { label: row.project_name, value: row.project_id }]
  }
  if (row.operator_id && row.operator_name && !userOptions.value.some((item) => item.value === row.operator_id)) {
    userOptions.value = [...userOptions.value, { label: row.operator_name, value: row.operator_id }]
  }
}

async function getActivityList(params) {
  const res = await api.projectActivityList(params)
  return res
}

function openCreate() {
  editingId.value = null
  readonly.value = false
  form.value = {
    ...defaultForm(),
    activity_type: activityTypeOptions.value[0]?.value,
    operator_id: userStore.userId || null,
    started_at: Date.now(),
  }
  modalVisible.value = true
  ensureFormOptions()
}

function openDetail(row) {
  seedRowOptions(row)
  editingId.value = row.id
  readonly.value = true
  form.value = { ...defaultForm(), ...row, started_at: row.started_at ? Date.parse(row.started_at) : null }
  modalVisible.value = true
}

function openEdit(row) {
  seedRowOptions(row)
  editingId.value = row.id
  readonly.value = false
  form.value = { ...defaultForm(), ...row, started_at: row.started_at ? Date.parse(row.started_at) : null }
  modalVisible.value = true
  ensureFormOptions()
}

async function submitActivity() {
  if (!form.value.project_id || !form.value.activity_type || !form.value.title?.trim()) {
    $message.warning('请选择项目、运维类型并填写标题')
    return
  }
  const payload = {
    ...form.value,
    started_at: form.value.started_at ? new Date(form.value.started_at).toISOString() : null,
  }
  delete payload.finished_at
  if (editingId.value) {
    await api.projectActivityUpdate({ ...payload, activity_id: editingId.value })
    $message.success('运维记录已更新')
  } else {
    await api.projectActivityCreate(payload)
    $message.success('运维记录已创建')
  }
  modalVisible.value = false
  $table.value?.handleSearch()
}

async function deleteActivity(row) {
  await api.projectActivityDelete({ activity_id: row.id })
  $message.success('运维记录已删除')
  $table.value?.handleSearch()
}

const columns = [
  { title: '项目', key: 'project_name', align: 'center', width: 180 },
  { title: '运维类型', key: 'activity_type', align: 'center', width: 120 },
  {
    title: '标题',
    key: 'title',
    align: 'center',
    minWidth: 180,
    render: (row) => h(NButton, { text: true, type: 'primary', onClick: () => openDetail(row) }, { default: () => row.title || '-' }),
  },
  { title: '处理人', key: 'operator_name', align: 'center', width: 120, render: (row) => row.operator_name || '-' },
  { title: '处理时间', key: 'started_at', align: 'center', width: 170, render: (row) => row.started_at || '-' },
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
        h(
          NPopconfirm,
          { onPositiveClick: () => deleteActivity(row) },
          {
            trigger: () => h(NButton, { size: 'small', type: 'error', text: true, style: 'margin-left: 10px' }, { default: () => '删除' }),
            default: () => '删除后不可恢复，是否继续？',
          }
        ),
      ]
    },
  },
]
</script>

<template>
  <CommonPage title="运维记录">
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="getActivityList"
      :scroll-x="1160"
    >
      <template #queryBar>
        <QueryBarItem label="项目" :label-width="40">
          <NSelect
            v-model:value="queryItems.project_id"
            :options="projectOptions"
            clearable
            filterable
            remote
            style="width: 220px"
            @focus="loadProjectOptions"
            @search="loadProjectOptions"
          />
        </QueryBarItem>
        <QueryBarItem label="类型" :label-width="40">
          <NSelect v-model:value="queryItems.activity_type" :options="activityTypeOptions" clearable style="width: 160px" @focus="loadActivityTypes" />
        </QueryBarItem>
        <QueryBarItem label="处理人" :label-width="52">
          <NSelect
            v-model:value="queryItems.operator_id"
            :options="userOptions"
            clearable
            filterable
            remote
            style="width: 160px"
            @focus="loadUserOptions"
            @search="loadUserOptions"
          />
        </QueryBarItem>
        <QueryBarItem label="" :label-width="0">
          <NButton type="primary" @click="openCreate">新增运维</NButton>
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      :title="readonly ? '运维详情' : editingId ? '编辑运维' : '新增运维'"
      :show-footer="!readonly"
      width="760px"
      @save="submitActivity"
    >
      <div class="activity-modal-head">
        <div>
          <div class="modal-eyebrow">{{ readonly ? 'OPS DETAIL' : editingId ? 'OPS EDIT' : 'OPS CREATE' }}</div>
          <div class="modal-activity-name">{{ form.title || '未命名运维' }}</div>
        </div>
        <div class="modal-tags">
          <NTag v-if="form.activity_type" size="small" round type="info">{{ form.activity_type }}</NTag>
        </div>
      </div>
      <NForm class="activity-form" label-placement="top">
        <div class="form-section">
          <div class="section-title"><span>基础信息</span></div>
          <div class="form-grid">
            <NFormItem label="项目"><NSelect v-model:value="form.project_id" :options="projectOptions" :disabled="readonly" filterable remote @focus="loadProjectOptions" @search="loadProjectOptions" /></NFormItem>
            <NFormItem label="运维类型"><NSelect v-model:value="form.activity_type" :options="activityTypeOptions" :disabled="readonly" /></NFormItem>
            <NFormItem label="标题" class="span-2"><NInput v-model:value="form.title" :disabled="readonly" /></NFormItem>
          </div>
        </div>
        <div class="form-section">
          <div class="section-title"><span>处理信息</span></div>
          <div class="form-grid">
            <NFormItem label="处理人"><NSelect v-model:value="form.operator_id" :options="userOptions" :disabled="readonly" clearable filterable remote @focus="loadUserOptions" @search="loadUserOptions" /></NFormItem>
            <NFormItem label="处理时间"><NDatePicker v-model:value="form.started_at" type="datetime" :disabled="readonly" clearable style="width: 100%" /></NFormItem>
          </div>
        </div>
        <div class="form-section">
          <div class="section-title"><span>运维内容</span></div>
          <NFormItem label="内容"><NInput v-model:value="form.content" type="textarea" :disabled="readonly" :autosize="{ minRows: 4, maxRows: 8 }" /></NFormItem>
        </div>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>

<style scoped>
.activity-modal-head {
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

.modal-activity-name {
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

.activity-form {
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

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
  row-gap: 2px;
}

.span-2 {
  grid-column: 1 / -1;
}

</style>

