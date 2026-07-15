<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  NAlert,
  NButton,
  NCheckbox,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NSpin,
  NTag,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import RichTextEditor from '@/components/editor/RichTextEditor.vue'
import api from '@/api'
import { useAppStore, usePermissionStore } from '@/store'
import { isImageName, sanitizeHtml } from '@/utils'

defineOptions({ name: '工单详情' })

const props = defineProps({
  issueId: { type: [Number, String], default: 0 },
  embedded: { type: Boolean, default: false },
})
const emit = defineEmits(['updated'])
const route = useRoute()
const appStore = useAppStore()
const permissionStore = usePermissionStore()
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const errorMessage = ref('')
const issue = ref({})
const metadata = ref({ trackers: [], statuses: [], priorities: [], custom_fields: [] })
const statusChoices = ref([])
const assigneeOptions = ref([])
const rootCauseValues = ref([
  '代码缺陷',
  '配置错误',
  '环境异常',
  '数据问题',
  '操作不当',
  '第三方依赖',
])
const previewingAttachmentId = ref(null)
const imagePreviewMap = ref({})
const descriptionImagePreviewVisible = ref(false)
const descriptionImagePreviewSrc = ref('')
const descriptionImagePreviewAlt = ref('')
const editDescriptionVisible = ref(false)
const form = ref({
  title: '',
  company_name: '',
  project_phase: '',
  issue_tracker_id: null,
  issue_status_id: null,
  impact_scope: '',
  category: '',
  root_cause: '',
  assigned_to_id: null,
  issue_priority_id: null,
  description: '',
  custom_values: {},
  notes: '',
})

const issueId = computed(() => Number(props.issueId || route.query.issue_id || 0))
const isEmbedded = computed(() => props.embedded)
const pageShell = computed(() => (props.embedded ? 'div' : CommonPage))
const pageShellProps = computed(() => (props.embedded ? {} : { showHeader: false }))
const canUpdate = computed(() => permissionStore.apis.includes('post/api/v1/issue/update'))
const statusOptions = computed(() =>
  statusChoices.value.map((item) => ({ label: item.name, value: item.id })),
)
const priorityOptions = computed(() =>
  (metadata.value.priorities || []).map((item) => ({ label: item.name, value: item.id })),
)
const trackerOptions = computed(() =>
  (metadata.value.trackers || []).map((item) => ({ label: item.name, value: item.id })),
)
const projectPhaseOptions = computed(() => listOptions(appStore.ticketProjectPhases))
const impactScopeOptions = computed(() => listOptions(appStore.ticketImpactScopes))
const categoryOptions = computed(() => listOptions(appStore.ticketCategories))
const rootCauseOptions = computed(() => listOptions(rootCauseValues.value))
const customFields = computed(() => metadata.value.custom_fields || [])
const safeDescription = computed(() => sanitizeHtml(issue.value.description || '-'))
const descriptionExpanded = ref(true)
const selectedStatus = computed(() =>
  statusChoices.value.find(
    (item) => Number(item.id) === normalizeNumber(form.value.issue_status_id),
  ),
)
const isClosingStatus = computed(() => Boolean(selectedStatus.value?.is_closed))
const issueClosed = computed(() => Boolean(issue.value.status_is_closed))
const attachments = computed(() =>
  Array.isArray(issue.value.attachments) ? issue.value.attachments : [],
)
const imageAttachments = computed(() =>
  attachments.value.filter((item) => canUseAttachment(item) && isImageAttachment(item)),
)
const previewImageAttachments = computed(() =>
  imageAttachments.value.filter((item) => getImagePreviewUrl(item)),
)
const historyMaps = computed(() => issue.value.history_maps || {})

const fieldLabels = {
  issue_status_id: '状态',
  assigned_to_id: '当前指派人',
  company_name: '项目名称',
  project_phase: '项目阶段',
  issue_tracker_id: '跟踪',
  issue_priority_id: '优先级',
  impact_scope: '影响范围',
  category: '问题分类',
  root_cause: '问题根因',
  title: '标题',
  description: '描述',
}
const requiredTextLabels = {
  company_name: '项目名称',
  project_phase: '项目阶段',
  impact_scope: '影响范围',
  category: '问题分类',
  title: '标题',
}
const requiredIdLabels = {
  issue_tracker_id: '跟踪',
  issue_status_id: '状态',
  issue_priority_id: '优先级',
}

function listOptions(values = []) {
  return values.map((item) => ({ label: item, value: item }))
}

function userOption(user) {
  return {
    label: user.alias || user.username || user.email || `用户 #${user.id}`,
    value: Number(user.id),
  }
}

async function loadAssigneeOptions(statusId = form.value.issue_status_id, keepCurrent = true) {
  const options = []
  try {
    const res = await api.getIssueAssignees({
      issue_id: issueId.value,
      status_id: statusId || undefined,
      tracker_id: form.value.issue_tracker_id || issue.value.issue_tracker_id || undefined,
    })
    options.push(...(res?.data || []).map(userOption))
  } catch {
    // 用户列表不是详情编辑的硬依赖；至少保留当前指派人。
  }
  if (
    keepCurrent &&
    issue.value.assigned_to_id &&
    !options.some((item) => item.value === Number(issue.value.assigned_to_id))
  ) {
    options.unshift({
      label: issue.value.assigned_to_name || `用户 #${issue.value.assigned_to_id}`,
      value: Number(issue.value.assigned_to_id),
    })
  }
  assigneeOptions.value = options
}

function resetForm() {
  form.value = {
    title: issue.value.title || '',
    company_name: issue.value.company_name || '',
    project_phase: issue.value.project_phase || '',
    issue_tracker_id: issue.value.issue_tracker_id || null,
    issue_status_id: issue.value.issue_status_id || null,
    impact_scope: issue.value.impact_scope || '',
    category: issue.value.category || '',
    root_cause: issue.value.root_cause || '',
    assigned_to_id: issue.value.assigned_to_id || null,
    issue_priority_id: issue.value.issue_priority_id || null,
    description: issue.value.description || '',
    custom_values: { ...(issue.value.custom_values || {}) },
    notes: '',
  }
}

async function loadIssue() {
  if (!issueId.value) {
    errorMessage.value = '缺少工单ID'
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    const [metaRes, issueRes, statusRes, configRes] = await Promise.all([
      api.getIssueMetadata(),
      api.getIssueById({ issue_id: issueId.value }),
      api.getIssueStatusOptions({ issue_id: issueId.value }),
      api.getAppConfig().catch(() => null),
    ])
    if (configRes?.data) {
      appStore.setSiteConfig(configRes.data)
      if (configRes.data.ticket_root_causes?.length)
        rootCauseValues.value = configRes.data.ticket_root_causes
    }
    metadata.value = metaRes?.data || {
      trackers: [],
      statuses: [],
      priorities: [],
      custom_fields: [],
    }
    issue.value = issueRes?.data || {}
    statusChoices.value = statusRes?.data?.statuses || []
    resetForm()
    descriptionExpanded.value = true
    editDescriptionVisible.value = false
    await loadAssigneeOptions()
    editing.value = false
  } catch {
    errorMessage.value = '加载工单详情失败'
  } finally {
    loading.value = false
  }
}

function normalizeNumber(value) {
  return value === '' || value == null ? null : Number(value)
}

function buildChanges() {
  const changes = {}
  for (const field of [
    'issue_tracker_id',
    'issue_status_id',
    'assigned_to_id',
    'issue_priority_id',
  ]) {
    const nextValue = normalizeNumber(form.value[field])
    const oldValue = normalizeNumber(issue.value[field])
    if (nextValue !== oldValue) changes[field] = nextValue
  }
  for (const field of ['title', 'company_name', 'project_phase', 'impact_scope', 'category']) {
    const nextValue = form.value[field] || null
    const oldValue = issue.value[field] || null
    if (nextValue !== oldValue) changes[field] = nextValue
  }
  if (isClosingStatus.value) {
    const nextValue = form.value.root_cause || null
    const oldValue = issue.value.root_cause || null
    if (nextValue !== oldValue) changes.root_cause = nextValue
  }
  if (editDescriptionVisible.value) {
    const nextDescription = form.value.description || null
    const oldDescription = issue.value.description || null
    if (nextDescription !== oldDescription) changes.description = nextDescription
  }
  return changes
}

function isEmptyCustomValue(value) {
  return value == null || value === '' || (Array.isArray(value) && !value.length)
}

function sameCustomValue(a, b) {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null)
}

function buildCustomChanges() {
  const changes = {}
  const current = issue.value.custom_values || {}
  for (const field of customFields.value) {
    const key = String(field.id)
    const nextValue = form.value.custom_values?.[key] ?? form.value.custom_values?.[field.id]
    const oldValue = current[key] ?? current[field.id]
    if (!sameCustomValue(nextValue, oldValue)) changes[key] = nextValue
  }
  return changes
}

function validateCustomFields(values = form.value.custom_values) {
  const missing = customFields.value.find(
    (field) =>
      field.is_required && isEmptyCustomValue(values?.[field.id] ?? values?.[String(field.id)]),
  )
  if (missing) {
    $message.warning(`请填写自定义字段：${missing.name}`)
    return false
  }
  return true
}

function richTextPlain(value) {
  const div = document.createElement('div')
  div.innerHTML = sanitizeHtml(value || '')
  return (div.textContent || '').replace(/\s+/g, ' ').trim()
}

function validateIssueFields(changes) {
  for (const [field, label] of Object.entries(requiredIdLabels)) {
    if (Object.hasOwn(changes, field) && !normalizeNumber(changes[field])) {
      $message.warning(`请选择${label}`)
      return false
    }
  }
  for (const [field, label] of Object.entries(requiredTextLabels)) {
    if (Object.hasOwn(changes, field) && !String(changes[field] || '').trim()) {
      $message.warning(`请输入${label}`)
      return false
    }
  }
  if (Object.hasOwn(changes, 'description') && !richTextPlain(changes.description)) {
    $message.warning('请输入描述')
    return false
  }
  return true
}

async function submitUpdate() {
  const changes = buildChanges()
  const customValues = buildCustomChanges()
  if (!validateIssueFields(changes)) return
  if (Object.hasOwn(changes, 'issue_status_id')) {
    const nextAssignee = normalizeNumber(form.value.assigned_to_id)
    if (!nextAssignee) {
      $message.warning('状态变更时必须指定当前指派人')
      return
    }
  }
  if (isClosingStatus.value && !form.value.root_cause?.trim()) {
    $message.warning('关闭工单时请填写问题根因')
    return
  }
  if (
    !Object.keys(changes).length &&
    !Object.keys(customValues).length &&
    !form.value.notes?.trim()
  ) {
    $message.warning('没有需要提交的变更')
    return
  }
  if (!validateCustomFields()) return
  saving.value = true
  try {
    await api.updateIssue({
      issue_id: issueId.value,
      changes,
      custom_values: customValues,
      notes: form.value.notes?.trim() || null,
    })
    $message.success('工单已更新')
    await loadIssue()
    emit('updated', issue.value)
  } finally {
    saving.value = false
  }
}

async function openEdit() {
  editing.value = true
  editDescriptionVisible.value = false
  await nextTick()
  scrollToSection('issue-update')
}

function valueName(kind, value) {
  if (value == null || value === '') return '-'
  const id = Number(value)
  if (!Number.isFinite(id)) return value || '-'
  const item = (metadata.value[kind] || []).find((row) => Number(row.id) === id)
  const historyItem = historyMaps.value[kind]?.[id] ?? historyMaps.value[kind]?.[String(id)]
  return item?.name || historyItem?.name || historyItem || value
}

function userName(value) {
  if (value == null || value === '') return '-'
  const id = Number(value)
  if (!Number.isFinite(id)) return value || '-'
  return (
    assigneeOptions.value.find((item) => item.value === id)?.label ||
    historyMaps.value.users?.[id] ||
    historyMaps.value.users?.[String(id)] ||
    `用户 #${value}`
  )
}

function detailPart(key, value) {
  if (key === 'issue_tracker_id') return valueName('trackers', value)
  if (key === 'issue_status_id') return valueName('statuses', value)
  if (key === 'issue_priority_id') return valueName('priorities', value)
  if (key === 'assigned_to_id') return userName(value)
  if (key === 'description') return richTextPlain(value) || '-'
  return value || '-'
}

function detailValue(detail) {
  const key = detail.prop_key
  if (detail.property === 'cf') {
    const field = customFields.value.find((item) => Number(item.id) === Number(key))
    return `${formatCustomValue(field, detail.old_value)} -> ${formatCustomValue(field, detail.value)}`
  }
  return `${detailPart(key, detail.old_value)} -> ${detailPart(key, detail.value)}`
}

function detailLabel(detail) {
  if (detail.property === 'cf') {
    return (
      customFields.value.find((item) => Number(item.id) === Number(detail.prop_key))?.name ||
      detail.prop_key
    )
  }
  return fieldLabels[detail.prop_key] || detail.prop_key
}

function customFieldOptions(field) {
  return (field.possible_values || []).map((item) => ({ label: item, value: item }))
}

function formatCustomValue(field, value) {
  if (!field) return value || '-'
  if (field.multiple) {
    const values = Array.isArray(value) ? value : parseMaybeJsonArray(value)
    return values.length ? values.join('、') : '-'
  }
  if (field.field_format === 'bool') {
    if (value == null || value === '') return '-'
    return value === true || value === '1' ? '是' : '否'
  }
  return value == null || value === '' ? '-' : value
}

function parseMaybeJsonArray(value) {
  if (Array.isArray(value)) return value
  try {
    const parsed = JSON.parse(value || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return value ? [value] : []
  }
}

function visibleJournalDetails(journal) {
  return (journal.details || []).filter((detail) => detail.prop_key !== 'done_ratio')
}

function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function isImageAttachment(item) {
  return isImageName(item?.origin_name || item?.file_path || '')
}

function canUseAttachment(item) {
  return item?.file_exists !== false
}

function getImagePreviewUrl(item) {
  return imagePreviewMap.value[item.id] || ''
}

function revokeImagePreviewUrls(urls = Object.values(imagePreviewMap.value || {})) {
  urls.forEach((url) => {
    if (url) URL.revokeObjectURL(url)
  })
}

let imagePreviewRun = 0
async function loadImageAttachmentPreviews() {
  const run = ++imagePreviewRun
  revokeImagePreviewUrls()
  imagePreviewMap.value = {}
  const nextMap = {}
  for (const item of imageAttachments.value) {
    try {
      const res = await api.downloadTicketAttachment({ attachment_id: item.id })
      const blob = res instanceof Blob ? res : new Blob([res])
      nextMap[item.id] = URL.createObjectURL(blob)
    } catch {
      nextMap[item.id] = ''
    }
  }
  if (run !== imagePreviewRun) {
    revokeImagePreviewUrls(Object.values(nextMap))
    return
  }
  imagePreviewMap.value = nextMap
}

function openDescriptionImagePreview(event) {
  const target = event?.target
  if (!(target instanceof HTMLImageElement)) return
  const src = target.currentSrc || target.src
  if (!src) return
  event.preventDefault()
  descriptionImagePreviewSrc.value = src
  descriptionImagePreviewAlt.value = target.alt || '描述图片'
  descriptionImagePreviewVisible.value = true
}

async function previewAttachment(item) {
  if (!item?.id) return
  if (!canUseAttachment(item)) {
    $message.warning('附件文件不存在')
    return
  }
  previewingAttachmentId.value = item.id
  try {
    const res = await api.previewTicketAttachment({ attachment_id: item.id })
    const previewUrl = res?.data?.preview_url || ''
    if (!previewUrl) {
      $message.error('预览链接生成失败，请稍后重试')
      return
    }
    const routeUrl = `/public/webdav/preview?${new URLSearchParams({
      name: item.origin_name || `attachment-${item.id}`,
      url: previewUrl,
    }).toString()}`
    window.open(routeUrl, '_blank', 'noopener,noreferrer')
  } finally {
    previewingAttachmentId.value = null
  }
}

async function openAttachment(item) {
  if (!item?.id) return
  if (!canUseAttachment(item)) {
    $message.warning('附件文件不存在')
    return
  }
  const res = await api.downloadTicketAttachment({ attachment_id: item.id })
  const blob = res instanceof Blob ? res : new Blob([res])
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = item.origin_name || `attachment-${item.id}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

watch(issueId, loadIssue, { immediate: true })
watch(
  () => form.value.issue_status_id,
  async (value) => {
    if (!editing.value) return
    const currentStatusId = normalizeNumber(issue.value.issue_status_id)
    const nextStatusId = normalizeNumber(value)
    if (!nextStatusId) return
    if (nextStatusId === currentStatusId) {
      await loadAssigneeOptions(nextStatusId)
      form.value.assigned_to_id = issue.value.assigned_to_id || null
      return
    }
    await loadAssigneeOptions(nextStatusId, false)
    form.value.assigned_to_id = assigneeOptions.value[0]?.value || null
  },
)
watch(() => imageAttachments.value.map((item) => item.id).join(','), loadImageAttachmentPreviews)

onBeforeUnmount(() => {
  imagePreviewRun += 1
  revokeImagePreviewUrls()
  imagePreviewMap.value = {}
})
</script>

<template>
  <component :is="pageShell" v-bind="pageShellProps">
    <div class="issue-detail-page" :class="{ 'is-embedded': isEmbedded }">
      <NAlert v-if="errorMessage" type="error">{{ errorMessage }}</NAlert>
      <div v-else-if="loading" class="loading-state">
        <NSpin />
        <span>工单加载中...</span>
      </div>
      <template v-else>
        <header class="issue-hero">
          <div class="issue-hero-main">
            <h1>{{ issue.title || '-' }}</h1>
            <div class="issue-subline">
              <div class="issue-subline-row">
                <span class="issue-pill"
                  >提交人：{{ issue.submitter_name || issue.submitter_id || '-' }}</span
                >
                <span class="issue-pill">创建：{{ issue.created_at || '-' }}</span>
                <span class="issue-pill">更新：{{ issue.updated_at || '-' }}</span>
                <span class="issue-pill">项目阶段：{{ issue.project_phase || '-' }}</span>
                <span class="issue-pill">
                  跟踪：{{ issue.tracker_name || issue.issue_type || '-' }}
                </span>
                <span class="issue-pill">
                  状态：{{ issue.status_name || issue.issue_status_id || '-' }}
                </span>
              </div>
              <div class="issue-subline-row">
                <span class="issue-pill">影响范围：{{ issue.impact_scope || '-' }}</span>
                <span class="issue-pill">问题分类：{{ issue.category || '-' }}</span>
                <span class="issue-pill"
                  >优先级：{{ issue.priority_name || issue.issue_priority_id || '-' }}</span
                >
                <span class="issue-pill">
                  当前指派人：{{ issue.assigned_to_name || issue.assigned_to_id || '-' }}
                </span>
                <span v-for="field in customFields" :key="field.id" class="issue-pill">
                  {{ field.name }}：{{ formatCustomValue(field, issue.custom_values?.[field.id]) }}
                </span>
                <span v-if="issueClosed" class="issue-pill"
                  >问题根因：{{ issue.root_cause || '-' }}</span
                >
              </div>
            </div>
          </div>
          <div class="detail-actions">
            <NButton v-if="canUpdate" size="small" type="primary" secondary @click="openEdit">
              <template #icon>
                <TheIcon icon="material-symbols:edit-outline" :size="16" />
              </template>
              编辑
            </NButton>
          </div>
        </header>

        <div class="detail-layout">
          <main class="detail-main">
            <section class="issue-section">
              <div class="section-head">
                <div>
                  <span>DESCRIPTION</span>
                  <h2>描述</h2>
                </div>
                <NButton
                  v-if="issue.description && !descriptionExpanded"
                  size="small"
                  text
                  type="primary"
                  @click="descriptionExpanded = true"
                >
                  详细
                </NButton>
              </div>
              <!-- sanitized with sanitizeHtml before rendering -->
              <!-- eslint-disable vue/no-v-html -->
              <div
                class="description"
                :class="{ 'is-collapsed': !descriptionExpanded }"
                @click="openDescriptionImagePreview"
                v-html="safeDescription"
              ></div>
              <!-- eslint-enable vue/no-v-html -->
            </section>

            <section class="issue-section">
              <div class="section-head">
                <div>
                  <span>FILES</span>
                  <h2>附件</h2>
                </div>
                <NTag size="small" :bordered="false">{{ attachments.length }} 个</NTag>
              </div>
              <div v-if="previewImageAttachments.length" class="image-preview-grid">
                <a
                  v-for="item in previewImageAttachments"
                  :key="`img-${item.id}`"
                  :href="getImagePreviewUrl(item)"
                  target="_blank"
                  rel="noopener"
                  class="image-preview-item"
                >
                  <img
                    :src="getImagePreviewUrl(item)"
                    :alt="item.origin_name || `image-${item.id}`"
                  />
                </a>
              </div>
              <div v-if="attachments.length" class="attachment-list">
                <div v-for="item in attachments" :key="item.id" class="attachment-item">
                  <div>
                    <div class="attachment-name">{{ item.origin_name || item.file_path }}</div>
                    <div class="attachment-meta">
                      {{ item.mime_type || 'application/octet-stream' }} /
                      {{ item.file_size || 0 }} bytes
                      <template v-if="!canUseAttachment(item)"> / 文件不存在</template>
                    </div>
                  </div>
                  <div class="attachment-actions">
                    <NButton
                      v-if="!isImageAttachment(item)"
                      size="small"
                      type="info"
                      quaternary
                      :disabled="!canUseAttachment(item)"
                      :loading="previewingAttachmentId === item.id"
                      @click="previewAttachment(item)"
                    >
                      预览
                    </NButton>
                    <NButton
                      size="small"
                      type="primary"
                      quaternary
                      :disabled="!canUseAttachment(item)"
                      @click="openAttachment(item)"
                    >
                      下载
                    </NButton>
                  </div>
                </div>
              </div>
              <NAlert v-else type="default">暂无附件</NAlert>
            </section>

            <section
              v-if="canUpdate && editing"
              id="issue-update"
              class="issue-section update-section"
            >
              <div class="section-head">
                <div>
                  <span>EDIT</span>
                  <h2>编辑工单</h2>
                </div>
              </div>
              <NForm class="update-form" label-placement="top">
                <NFormItem label="项目名称">
                  <NInput
                    v-model:value="form.company_name"
                    clearable
                    placeholder="请输入项目或客户名称"
                  />
                </NFormItem>
                <NFormItem label="标题">
                  <NInput v-model:value="form.title" clearable placeholder="请输入标题" />
                </NFormItem>
                <NFormItem label="项目阶段">
                  <NSelect
                    v-model:value="form.project_phase"
                    :options="projectPhaseOptions"
                    placeholder="请选择项目阶段"
                  />
                </NFormItem>
                <NFormItem label="跟踪">
                  <NSelect
                    v-model:value="form.issue_tracker_id"
                    :options="trackerOptions"
                    placeholder="请选择跟踪"
                  />
                </NFormItem>
                <NFormItem label="影响范围">
                  <NSelect
                    v-model:value="form.impact_scope"
                    :options="impactScopeOptions"
                    placeholder="请选择影响范围"
                  />
                </NFormItem>
                <NFormItem label="问题分类">
                  <NSelect
                    v-model:value="form.category"
                    :options="categoryOptions"
                    placeholder="请选择问题分类"
                  />
                </NFormItem>
                <NFormItem label="状态">
                  <NSelect v-model:value="form.issue_status_id" :options="statusOptions" />
                </NFormItem>
                <NFormItem label="当前指派人">
                  <NSelect
                    v-model:value="form.assigned_to_id"
                    :options="assigneeOptions"
                    clearable
                    filterable
                    placeholder="请选择当前指派人"
                    style="width: 100%"
                  />
                </NFormItem>
                <NFormItem v-if="isClosingStatus" label="问题根因" required>
                  <NSelect
                    v-if="rootCauseOptions.length"
                    v-model:value="form.root_cause"
                    :options="rootCauseOptions"
                    clearable
                    placeholder="请选择问题根因"
                  />
                  <NInput
                    v-else
                    v-model:value="form.root_cause"
                    clearable
                    placeholder="请输入问题根因"
                  />
                </NFormItem>
                <NFormItem label="优先级">
                  <NSelect v-model:value="form.issue_priority_id" :options="priorityOptions" />
                </NFormItem>
                <NFormItem
                  v-for="field in customFields"
                  :key="field.id"
                  :label="field.name"
                  :required="field.is_required"
                >
                  <NSelect
                    v-if="field.field_format === 'list'"
                    v-model:value="form.custom_values[field.id]"
                    :options="customFieldOptions(field)"
                    :multiple="field.multiple"
                    clearable
                    placeholder="请选择"
                  />
                  <NCheckbox
                    v-else-if="field.field_format === 'bool'"
                    v-model:checked="form.custom_values[field.id]"
                  >
                    是
                  </NCheckbox>
                  <NInputNumber
                    v-else-if="['int', 'float', 'user', 'version'].includes(field.field_format)"
                    v-model:value="form.custom_values[field.id]"
                    clearable
                    :precision="field.field_format === 'float' ? undefined : 0"
                    placeholder="请输入"
                    style="width: 100%"
                  />
                  <input
                    v-else-if="field.field_format === 'date'"
                    v-model="form.custom_values[field.id]"
                    class="native-date-input"
                    type="date"
                  />
                  <NInput
                    v-else-if="field.field_format === 'text'"
                    v-model:value="form.custom_values[field.id]"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 5 }"
                    placeholder="请输入"
                  />
                  <NInput
                    v-else
                    v-model:value="form.custom_values[field.id]"
                    clearable
                    placeholder="请输入"
                  />
                </NFormItem>
                <NFormItem class="span-full" label="描述">
                  <RichTextEditor
                    v-if="editDescriptionVisible"
                    v-model="form.description"
                    placeholder="请输入描述"
                    :min-height="220"
                    :max-height="460"
                  />
                  <NButton v-else text type="primary" @click="editDescriptionVisible = true">
                    详情
                  </NButton>
                </NFormItem>
                <NFormItem label="说明" class="span-full">
                  <NInput
                    v-model:value="form.notes"
                    type="textarea"
                    :autosize="{ minRows: 4, maxRows: 8 }"
                    placeholder=""
                  />
                </NFormItem>
              </NForm>
              <div class="actions">
                <NButton @click="editing = false">
                  <template #icon>
                    <TheIcon icon="mdi-content-save-cog-outline" :size="16" />
                  </template>
                  取消
                </NButton>
                <NButton :loading="saving" type="primary" @click="submitUpdate">
                  <template #icon>
                    <TheIcon icon="mdi-content-save-cog-outline" :size="17" />
                  </template>
                  提交更新
                </NButton>
              </div>
            </section>

            <section id="issue-history" class="issue-section">
              <div class="section-head">
                <div>
                  <span>HISTORY</span>
                  <h2>历史记录</h2>
                </div>
                <NTag size="small" :bordered="false">{{ issue.journals?.length || 0 }} 条</NTag>
              </div>
              <div v-if="issue.journals?.length" class="journal-list">
                <div v-for="journal in issue.journals" :key="journal.id" class="journal-item">
                  <div class="journal-head">
                    <strong>{{ journal.user_name || journal.user_id || '-' }}</strong>
                    <span>{{ journal.created_at || '-' }}</span>
                    <NTag v-if="journal.private_notes" size="small" type="warning">私有</NTag>
                  </div>
                  <!-- sanitized with sanitizeHtml before rendering -->
                  <!-- eslint-disable vue/no-v-html -->
                  <div
                    v-if="journal.notes"
                    class="journal-notes"
                    v-html="sanitizeHtml(journal.notes)"
                  ></div>
                  <!-- eslint-enable vue/no-v-html -->
                  <ul v-if="visibleJournalDetails(journal).length" class="journal-details">
                    <li v-for="detail in visibleJournalDetails(journal)" :key="detail.id">
                      {{ detailLabel(detail) }}:
                      {{ detailValue(detail) }}
                    </li>
                  </ul>
                </div>
              </div>
              <NAlert v-else type="default">暂无历史记录</NAlert>
            </section>
          </main>
        </div>
      </template>
    </div>
  </component>
  <NModal
    v-model:show="descriptionImagePreviewVisible"
    preset="card"
    title="图片预览"
    class="description-image-modal"
  >
    <div class="description-image-preview">
      <img :src="descriptionImagePreviewSrc" :alt="descriptionImagePreviewAlt" />
    </div>
  </NModal>
</template>

<style scoped>
.issue-detail-page {
  --issue-accent: #0f766e;
  --issue-accent-soft: #e8f5f1;
  --issue-border: #e5e7eb;
  --issue-muted: #64748b;
  --issue-ink: #111827;
  color: var(--issue-ink);
  min-height: calc(100vh - 150px);
}

.issue-detail-page.is-embedded {
  min-height: auto;
  padding: 0 22px 22px;
}

.loading-state,
.journal-head,
.actions {
  display: flex;
  align-items: center;
}

.loading-state {
  justify-content: center;
  gap: 10px;
  min-height: 260px;
  color: #64748b;
}

.issue-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  padding: 18px;
  border: 1px solid #dbe8e5;
  border-radius: 8px;
  background: #f8fffd;
}

.issue-hero-main {
  min-width: 0;
}

.issue-hero h1 {
  margin: 0;
  color: var(--issue-ink);
  font-size: 25px;
  line-height: 1.35;
  word-break: break-word;
}

.issue-subline {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
  color: var(--issue-muted);
  font-size: 12px;
}

.issue-subline-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
}

.issue-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  background: #f8fafc;
  color: #475569;
  font-weight: 600;
  line-height: 1.4;
}

.issue-pill.is-phase {
  border-color: #a7f3d0;
  background: #ecfdf5;
  color: #047857;
}

.issue-pill.is-tracker {
  border-color: #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
}

.issue-pill.is-status {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #c2410c;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.detail-layout {
  margin-top: 4px;
}

.issue-section {
  padding: 18px 0;
  border-bottom: 1px solid #edf2f7;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-head span {
  color: var(--issue-accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
}

.section-head h2 {
  margin: 2px 0 0;
  color: var(--issue-ink);
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
}

.update-form {
  display: grid;
  gap: 10px;
}

.update-form {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.description,
.journal-notes {
  color: #1f2937;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.description {
  min-height: 120px;
  padding: 15px 16px;
  border: 1px solid #cfe8df;
  border-left: 5px solid var(--issue-accent);
  border-radius: 8px;
  background: #f8fffd;
}

.description.is-collapsed {
  max-height: 120px;
  overflow: hidden;
}

.description :deep(img) {
  display: inline-block;
  max-width: min(180px, 100%);
  max-height: 140px;
  width: auto;
  height: auto;
  margin: 8px 8px 8px 0;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  object-fit: contain;
  vertical-align: top;
  cursor: zoom-in;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
}

.description-image-modal {
  width: min(92vw, 960px);
}

.description-image-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  max-height: 78vh;
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  background: #0f172a;
}

.description-image-preview img {
  display: block;
  max-width: 100%;
  max-height: 74vh;
  object-fit: contain;
}

.update-section {
  margin: 18px 0;
  padding: 16px;
  border: 1px solid var(--issue-border);
  border-radius: 8px;
  background: #fbfdff;
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

.span-full {
  grid-column: 1 / -1;
}

.actions {
  justify-content: flex-end;
}

.attachment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.attachment-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--issue-border);
  border-radius: 8px;
  background: #fff;
}

.attachment-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.image-preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.image-preview-item {
  display: block;
  overflow: hidden;
  border: 1px solid var(--issue-border);
  border-radius: 8px;
  background: #fff;
}

.image-preview-item img {
  display: block;
  width: 100%;
  height: 120px;
  object-fit: cover;
}

.attachment-name {
  color: var(--issue-ink);
  font-weight: 700;
  word-break: break-word;
}

.attachment-meta {
  margin-top: 4px;
  color: var(--issue-muted);
  font-size: 12px;
}

.journal-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-left: 12px;
  border-left: 2px solid #dbeafe;
}

.journal-item {
  position: relative;
  padding: 12px 14px;
  border: 1px solid var(--issue-border);
  border-radius: 8px;
  background: #fff;
}

.journal-item::before {
  position: absolute;
  top: 17px;
  left: -18px;
  width: 8px;
  height: 8px;
  border: 2px solid #fff;
  border-radius: 999px;
  background: #2563eb;
  box-shadow: 0 0 0 2px #dbeafe;
  content: '';
}

.journal-head {
  flex-wrap: wrap;
  gap: 10px;
  color: var(--issue-muted);
  font-size: 12px;
}

.journal-head strong {
  color: var(--issue-ink);
  font-size: 13px;
}

.journal-notes {
  margin-top: 8px;
}

.journal-details {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #475569;
  line-height: 1.8;
}

@media (max-width: 1100px) {
  .issue-hero {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 640px) {
  .issue-hero {
    padding: 14px;
  }

  .issue-hero h1 {
    font-size: 22px;
  }

  .detail-actions {
    justify-content: flex-start;
  }

  .update-form {
    grid-template-columns: minmax(0, 1fr);
  }

  .attachment-item {
    align-items: stretch;
    flex-direction: column;
  }

  .attachment-actions {
    justify-content: flex-start;
  }
}
</style>
