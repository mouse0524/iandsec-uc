<script setup>
import { computed, h, nextTick, onMounted, ref } from 'vue'
import {
  NButton,
  NCheckbox,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NTag,
  NUpload,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import RichTextEditor from '@/components/editor/RichTextEditor.vue'
import IssueDetail from '@/views/issue/detail/index.vue'
import api from '@/api'
import { useAppStore, useUserStore } from '@/store'
import { formatDateTime, isImageName } from '@/utils'

defineOptions({ name: '工单列表' })

const $table = ref(null)
const formRef = ref(null)
const appStore = useAppStore()
const userStore = useUserStore()
const queryItems = ref(defaultQueryFilters())
const metadata = ref({ trackers: [], statuses: [], priorities: [], custom_fields: [] })
const queries = ref([])
const selectedQueryId = ref(null)
const showCreateModal = ref(false)
const showQueryModal = ref(false)
const creating = ref(false)
const savingQuery = ref(false)
const queryName = ref('')
const createForm = ref(defaultCreateForm())
const assigneeOptions = ref([])
const uploadLoading = ref(false)
const uploadedAttachmentIds = ref([])
const uploadFileList = ref([])
const attachmentAccept = ref('.zip,.rar,.png,.jpg,.jpeg,.gif,.docx,.pptx,.xlsx')
const detailVisible = ref(false)
const detailIssueId = ref(null)
const detailIssueProjectName = ref('')
const projectPhaseOptions = ref([
  { label: '售前', value: '售前' },
  { label: '实施', value: '实施' },
  { label: '售后', value: '售后' },
])
const issueTypeOptions = ref([
  { label: '现网问题', value: '现网问题' },
  { label: '现网需求', value: '现网需求' },
])
const impactScopeOptions = ref([
  { label: '全部', value: '全部' },
  { label: '偶现', value: '偶现' },
  { label: '单台必现', value: '单台必现' },
  { label: '单台偶现', value: '单台偶现' },
])
const categoryOptions = ref([
  { label: '登录问题', value: '登录问题' },
  { label: '权限问题', value: '权限问题' },
  { label: '系统异常', value: '系统异常' },
  { label: '其他', value: '其他' },
])
const descriptionTemplateOptions = ref([])

const detailDrawerTitle = computed(() =>
  detailIssueId.value
    ? `工单 #${detailIssueId.value}${detailIssueProjectName.value ? ` ${detailIssueProjectName.value}` : ''}`
    : '工单详情',
)
const customFields = computed(() => metadata.value.custom_fields || [])
const customFilterFields = computed(() => customFields.value.filter((item) => item.is_filter))
const tableScrollX = computed(() => 1020 + customFields.value.length * 140)
const builtInQueries = computed(() => {
  const userId = Number(userStore.userId || 0)
  return [
    {
      label: '我提交',
      value: 'builtin:submitted-by-me',
      filters: userId ? { submitter_id: userId } : {},
    },
    {
      label: '指派给我',
      value: 'builtin:assigned-to-me',
      filters: userId ? { assigned_to_id: userId } : {},
    },
  ]
})
const queryOptions = computed(() => [
  ...builtInQueries.value,
  ...queries.value.map((item) => ({ label: item.name, value: item.id })),
])

const createRules = {
  company_name: { required: true, message: '请输入项目名称', trigger: ['blur', 'input'] },
  project_phase: { required: true, message: '请选择项目阶段', trigger: ['change'] },
  issue_type: { required: true, message: '请选择跟踪', trigger: ['change'] },
  impact_scope: { required: true, message: '请选择影响范围', trigger: ['change'] },
  category: { required: true, message: '请选择问题分类', trigger: ['change'] },
  issue_priority_id: {
    required: true,
    type: 'number',
    message: '请选择优先级',
    trigger: ['change'],
  },
  title: { required: true, message: '请输入标题', trigger: ['blur', 'input'] },
  description: {
    validator: () => (hasRichText(createForm.value.description) ? true : new Error('请输入描述')),
    trigger: ['blur', 'input'],
  },
}

onMounted(async () => {
  if (!userStore.userId) await userStore.getUserInfo()
  queryItems.value = defaultQueryFilters()
  selectedQueryId.value = defaultQueryId()
  loadMetadata()
  loadQueries()
  loadIssueCreateConfig()
  loadAssigneeOptions()
  fetchPrefill()
  await nextTick()
  $table.value?.handleSearch?.()
})

function getIssueList(params) {
  const { filters, customValues } = splitListParams(params)
  const queryId = savedQueryId(selectedQueryId.value)
  return api.getIssueList({
    ...filters,
    custom_values: Object.keys(customValues).length ? JSON.stringify(customValues) : undefined,
    query_id: queryId || undefined,
  })
}

async function loadMetadata() {
  const res = await api.getIssueMetadata()
  metadata.value = res?.data || { trackers: [], statuses: [], priorities: [], custom_fields: [] }
  if (metadata.value.trackers?.length) {
    issueTypeOptions.value = metadata.value.trackers.map((item) => ({
      label: item.name,
      value: item.name,
    }))
  }
  ensureCreateDefaults()
}

async function loadQueries() {
  const res = await api.getIssueQueries()
  queries.value = res?.data || []
}

function optionList(key) {
  return (metadata.value[key] || []).map((item) => ({ label: item.name, value: item.id }))
}

function displayName(row, nameKey, idKey) {
  return row[nameKey] || row[idKey] || '-'
}

function statusTagType(row) {
  if (row.status_is_closed) return 'success'
  const text = String(row.status_name || '')
  if (/拒绝|驳回|失败|异常/.test(text)) return 'error'
  if (/处理中|开发|测试|评估|审核|进行/.test(text)) return 'info'
  if (/待|新建|未/.test(text)) return 'warning'
  return 'default'
}

function priorityTagType(value) {
  const text = String(value || '')
  if (/紧急|立刻|最高|严重|阻塞/.test(text)) return 'error'
  if (/高|重要/.test(text)) return 'warning'
  if (/低|轻微|计划/.test(text)) return 'success'
  return 'info'
}

function renderTag(label, type = 'default') {
  return h(NTag, { size: 'small', type, bordered: false }, { default: () => label || '-' })
}

function renderIssueTitle(row) {
  const meta = [
    row.company_name ? h('span', { title: row.company_name }, row.company_name) : null,
    row.project_phase ? h('span', row.project_phase) : null,
  ].filter(Boolean)
  return h('div', { class: 'issue-title-cell' }, [
    h(
      'button',
      {
        class: 'issue-title-link',
        type: 'button',
        onClick: (event) => {
          event.preventDefault()
          openDetail(row)
        },
      },
      row.title || '-',
    ),
    meta.length
      ? h(
          'div',
          { class: 'issue-title-meta' },
          meta,
        )
      : null,
  ])
}

function defaultCreateForm() {
  return {
    title: '',
    description: '',
    project_phase: '',
    issue_type: '',
    impact_scope: '',
    category: '',
    company_name: '',
    contact_name: '',
    email: '',
    phone: '',
    assigned_to_id: Number(userStore.userId) || null,
    issue_priority_id: null,
    custom_values: {},
  }
}

function ensureCreateDefaults() {
  if (!createForm.value.project_phase)
    createForm.value.project_phase = projectPhaseOptions.value[0]?.value || ''
  const issueTypeValues = issueTypeOptions.value.map((item) => item.value)
  if (!createForm.value.issue_type || !issueTypeValues.includes(createForm.value.issue_type))
    createForm.value.issue_type = issueTypeOptions.value[0]?.value || ''
  if (!createForm.value.impact_scope)
    createForm.value.impact_scope = impactScopeOptions.value[0]?.value || ''
  if (!createForm.value.category) createForm.value.category = categoryOptions.value[0]?.value || ''
  const priorityValues = optionList('priorities').map((item) => item.value)
  if (
    !createForm.value.issue_priority_id ||
    !priorityValues.includes(createForm.value.issue_priority_id)
  ) {
    createForm.value.issue_priority_id = priorityValues[0] || null
  }
  if (!createForm.value.assigned_to_id && userStore.userId) {
    createForm.value.assigned_to_id = Number(userStore.userId)
  }
  ensureCustomDefaults()
}

function userOption(user) {
  return {
    label: user.alias || user.username || user.email || `用户 #${user.id}`,
    value: Number(user.id),
  }
}

function defaultQueryId() {
  return 'builtin:assigned-to-me'
}

function defaultQueryFilters() {
  const userId = Number(userStore.userId || 0)
  return userId ? { assigned_to_id: userId } : {}
}

async function loadAssigneeOptions() {
  const options = []
  try {
    const res = await api.getIssueAssignees()
    options.push(...(res?.data || []).map(userOption))
  } catch {
    // 指派人列表只是新建体验增强；后端仍会默认指派给当前提交人。
  }
  const currentUserId = Number(userStore.userId || 0)
  if (currentUserId && !options.some((item) => item.value === currentUserId)) {
    options.unshift({
      label: userStore.name || `用户 #${currentUserId}`,
      value: currentUserId,
    })
  }
  assigneeOptions.value = options
  ensureCreateDefaults()
}

function ensureCustomDefaults() {
  createForm.value.custom_values = createForm.value.custom_values || {}
  for (const field of customFields.value) {
    const key = String(field.id)
    if (createForm.value.custom_values[key] == null && field.default_value != null) {
      createForm.value.custom_values[key] = field.multiple
        ? [field.default_value]
        : field.default_value
    }
  }
}

function openDetail(row) {
  if (!row?.id) return
  detailIssueId.value = Number(row.id)
  detailIssueProjectName.value = row.company_name || ''
  detailVisible.value = true
}

function openCreateModal() {
  resetCreateForm()
  fetchPrefill()
  showCreateModal.value = true
}

function resetCreateForm() {
  createForm.value = defaultCreateForm()
  ensureCreateDefaults()
  uploadedAttachmentIds.value = []
  uploadFileList.value = []
}

function buildTemplateLabel(value, index) {
  const plainText = String(value || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return plainText ? `模板${index + 1} · ${plainText.slice(0, 12)}` : `模板${index + 1}`
}

function hasRichText(value) {
  return String(value || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .trim()
}

async function loadIssueCreateConfig() {
  try {
    const res = await api.getAppConfig()
    const config = res?.data || {}
    appStore.setSiteConfig(config)
    const projectPhases = config.ticket_project_phases || []
    const impactScopes = config.ticket_impact_scopes || []
    const categories = config.ticket_categories || []
    const descriptionTemplates = config.ticket_description_templates || []
    const attachmentExtensions = config.ticket_attachment_extensions || []
    if (projectPhases.length)
      projectPhaseOptions.value = projectPhases.map((item) => ({ label: item, value: item }))
    if (impactScopes.length)
      impactScopeOptions.value = impactScopes.map((item) => ({ label: item, value: item }))
    if (categories.length)
      categoryOptions.value = categories.map((item) => ({ label: item, value: item }))
    descriptionTemplateOptions.value = descriptionTemplates.map((item, index) => ({
      label: buildTemplateLabel(item, index),
      value: item,
    }))
    if (attachmentExtensions.length) {
      attachmentAccept.value = attachmentExtensions
        .map((item) => `.${String(item).replace(/^\./, '')}`)
        .join(',')
    }
    ensureCreateDefaults()
    if (!createForm.value.description && descriptionTemplateOptions.value.length) {
      createForm.value.description = descriptionTemplateOptions.value[0].value
    }
  } catch {
    ensureCreateDefaults()
  }
}

async function fetchPrefill() {
  try {
    const res = await api.getTicketPrefill()
    createForm.value.contact_name = res?.data?.contact_name || createForm.value.contact_name
    createForm.value.email = res?.data?.email || createForm.value.email
    createForm.value.phone = res?.data?.phone || createForm.value.phone
  } catch {
    // prefill is a convenience only
  }
}

function applyDescriptionTemplate(value) {
  if (value) createForm.value.description = value
}

function buildObjectUrl(rawFile) {
  if (!rawFile) return ''
  try {
    return URL.createObjectURL(rawFile)
  } catch {
    return ''
  }
}

async function uploadSingleFile(rawFile, targetFile = null) {
  const res = await api.uploadTicketAttachment(rawFile)
  const attachmentId = Number(res?.data?.id || 0)
  if (!attachmentId) throw new Error('上传成功但未返回附件ID')
  if (targetFile) {
    targetFile.attachmentId = attachmentId
    if (isImageName(targetFile.name)) targetFile.url = buildObjectUrl(rawFile)
  }
  uploadedAttachmentIds.value = [...new Set([...uploadedAttachmentIds.value, attachmentId])]
}

async function customUpload({ file, onFinish, onError }) {
  try {
    uploadLoading.value = true
    await uploadSingleFile(file.file, file)
    onFinish()
  } catch {
    onError()
  } finally {
    uploadLoading.value = false
  }
}

async function handlePasteUpload(event) {
  const files = Array.from(event?.clipboardData?.files || [])
  const imageFiles = files.filter((item) => /^image\//.test(item.type || ''))
  if (!imageFiles.length) return
  event.preventDefault()
  for (const rawFile of imageFiles) {
    if (uploadFileList.value.length >= 5) break
    const uploadFile = {
      id: `${Date.now()}-${Math.random()}`,
      name: rawFile.name || `pasted-${Date.now()}.png`,
      status: 'uploading',
      file: rawFile,
      url: buildObjectUrl(rawFile),
    }
    uploadFileList.value = [...uploadFileList.value, uploadFile]
    try {
      uploadLoading.value = true
      await uploadSingleFile(rawFile, uploadFile)
      uploadFile.status = 'finished'
    } catch {
      uploadFile.status = 'error'
    } finally {
      uploadLoading.value = false
    }
  }
}

function handleRemove({ file }) {
  const attachmentId = Number(file?.attachmentId || 0)
  if (attachmentId > 0) {
    uploadedAttachmentIds.value = uploadedAttachmentIds.value.filter((id) => id !== attachmentId)
  }
}

function compactFilters() {
  const filters = Object.fromEntries(
    Object.entries(queryItems.value || {}).filter(
      ([, value]) => value !== '' && value !== null && value !== undefined,
    ),
  )
  const customValues = {}
  for (const key of Object.keys(filters)) {
    if (key.startsWith('cf_')) {
      customValues[key.slice(3)] = filters[key]
      delete filters[key]
    }
  }
  if (Object.keys(customValues).length) filters.custom_values = customValues
  return filters
}

async function applySavedQuery(queryId) {
  const builtInQuery = builtInQueries.value.find((item) => item.value === queryId)
  if (builtInQuery) {
    queryItems.value = { ...builtInQuery.filters }
    await nextTick()
    $table.value?.handleSearch?.()
    return
  }
  const query = queries.value.find((item) => Number(item.id) === Number(queryId))
  const filters = { ...(query?.filters || {}) }
  const customValues = filters.custom_values || {}
  delete filters.custom_values
  queryItems.value = {
    ...filters,
    ...Object.fromEntries(Object.entries(customValues).map(([key, value]) => [`cf_${key}`, value])),
  }
  await nextTick()
  $table.value?.handleSearch?.()
}

function savedQueryId(value) {
  if (!value || String(value).startsWith('builtin:')) return null
  const id = Number(value)
  return Number.isFinite(id) ? id : null
}

function splitListParams(params = {}) {
  const filters = { ...params }
  const customValues = {}
  for (const key of Object.keys(filters)) {
    if (key.startsWith('cf_')) {
      customValues[key.slice(3)] = filters[key]
      delete filters[key]
    }
  }
  return {
    filters,
    customValues,
  }
}

function isEmptyCustomValue(value) {
  return value == null || value === '' || (Array.isArray(value) && !value.length)
}

function cleanCustomValues(values = {}) {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => !isEmptyCustomValue(value)),
  )
}

function validateCustomFields(values = createForm.value.custom_values) {
  const missing = customFields.value.find(
    (field) => field.is_required && isEmptyCustomValue(values?.[field.id]),
  )
  if (missing) {
    $message.warning(`请填写自定义字段：${missing.name}`)
    return false
  }
  return true
}

function customFieldOptions(field) {
  return (field.possible_values || []).map((item) => ({ label: item, value: item }))
}

function customFieldValue(field, values = {}) {
  const value = values?.[field.id] ?? values?.[String(field.id)]
  if (Array.isArray(value)) return value.join('、') || '-'
  if (field.field_format === 'bool')
    return value == null || value === '' ? '-' : value ? '是' : '否'
  return value == null || value === '' ? '-' : value
}

function openSaveQueryDrawer() {
  queryName.value = ''
  showQueryModal.value = true
}

async function saveCurrentQuery() {
  if (!queryName.value.trim()) {
    $message.warning('请输入查询名称')
    return
  }
  savingQuery.value = true
  try {
    await api.createIssueQuery({
      name: queryName.value.trim(),
      filters: compactFilters(),
      sort_criteria: [{ field: 'updated_at', direction: 'desc' }],
    })
    $message.success('查询已保存')
    showQueryModal.value = false
    queryName.value = ''
    await loadQueries()
  } finally {
    savingQuery.value = false
  }
}

async function submitCreateIssue() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (!validateCustomFields()) return
  creating.value = true
  try {
    const res = await api.createIssue({
      ...createForm.value,
      title: createForm.value.title.trim(),
      description: createForm.value.description || '',
      custom_values: cleanCustomValues(createForm.value.custom_values),
      attachment_ids: [...uploadedAttachmentIds.value],
    })
    $message.success('工单已创建')
    showCreateModal.value = false
    resetCreateForm()
    $table.value?.handleSearch?.()
    if (res?.data?.id) openDetail(res.data)
  } finally {
    creating.value = false
  }
}

const columns = computed(() => [
  {
    title: '#',
    key: 'id',
    align: 'center',
    width: 86,
    render(row) {
      return h('span', { class: 'issue-id-pill' }, `#${row.id}`)
    },
  },
  {
    title: '标题',
    key: 'title',
    align: 'center',
    minWidth: 280,
    render: renderIssueTitle,
  },
  {
    title: '跟踪',
    key: 'issue_tracker_id',
    align: 'center',
    width: 110,
    render: (row) => renderTag(displayName(row, 'tracker_name', 'issue_tracker_id'), 'default'),
  },
  {
    title: '状态',
    key: 'issue_status_id',
    align: 'center',
    width: 130,
    render: (row) =>
      renderTag(displayName(row, 'status_name', 'issue_status_id'), statusTagType(row)),
  },
  {
    title: '优先级',
    key: 'issue_priority_id',
    align: 'center',
    width: 110,
    render: (row) =>
      renderTag(
        displayName(row, 'priority_name', 'issue_priority_id'),
        priorityTagType(row.priority_name),
      ),
  },
  ...customFields.value.filter((field) => field.show_in_list).map((field) => ({
    title: field.name,
    key: `cf_${field.id}`,
    align: 'center',
    minWidth: 140,
    render: (row) => customFieldValue(field, row.custom_values),
  })),
  {
    title: '当前指派人',
    key: 'assigned_to_id',
    align: 'center',
    width: 120,
    render: (row) => row.assigned_to_name || row.assigned_to_id || '未指派',
  },
  {
    title: '更新于',
    key: 'updated_at',
    align: 'center',
    width: 180,
    render: (row) => (row.updated_at ? formatDateTime(row.updated_at) : '-'),
  },
])
</script>

<template>
  <CommonPage title="工单列表" :show-header="false" show-footer>
    <div class="issue-list-page">
      <div class="table-shell">
        <div class="issue-toolbar">
          <div class="query-tools">
            <NSelect
              v-model:value="selectedQueryId"
              :options="queryOptions"
              clearable
              placeholder="保存查询"
              @update:value="applySavedQuery"
            />
            <NButton secondary @click="openSaveQueryDrawer">
              <template #icon>
                <TheIcon icon="mdi-content-save-cog-outline" :size="16" />
              </template>
              保存查询
            </NButton>
            <NButton type="primary" @click="openCreateModal">
              <template #icon>
                <TheIcon icon="mdi-content-save-cog-outline" :size="18" />
              </template>
              新建工单
            </NButton>
          </div>
        </div>
        <CrudTable
          ref="$table"
          v-model:query-items="queryItems"
          :columns="columns"
          :get-data="getIssueList"
          :scroll-x="tableScrollX"
        >
          <template #queryBar>
            <QueryBarItem label="标题" :label-width="40">
              <NInput
                v-model:value="queryItems.title"
                clearable
                placeholder="输入标题"
                @keypress.enter="$table?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="提交者" :label-width="58">
              <NInput
                v-model:value="queryItems.submitter_name"
                clearable
                placeholder="输入提交者"
                style="width: 140px"
                @keypress.enter="$table?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="项目名称" :label-width="68">
              <NInput
                v-model:value="queryItems.issue_project_name"
                clearable
                placeholder="输入项目名称"
                style="width: 140px"
                @keypress.enter="$table?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="跟踪" :label-width="58">
              <NSelect
                v-model:value="queryItems.issue_tracker_id"
                :options="optionList('trackers')"
                clearable
                placeholder="跟踪"
                style="width: 140px"
              />
            </QueryBarItem>
            <QueryBarItem label="状态" :label-width="58">
              <NSelect
                v-model:value="queryItems.issue_status_name"
                :options="metadata.statuses.map((item) => ({ label: item.name, value: item.name }))"
                clearable
                placeholder="状态"
                style="width: 140px"
              />
            </QueryBarItem>
            <QueryBarItem label="优先级" :label-width="58">
              <NSelect
                v-model:value="queryItems.issue_priority_id"
                :options="optionList('priorities')"
                clearable
                placeholder="优先级"
                style="width: 140px"
              />
            </QueryBarItem>
            <QueryBarItem label="当前指派人" :label-width="82">
              <NInput
                v-model:value="queryItems.assigned_to_name"
                clearable
                placeholder="输入用户名称"
                style="width: 140px"
                @keypress.enter="$table?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem
              v-for="field in customFilterFields"
              :key="field.id"
              :label="field.name"
              :label-width="68"
            >
              <NSelect
                v-if="field.field_format === 'bool'"
                v-model:value="queryItems[`cf_${field.id}`]"
                :options="[
                  { label: '是', value: '1' },
                  { label: '否', value: '0' },
                ]"
                clearable
                placeholder="请选择"
                style="width: 150px"
              />
              <NSelect
                v-else-if="field.field_format === 'list'"
                v-model:value="queryItems[`cf_${field.id}`]"
                :options="customFieldOptions(field)"
                :multiple="field.multiple"
                clearable
                placeholder="请选择"
                style="width: 150px"
              />
              <NInputNumber
                v-else-if="['int', 'float', 'user', 'version'].includes(field.field_format)"
                v-model:value="queryItems[`cf_${field.id}`]"
                clearable
                placeholder="输入值"
                style="width: 150px"
              />
              <NInput
                v-else
                v-model:value="queryItems[`cf_${field.id}`]"
                clearable
                placeholder="输入值"
                style="width: 150px"
                @keypress.enter="$table?.handleSearch()"
              />
            </QueryBarItem>
          </template>
        </CrudTable>
      </div>

      <NDrawer v-model:show="showCreateModal" placement="right" :width="1080">
        <NDrawerContent
          title="新建工单"
          closable
          body-content-class="issue-drawer-body"
          body-content-style="padding: 0 20px;"
        >
          <NForm
            ref="formRef"
            :model="createForm"
            :rules="createRules"
            :label-width="92"
            label-placement="left"
            class="issue-create-form"
          >
            <section class="create-section">
              <div class="create-section-head compact">
                <div>
                  <h3>问题内容</h3>
                </div>
              </div>
              <div class="create-grid two-col">
                <NFormItem label="项目名称" path="company_name">
                  <NInput
                    v-model:value="createForm.company_name"
                    clearable
                    placeholder="请输入项目或客户名称"
                  />
                </NFormItem>
                <NFormItem label="项目阶段" path="project_phase">
                  <NSelect
                    v-model:value="createForm.project_phase"
                    :options="projectPhaseOptions"
                    placeholder="请选择项目阶段"
                  />
                </NFormItem>
                <NFormItem label="跟踪" path="issue_type">
                  <NSelect
                    v-model:value="createForm.issue_type"
                    :options="issueTypeOptions"
                    placeholder="请选择问题或需求类型"
                  />
                </NFormItem>
                <NFormItem label="影响范围" path="impact_scope">
                  <NSelect
                    v-model:value="createForm.impact_scope"
                    :options="impactScopeOptions"
                    placeholder="请选择影响范围"
                  />
                </NFormItem>
                <NFormItem label="问题分类" path="category">
                  <NSelect
                    v-model:value="createForm.category"
                    :options="categoryOptions"
                    placeholder="请选择分类"
                  />
                </NFormItem>
                <NFormItem label="当前指派人">
                  <NSelect
                    v-model:value="createForm.assigned_to_id"
                    :options="assigneeOptions"
                    clearable
                    filterable
                    placeholder="默认当前提交人"
                  />
                </NFormItem>
                <NFormItem label="优先级" path="issue_priority_id">
                  <NSelect
                    v-model:value="createForm.issue_priority_id"
                    :options="optionList('priorities')"
                    placeholder="请选择优先级"
                  />
                </NFormItem>
                <NFormItem
                  v-for="field in customFields"
                  :key="field.id"
                  :label="field.name"
                  :required="field.is_required"
                >
                  <NSelect
                    v-if="field.field_format === 'list'"
                    v-model:value="createForm.custom_values[field.id]"
                    :options="customFieldOptions(field)"
                    :multiple="field.multiple"
                    clearable
                    placeholder="请选择"
                  />
                  <NCheckbox
                    v-else-if="field.field_format === 'bool'"
                    v-model:checked="createForm.custom_values[field.id]"
                  >
                    是
                  </NCheckbox>
                  <NInputNumber
                    v-else-if="['int', 'float', 'user', 'version'].includes(field.field_format)"
                    v-model:value="createForm.custom_values[field.id]"
                    clearable
                    :precision="field.field_format === 'float' ? undefined : 0"
                    placeholder="请输入"
                    style="width: 100%"
                  />
                  <input
                    v-else-if="field.field_format === 'date'"
                    v-model="createForm.custom_values[field.id]"
                    class="native-date-input"
                    type="date"
                  />
                  <NInput
                    v-else-if="field.field_format === 'text'"
                    v-model:value="createForm.custom_values[field.id]"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 5 }"
                    placeholder="请输入"
                  />
                  <NInput
                    v-else
                    v-model:value="createForm.custom_values[field.id]"
                    clearable
                    placeholder="请输入"
                  />
                </NFormItem>
                <NFormItem class="create-grid-span-2" label="标题" path="title">
                  <NInput
                    v-model:value="createForm.title"
                    clearable
                    placeholder="例如：用户导入报错 500"
                  />
                </NFormItem>
                <NFormItem class="create-grid-span-2" label="描述" path="description">
                  <div class="editor-host">
                    <div v-if="descriptionTemplateOptions.length" class="template-toolbar">
                      <span class="template-label">描述模板</span>
                      <NSpace size="small">
                        <NButton
                          v-for="item in descriptionTemplateOptions"
                          :key="item.value"
                          size="small"
                          secondary
                          @click="applyDescriptionTemplate(item.value)"
                        >
                          {{ item.label }}
                        </NButton>
                      </NSpace>
                    </div>
                    <RichTextEditor
                      v-model="createForm.description"
                      placeholder="建议包含问题现象、复现步骤、影响范围、期望结果"
                      :min-height="220"
                      :max-height="460"
                    />
                  </div>
                </NFormItem>
              </div>
            </section>

            <section class="create-section">
              <div class="create-section-head compact">
                <div>
                  <h3>附件</h3>
                  <p>截图、日志、报错文件会随工单一起进入处理闭环。</p>
                </div>
              </div>
              <NFormItem label="附件">
                <div class="upload-box" @paste="handlePasteUpload">
                  <NUpload
                    v-model:file-list="uploadFileList"
                    list-type="text"
                    :custom-request="customUpload"
                    :max="5"
                    :accept="attachmentAccept"
                    @remove="handleRemove"
                  >
                    <NButton class="upload-btn" :loading="uploadLoading">
                      <template #icon>
                        <TheIcon icon="mdi-content-save-cog-outline" :size="17" />
                      </template>
                      上传附件
                    </NButton>
                  </NUpload>
                  <span class="upload-tip"
                    >支持最多 5 个附件，支持粘贴图片上传，当前允许类型：{{
                      attachmentAccept
                    }}。</span
                  >
                </div>
              </NFormItem>
            </section>
          </NForm>
          <template #footer>
            <div class="modal-actions">
              <NButton @click="showCreateModal = false">
                <template #icon>
                  <TheIcon icon="mdi-content-save-cog-outline" :size="16" />
                </template>
                取消
              </NButton>
              <NButton type="primary" :loading="creating" @click="submitCreateIssue">
                <template #icon>
                  <TheIcon icon="mdi-content-save-cog-outline" :size="18" />
                </template>
                创建
              </NButton>
            </div>
          </template>
        </NDrawerContent>
      </NDrawer>

      <NDrawer
        v-model:show="detailVisible"
        placement="right"
        :width="1040"
        @after-leave="detailIssueId = null"
      >
        <NDrawerContent
          :title="detailDrawerTitle"
          closable
          body-content-class="issue-drawer-body"
          body-content-style="padding: 0;"
        >
          <IssueDetail
            v-if="detailVisible && detailIssueId"
            :issue-id="detailIssueId"
            embedded
            @updated="$table?.handleSearch?.()"
          />
        </NDrawerContent>
      </NDrawer>

      <NDrawer v-model:show="showQueryModal" placement="right" :width="420">
        <NDrawerContent
          title="保存查询"
          closable
          body-content-class="query-drawer-body"
          body-content-style="padding: 0 18px;"
        >
          <div class="query-save-panel">
            <div class="query-save-note">
              <strong>保存当前筛选条件</strong>
              <span>下次可直接从列表上方的保存查询下拉中快速切换。</span>
            </div>
            <NForm label-placement="top">
              <NFormItem label="查询名称">
                <NInput
                  v-model:value="queryName"
                  clearable
                  placeholder="例如：我关注的高优先级问题"
                  @keypress.enter="saveCurrentQuery"
                />
              </NFormItem>
            </NForm>
          </div>
          <template #footer>
            <div class="query-drawer-footer">
              <NButton @click="showQueryModal = false">取消</NButton>
              <NButton type="primary" :loading="savingQuery" @click="saveCurrentQuery">
                <template #icon>
                  <TheIcon icon="mdi-content-save-cog-outline" :size="17" />
                </template>
                保存
              </NButton>
            </div>
          </template>
        </NDrawerContent>
      </NDrawer>
    </div>
  </CommonPage>
</template>

<style scoped>
.issue-list-page {
  --issue-accent: #0f766e;
  --issue-accent-soft: #e8f5f1;
  --issue-border: #e5e7eb;
  --issue-muted: #64748b;
  --issue-ink: #111827;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.table-shell {
  padding: 14px;
  border: 1px solid var(--issue-border);
  border-radius: 8px;
  background: linear-gradient(180deg, #f8fafc 0%, #fff 86px);
}

.issue-toolbar,
.query-tools,
.modal-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.issue-toolbar {
  align-items: flex-start;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.query-tools :deep(.n-select) {
  width: 220px;
}

:deep(.n-data-table-th) {
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}

:deep(.issue-id-pill) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  height: 24px;
  border-radius: 999px;
  background: var(--issue-accent-soft);
  color: var(--issue-accent);
  font-size: 12px;
  font-weight: 700;
}

:deep(.issue-title-cell) {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  min-width: 0;
  padding: 2px 0;
  text-align: center;
}

:deep(.issue-title-link) {
  appearance: none;
  border: 0;
  background: transparent;
  color: #1d4ed8;
  cursor: pointer;
  font-weight: 700;
  line-height: 1.4;
  padding: 0;
  text-align: center;
  text-decoration: none;
  white-space: normal;
}

:deep(.issue-title-link:hover) {
  text-decoration: underline;
}

:deep(.issue-title-meta) {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  color: var(--issue-muted);
  font-size: 12px;
}

:deep(.issue-title-meta span) {
  max-width: 180px;
  overflow: hidden;
  padding: 2px 7px;
  border-radius: 999px;
  background: #f1f5f9;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.issue-modal {
  width: min(980px, calc(100vw - 32px));
}

.issue-create-form {
  padding-right: 0;
}

:deep(.issue-drawer-body) {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

:deep(.issue-drawer-body::-webkit-scrollbar) {
  width: 0;
  height: 0;
}

.query-save-panel {
  padding: 18px 0;
}

.query-drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.query-save-note {
  display: grid;
  gap: 5px;
  margin-bottom: 18px;
  padding: 14px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #eff6ff;
}

.query-save-note strong {
  color: #1e3a8a;
  font-size: 14px;
}

.query-save-note span {
  color: #475569;
  font-size: 12px;
  line-height: 1.5;
}

.create-section {
  margin-bottom: 16px;
  padding: 16px 16px 4px;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: linear-gradient(180deg, #fff 0%, #fbfcfe 100%);
}

.create-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.create-section-head.compact {
  margin-bottom: 10px;
}

.create-section-head h3 {
  margin: 0;
  color: var(--issue-ink);
  font-size: 16px;
  line-height: 1.35;
}

.create-section-head p {
  margin: 5px 0 0;
  color: var(--issue-muted);
  font-size: 12px;
  line-height: 1.5;
}

.create-grid {
  display: grid;
  gap: 2px 16px;
}

.create-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.create-grid.single-col {
  grid-template-columns: minmax(0, 1fr);
}

.create-grid-span-2 {
  grid-column: 1 / -1;
}

.editor-host,
.upload-box {
  width: 100%;
}

.native-date-input {
  width: 100%;
  height: 34px;
  padding: 0 12px;
  border: 1px solid #d9d9e3;
  border-radius: 4px;
  background: #fff;
  color: var(--issue-ink);
}

.template-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.template-label,
.upload-tip {
  color: var(--issue-muted);
  font-size: 12px;
}

.template-label {
  font-weight: 700;
}

.upload-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.upload-btn {
  width: fit-content;
}

.modal-actions {
  justify-content: flex-end;
}

@media (max-width: 720px) {
  .issue-toolbar,
  .query-tools {
    align-items: stretch;
    flex-direction: column;
  }

  .query-tools :deep(.n-select) {
    width: 100%;
  }

  .create-grid.two-col {
    grid-template-columns: minmax(0, 1fr);
  }

  .create-section-head {
    flex-direction: column;
  }
}
</style>
