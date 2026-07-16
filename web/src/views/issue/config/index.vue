<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NCheckbox,
  NCheckboxGroup,
  NDataTable,
  NDynamicTags,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { useAppStore } from '@/store'

defineOptions({ name: '工单配置' })

const tab = ref('system_config')
const loading = ref(false)
const saving = ref(false)
const settingsLoading = ref(false)
const settingsSaving = ref(false)
const settingsFormRef = ref(null)
const modalVisible = ref(false)
const editingType = ref('workflows')
const modalForm = ref({})
const config = ref(emptyConfig())
const appStore = useAppStore()
const fullSettings = ref({})
const issueSettings = ref(defaultIssueSettings())
const csReviewPhaseDraggingValue = ref(null)

const SortableTags = {
  name: 'SortableTags',
  props: {
    value: { type: Array, default: () => [] },
  },
  emits: ['update:value'],
  setup(props, { emit }) {
    const draggingIndex = ref(-1)
    const update = (value) => emit('update:value', value)
    const reorder = (from, to) => {
      const list = [...(props.value || [])]
      if (from < 0 || to < 0 || from === to || from >= list.length || to >= list.length) return
      const [item] = list.splice(from, 1)
      list.splice(to, 0, item)
      update(list)
    }
    const remove = (index) => {
      const list = [...(props.value || [])]
      list.splice(index, 1)
      update(list)
    }
    const renderTag = (tag, index) =>
      h(
        NTag,
        {
          key: `${tag}-${index}`,
          class: ['sortable-tag', draggingIndex.value === index ? 'is-dragging' : ''],
          closable: true,
          draggable: true,
          onClose: () => remove(index),
          onDragstart: (event) => {
            draggingIndex.value = index
            event.dataTransfer.effectAllowed = 'move'
          },
          onDragover: (event) => {
            event.preventDefault()
            event.dataTransfer.dropEffect = 'move'
          },
          onDrop: (event) => {
            event.preventDefault()
            reorder(draggingIndex.value, index)
            draggingIndex.value = -1
          },
          onDragend: () => {
            draggingIndex.value = -1
          },
        },
        { default: () => (typeof tag === 'string' ? tag : tag.label) },
      )
    return () =>
      h(NDynamicTags, {
        class: 'sortable-tags',
        value: props.value || [],
        renderTag,
        'onUpdate:value': update,
      })
  },
}

const ticketNotifyRoles = [
  { label: '用户', value: '用户' },
  { label: '渠道商', value: '代理商' },
  { label: '客服', value: '客服' },
  { label: '技术', value: '技术' },
  { label: '产品', value: '产品' },
  { label: '测试', value: '测试' },
  { label: '研发', value: '研发' },
]

const ticketNotifyRoleOptions = {
  用户: [
    { label: '客服驳回', value: 'cs_rejected' },
    { label: '技术驳回', value: 'tech_rejected' },
    { label: '待关闭', value: 'pending_close' },
    { label: '处理完成', value: 'done' },
  ],
  代理商: [
    { label: '客服驳回', value: 'cs_rejected' },
    { label: '技术驳回', value: 'tech_rejected' },
    { label: '待关闭', value: 'pending_close' },
    { label: '处理完成', value: 'done' },
  ],
  客服: [{ label: '商务审核', value: 'pending_review' }],
  技术: [
    { label: '待技术处理', value: 'tech_processing' },
    { label: '现场验证', value: 'field_verification' },
  ],
  产品: [{ label: '产品评估', value: 'product_evaluation' }],
  测试: [
    { label: '测试过滤', value: 'test_filtering' },
    { label: '测试验证', value: 'test_verification' },
  ],
  研发: [{ label: '研发修改', value: 'rd_processing' }],
}

const settingsRules = {
  ticket_attachment_extensions: listRule('请至少配置一个允许上传类型'),
  ticket_project_phases: listRule('请至少配置一个项目阶段'),
  ticket_cs_review_project_phases: {
    required: true,
    validator: () => {
      if (!cleanList(issueSettings.value.ticket_cs_review_project_phases).length) {
        return new Error('请至少配置一个客服审核阶段')
      }
      const phases = new Set(cleanList(issueSettings.value.ticket_project_phases))
      const invalid = cleanList(issueSettings.value.ticket_cs_review_project_phases).filter(
        (item) => !phases.has(item),
      )
      return invalid.length ? new Error('客服审核阶段必须包含在项目阶段中') : true
    },
    trigger: ['change', 'blur'],
  },
  ticket_impact_scopes: listRule('请至少配置一个影响范围'),
  ticket_categories: listRule('请至少配置一个问题分类'),
  ticket_root_causes: listRule('请至少配置一个问题根因'),
  ticket_description_templates: listRule('请至少配置一个问题描述模板'),
  ticket_issue_types: listRule('请至少配置一个跟踪'),
  ticket_statuses: listRule('请至少配置一个状态'),
  ticket_priorities: listRule('请至少配置一个优先级'),
}

const sectionMap = {
  workflows: {
    title: '工作流',
    button: '新增权限',
    hint: '按角色定义可操作的状态流转权限',
    save: api.saveIssueWorkflowConfig,
    defaults: () => ({
      role_id: null,
      tracker_id: null,
      old_status_id: null,
      new_status_ids: [],
      assignee_required: true,
      author_allowed: true,
      assignee_allowed: true,
    }),
  },
  custom_fields: {
    title: '自定义字段',
    button: '新增字段',
    hint: '维护工单表单字段、显示排序、筛选和搜索能力',
    save: api.saveIssueCustomFieldConfig,
    defaults: () => ({
      type: 'issue',
      name: '',
      field_format: 'string',
      possible_values: [],
      default_value: '',
      is_required: false,
      is_filter: false,
      show_in_list: false,
      searchable: false,
      multiple: false,
      visible: true,
      position: nextPosition('custom_fields'),
    }),
  },
}

const submitSectionMap = {
  system_config: {
    title: '系统配置',
    hint: '维护商务审核、附件类型等提交基础规则',
  },
  issue_config: {
    title: '工单配置',
    hint: '维护工单选项顺序、分类、根因和描述模板',
  },
  submit_notify: {
    title: '提醒规则',
    hint: '按角色维护需要触达的工单节点',
  },
}

const activeStatuses = computed(() =>
  (config.value.statuses || []).filter((item) => item.active !== false),
)
const statusOptions = computed(() => {
  const allowed = new Set(cleanList(issueSettings.value.ticket_statuses))
  return toOptions(activeStatuses.value.filter((item) => !allowed.size || allowed.has(item.name)))
})
const trackerOptions = computed(() => {
  const allowed = new Set(cleanList(issueSettings.value.ticket_issue_types))
  return toOptions(
    (config.value.trackers || []).filter(
      (item) => item.is_active !== false && (!allowed.size || allowed.has(item.name)),
    ),
  )
})
const roleOptions = computed(() => toOptions(config.value.roles))
const fieldFormatLabels = {
  string: '单行文本',
  text: '多行文本',
  date: '日期',
  list: '列表',
}
const fieldFormatOptions = computed(() =>
  (config.value.field_formats || [])
    .filter((item) => Object.prototype.hasOwnProperty.call(fieldFormatLabels, item.value))
    .map((item) => ({ ...item, label: fieldFormatLabels[item.value] })),
)
const statusMap = computed(() => toNameMap(config.value.statuses))
const trackerMap = computed(() => toNameMap(config.value.trackers))
const roleMap = computed(() => toNameMap(config.value.roles))
const currentSection = computed(() => sectionMap[editingType.value] || sectionMap.workflows)
const drawerTitle = computed(
  () =>
    `${modalForm.value?._editing || modalForm.value?.id ? '编辑' : '新增'}${currentSection.value.title}`,
)
const drawerWidth = computed(() =>
  editingType.value === 'workflows' || editingType.value === 'custom_fields' ? 760 : 680,
)
const activeSection = computed(
  () => sectionMap[tab.value] || submitSectionMap[tab.value] || submitSectionMap.system_config,
)
const projectPhaseOptions = computed(() =>
  cleanList(issueSettings.value.ticket_project_phases).map((item) => ({
    label: item,
    value: item,
  })),
)
const submitEntryCount = computed(() =>
  settingListCount(['ticket_attachment_extensions', 'ticket_cs_review_project_phases']),
)
const submitContentCount = computed(() =>
  settingListCount([
    'ticket_project_phases',
    'ticket_issue_types',
    'ticket_statuses',
    'ticket_priorities',
    'ticket_impact_scopes',
    'ticket_categories',
    'ticket_root_causes',
    'ticket_description_templates',
  ]),
)
const submitNotifyCount = computed(() =>
  Object.values(issueSettings.value.ticket_notify_by_role || {}).reduce(
    (total, items) => total + cleanList(items).length,
    0,
  ),
)
const possibleValueText = computed({
  get: () => (modalForm.value.possible_values || []).join('\n'),
  set: (value) => {
    modalForm.value.possible_values = String(value || '')
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean)
  },
})
const workflowRoleGroups = computed(() => {
  const groups = new Map()
  const activeStatusIds = new Set(activeStatuses.value.map((item) => Number(item.id || 0)))
  const activeTrackerIds = new Set(
    (config.value.trackers || [])
      .filter((item) => item.is_active !== false)
      .map((item) => Number(item.id || 0)),
  )
  ;(config.value.workflows || []).forEach((row) => {
    const roleId = Number(row.role_id || 0)
    const trackerId = Number(row.tracker_id || 0)
    const oldStatusId = Number(row.old_status_id || 0)
    const newStatusId = Number(row.new_status_id || 0)
    if (
      !activeTrackerIds.has(trackerId) ||
      !activeStatusIds.has(oldStatusId) ||
      !activeStatusIds.has(newStatusId)
    ) {
      return
    }
    if (!groups.has(roleId))
      groups.set(roleId, { id: roleId, name: nameOf(roleMap, roleId), rows: [] })
    const group = groups.get(roleId)
    const key = `${roleId}-${trackerId}-${oldStatusId}`
    let merged = group.rows.find((item) => item.key === key)
    if (!merged) {
      merged = {
        key,
        _editing: true,
        role_id: roleId,
        tracker_id: trackerId,
        old_status_id: oldStatusId,
        new_status_ids: [],
        assignee_required: row.assignee_required,
        author_allowed: row.author_allowed,
        assignee_allowed: row.assignee_allowed,
      }
      group.rows.push(merged)
    }
    if (newStatusId && !merged.new_status_ids.includes(newStatusId)) {
      merged.new_status_ids.push(newStatusId)
    }
  })
  return [...groups.values()]
})
const workflowCount = computed(() =>
  workflowRoleGroups.value.reduce((total, group) => total + group.rows.length, 0),
)

const customFieldColumns = [
  { title: '排序', key: 'position', width: 80, align: 'center' },
  { title: '名称', key: 'name', minWidth: 150, render: (row) => nameCell(row.name) },
  {
    title: '格式',
    key: 'field_format',
    width: 110,
    render: (row) => valueTag(fieldFormatLabels[row.field_format] || row.field_format, 'default'),
  },
  {
    title: '必填',
    key: 'is_required',
    width: 80,
    align: 'center',
    render: (row) => booleanTag(row.is_required),
  },
  {
    title: '筛选',
    key: 'is_filter',
    width: 80,
    align: 'center',
    render: (row) => booleanTag(row.is_filter),
  },
  {
    title: '列表',
    key: 'show_in_list',
    width: 80,
    align: 'center',
    render: (row) => booleanTag(row.show_in_list),
  },
  {
    title: '可见',
    key: 'visible',
    width: 80,
    align: 'center',
    render: (row) => booleanTag(row.visible),
  },
  actionColumn('custom_fields'),
]

onMounted(() => {
  loadConfig()
  loadIssueSettings()
})

function emptyConfig() {
  return {
    trackers: [],
    statuses: [],
    priorities: [],
    workflows: [],
    custom_fields: [],
    roles: [],
    field_formats: [],
  }
}

function defaultIssueSettings() {
  return {
    customer_service_auto_approve_ticket: false,
    ticket_attachment_extensions: [
      'zip',
      'rar',
      'png',
      'jpg',
      'jpeg',
      'gif',
      'docx',
      'pptx',
      'xlsx',
    ],
    ticket_project_phases: ['售前', '实施', '售后'],
    ticket_cs_review_project_phases: ['实施', '售后'],
    ticket_issue_types: ['现网问题', '现网需求'],
    ticket_statuses: [
      '新建',
      '商务审核',
      '技术处理',
      '测试过滤',
      '研发修改',
      '测试验证',
      '现场验证',
      '产品评估',
      '问题转需求',
      '关闭',
    ],
    ticket_priorities: ['高', '中', '低'],
    ticket_impact_scopes: ['全部', '偶现', '单台必现', '单台偶现'],
    ticket_categories: ['登录问题', '权限问题', '系统异常', '其他'],
    ticket_root_causes: ['代码缺陷', '配置错误', '环境异常', '数据问题', '操作不当', '第三方依赖'],
    ticket_description_templates: ['问题现象：\n复现步骤：\n期望结果：\n实际结果：\n影响范围：'],
    project_products: ['安得卫士'],
    project_statuses: ['售前', '待实施', '实施中', '待验收', '已验收', '关闭'],
    project_regions: ['华东', '华南', '华北', '华中', '西南', '西北'],
    project_activity_types: ['迁移库', '重做系统', '运维', '其他'],
    project_server_versions: ['5.6.1'],
    project_client_versions: ['2.25'],
    ticket_notify_by_role: {
      用户: ['cs_rejected', 'tech_rejected', 'pending_close', 'done'],
      代理商: ['cs_rejected', 'tech_rejected', 'pending_close', 'done'],
      客服: ['pending_review'],
      技术: ['tech_processing', 'field_verification'],
      产品: ['product_evaluation'],
      测试: ['test_filtering', 'test_verification'],
      研发: ['rd_processing'],
    },
  }
}

function cleanList(items, { lower = false } = {}) {
  const result = []
  ;(items || []).forEach((item) => {
    const text = String(item || '').trim()
    const value = lower ? text.toLowerCase().replace(/^\./, '') : text
    if (value && !result.includes(value)) result.push(value)
  })
  return result
}

function listRule(message) {
  return {
    required: true,
    validator: (_rule, value) => (cleanList(value).length ? true : new Error(message)),
    trigger: ['change', 'blur'],
  }
}

function normalizeTicketNotifyByRole(raw = {}) {
  const normalized = {}
  ticketNotifyRoles.forEach((role) => {
    const allowed = new Set((ticketNotifyRoleOptions[role.value] || []).map((item) => item.value))
    const selected = Array.isArray(raw[role.value])
      ? raw[role.value]
      : role.value === '代理商' && Array.isArray(raw['渠道商'])
        ? raw['渠道商']
        : []
    normalized[role.value] = selected.filter((item) => allowed.has(item))
  })
  return normalized
}

function mergeIssueSettings(data = {}) {
  const defaults = defaultIssueSettings()
  issueSettings.value = {
    ...defaults,
    ...data,
    ticket_attachment_extensions: cleanList(
      data.ticket_attachment_extensions?.length
        ? data.ticket_attachment_extensions
        : defaults.ticket_attachment_extensions,
      { lower: true },
    ),
    ticket_project_phases: cleanList(
      data.ticket_project_phases?.length
        ? data.ticket_project_phases
        : defaults.ticket_project_phases,
    ),
    ticket_cs_review_project_phases: cleanList(
      data.ticket_cs_review_project_phases?.length
        ? data.ticket_cs_review_project_phases
        : defaults.ticket_cs_review_project_phases,
    ),
    ticket_issue_types: cleanList(
      data.ticket_issue_types?.length ? data.ticket_issue_types : defaults.ticket_issue_types,
    ),
    ticket_statuses: cleanList(
      data.ticket_statuses?.length ? data.ticket_statuses : defaults.ticket_statuses,
    ),
    ticket_priorities: cleanList(
      data.ticket_priorities?.length ? data.ticket_priorities : defaults.ticket_priorities,
    ),
    ticket_impact_scopes: cleanList(
      data.ticket_impact_scopes?.length ? data.ticket_impact_scopes : defaults.ticket_impact_scopes,
    ),
    ticket_categories: cleanList(
      data.ticket_categories?.length ? data.ticket_categories : defaults.ticket_categories,
    ),
    ticket_root_causes: cleanList(
      data.ticket_root_causes?.length ? data.ticket_root_causes : defaults.ticket_root_causes,
    ),
    ticket_description_templates: cleanList(
      Array.isArray(data.ticket_description_templates) && data.ticket_description_templates.length
        ? data.ticket_description_templates
        : defaults.ticket_description_templates,
    ),
    project_products: cleanList(
      data.project_products?.length ? data.project_products : defaults.project_products,
    ),
    project_statuses: cleanList(
      data.project_statuses?.length ? data.project_statuses : defaults.project_statuses,
    ),
    project_regions: cleanList(
      data.project_regions?.length ? data.project_regions : defaults.project_regions,
    ),
    project_activity_types: cleanList(
      data.project_activity_types?.length
        ? data.project_activity_types
        : defaults.project_activity_types,
    ),
    project_server_versions: cleanList(
      data.project_server_versions?.length
        ? data.project_server_versions
        : defaults.project_server_versions,
    ),
    project_client_versions: cleanList(
      data.project_client_versions?.length
        ? data.project_client_versions
        : defaults.project_client_versions,
    ),
    ticket_notify_by_role: normalizeTicketNotifyByRole(
      data.ticket_notify_by_role || defaults.ticket_notify_by_role,
    ),
  }
}

function issueSettingsPayload() {
  return {
    ...issueSettings.value,
    ticket_attachment_extensions: cleanList(issueSettings.value.ticket_attachment_extensions, {
      lower: true,
    }),
    ticket_project_phases: cleanList(issueSettings.value.ticket_project_phases),
    ticket_cs_review_project_phases: cleanList(issueSettings.value.ticket_cs_review_project_phases),
    ticket_issue_types: cleanList(issueSettings.value.ticket_issue_types),
    ticket_statuses: cleanList(issueSettings.value.ticket_statuses),
    ticket_priorities: cleanList(issueSettings.value.ticket_priorities),
    ticket_impact_scopes: cleanList(issueSettings.value.ticket_impact_scopes),
    ticket_categories: cleanList(issueSettings.value.ticket_categories),
    ticket_root_causes: cleanList(issueSettings.value.ticket_root_causes),
    ticket_description_templates: cleanList(issueSettings.value.ticket_description_templates),
    project_products: cleanList(issueSettings.value.project_products),
    project_statuses: cleanList(issueSettings.value.project_statuses),
    project_regions: cleanList(issueSettings.value.project_regions),
    project_activity_types: cleanList(issueSettings.value.project_activity_types),
    project_server_versions: cleanList(issueSettings.value.project_server_versions),
    project_client_versions: cleanList(issueSettings.value.project_client_versions),
    ticket_notify_by_role: normalizeTicketNotifyByRole(issueSettings.value.ticket_notify_by_role),
  }
}

function toOptions(items) {
  return (items || []).map((item) => ({ label: item.name, value: item.id }))
}

function toNameMap(items) {
  return Object.fromEntries((items || []).map((item) => [Number(item.id), item.name]))
}

function nameOf(source, id) {
  return source.value[Number(id)] || id || '-'
}

function booleanTag(value) {
  return h(
    NTag,
    { size: 'small', type: value ? 'success' : 'default', bordered: false },
    { default: () => (value ? '是' : '否') },
  )
}

function valueTag(value, type = 'default') {
  return h(NTag, { size: 'small', type, bordered: false }, { default: () => value || '-' })
}

function workflowLine(row) {
  const targets = (row.new_status_ids || []).map((id) => nameOf(statusMap, id)).join('、')
  return `${nameOf(trackerMap, row.tracker_id)}：${nameOf(statusMap, row.old_status_id)} → ${targets || '-'}`
}

function nameCell(value) {
  return h('span', { class: 'config-name-cell' }, value || '-')
}

function sectionCount(key) {
  return config.value?.[key]?.length || 0
}

function settingListCount(keys) {
  return keys.reduce((total, key) => total + cleanList(issueSettings.value[key]).length, 0)
}

function cleanIdList(items) {
  const result = []
  ;(items || []).forEach((item) => {
    const id = Number(item || 0)
    if (id > 0 && !result.includes(id)) result.push(id)
  })
  return result
}

const templateDraggingIndex = ref(-1)

function reorderSettingItem(key, from, to) {
  const list = [...(issueSettings.value[key] || [])]
  if (from < 0 || to < 0 || from === to || from >= list.length || to >= list.length) return
  const [item] = list.splice(from, 1)
  list.splice(to, 0, item)
  issueSettings.value[key] = list
}

function renderCsReviewPhaseTag({ option, handleClose }) {
  const value = option.value
  const list = issueSettings.value.ticket_cs_review_project_phases || []
  const index = list.indexOf(value)
  return h(
    NTag,
    {
      class: ['sortable-tag', csReviewPhaseDraggingValue.value === value ? 'is-dragging' : ''],
      closable: true,
      draggable: true,
      onClose: handleClose,
      onDragstart: (event) => {
        csReviewPhaseDraggingValue.value = value
        event.dataTransfer.effectAllowed = 'move'
      },
      onDragover: (event) => {
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'
      },
      onDrop: (event) => {
        event.preventDefault()
        reorderSettingItem(
          'ticket_cs_review_project_phases',
          list.indexOf(csReviewPhaseDraggingValue.value),
          index,
        )
        csReviewPhaseDraggingValue.value = null
      },
      onDragend: () => {
        csReviewPhaseDraggingValue.value = null
      },
    },
    { default: () => option.label || value },
  )
}

function startTemplateDrag(event, index) {
  templateDraggingIndex.value = index
  event.dataTransfer.effectAllowed = 'move'
}

function dropTemplate(index) {
  reorderSettingItem('ticket_description_templates', templateDraggingIndex.value, index)
  templateDraggingIndex.value = -1
}

function actionColumn(type) {
  return {
    title: '操作',
    key: 'actions',
    width: 90,
    align: 'center',
    fixed: 'right',
    render(row) {
      return h(
        NButton,
        { size: 'small', type: 'primary', secondary: true, onClick: () => openEditor(type, row) },
        {
          icon: () => h(TheIcon, { icon: 'material-symbols:edit-outline', size: 16 }),
          default: () => '编辑',
        },
      )
    },
  }
}

function nextPosition(key) {
  const rows = config.value?.[key] || []
  return rows.length ? Math.max(...rows.map((item) => Number(item.position || 0))) + 1 : 1
}

async function loadConfig() {
  loading.value = true
  try {
    const res = await api.getIssueAdminConfig()
    config.value = { ...emptyConfig(), ...(res?.data || {}) }
    config.value.custom_fields = (config.value.custom_fields || []).filter((item) => item.type === 'issue')
  } finally {
    loading.value = false
  }
}

async function loadIssueSettings() {
  settingsLoading.value = true
  try {
    const res = await api.getSystemSettings()
    fullSettings.value = res?.data || {}
    mergeIssueSettings(fullSettings.value)
  } finally {
    settingsLoading.value = false
  }
}

function saveIssueSettings() {
  settingsFormRef.value?.validate(async (err) => {
    if (err) return
    settingsSaving.value = true
    try {
      const payload = {
        ...fullSettings.value,
        ...issueSettingsPayload(),
      }
      await api.updateSystemSettings(payload)
      $message.success('工单配置已保存')
      const publicRes = await api.getAppConfig()
      appStore.setSiteConfig(publicRes.data || {})
      await loadIssueSettings()
      await loadConfig()
    } finally {
      settingsSaving.value = false
    }
  })
}

function addDescriptionTemplate() {
  issueSettings.value.ticket_description_templates.push('')
}

function removeDescriptionTemplate(index) {
  if ((issueSettings.value.ticket_description_templates || []).length <= 1) {
    $message.warning('至少保留一个问题描述模板')
    return
  }
  issueSettings.value.ticket_description_templates.splice(index, 1)
}

function openEditor(type, row = null) {
  editingType.value = type
  modalForm.value = row
    ? {
        ...row,
        _editing: true,
        new_status_ids: cleanIdList(
          row.new_status_ids || (row.new_status_id ? [row.new_status_id] : []),
        ),
      }
    : sectionMap[type].defaults()
  modalVisible.value = true
}

async function saveCurrent() {
  if (!modalForm.value.name?.trim() && editingType.value !== 'workflows') {
    $message.warning('请输入名称')
    return
  }
  if (editingType.value === 'workflows') {
    const requiredFields = ['role_id', 'tracker_id', 'old_status_id']
    if (requiredFields.some((field) => !modalForm.value[field])) {
      $message.warning('请选择完整流转')
      return
    }
    if (!cleanIdList(modalForm.value.new_status_ids).length) {
      $message.warning('请选择可操作到的状态')
      return
    }
  }
  saving.value = true
  try {
    const payload = { ...modalForm.value }
    if (payload.name) payload.name = payload.name.trim()
    if (editingType.value === 'workflows') {
      payload.new_status_ids = cleanIdList(payload.new_status_ids)
      payload.new_status_id = payload.new_status_ids[0]
      delete payload.id
      delete payload.key
      delete payload._editing
    }
    if (editingType.value === 'custom_fields' && payload.field_format !== 'list') {
      payload.possible_values = []
      payload.multiple = false
    }
    await currentSection.value.save(payload)
    $message.success('保存成功')
    modalVisible.value = false
    await loadConfig()
  } finally {
    saving.value = false
  }
}

async function deleteWorkflow(row) {
  await currentSection.value.save({
    role_id: row.role_id,
    tracker_id: row.tracker_id,
    old_status_id: row.old_status_id,
    new_status_ids: [],
  })
  $message.success('删除成功')
  await loadConfig()
}
</script>

<template>
  <CommonPage title="工单配置" :show-header="false" show-footer>
    <div class="issue-config-page">
      <div class="config-shell">
        <NForm
          ref="settingsFormRef"
          :model="issueSettings"
          :rules="settingsRules"
          label-placement="top"
        >
          <NTabs v-model:value="tab" type="line" animated>
            <NTabPane name="system_config">
              <template #tab>
                <span class="tab-label"
                  >系统配置 <em>{{ submitEntryCount }}</em></span
                >
              </template>
              <div class="section-toolbar">
                <div class="section-copy">
                  <strong>{{ activeSection.title }}</strong>
                  <span>{{ activeSection.hint }}</span>
                </div>
                <NButton
                  type="primary"
                  :disabled="settingsLoading"
                  :loading="settingsSaving"
                  @click="saveIssueSettings"
                >
                  <template #icon>
                    <TheIcon icon="mdi-content-save-cog-outline" :size="17" />
                  </template>
                  保存配置
                </NButton>
              </div>
              <section class="submit-section">
                <div class="settings-grid">
                  <NFormItem label="客服自动审批工单">
                    <NSwitch v-model:value="issueSettings.customer_service_auto_approve_ticket" />
                  </NFormItem>
                  <NFormItem label="附件类型" path="ticket_attachment_extensions">
                    <SortableTags v-model:value="issueSettings.ticket_attachment_extensions" />
                  </NFormItem>
                  <NFormItem label="客服审核阶段" path="ticket_cs_review_project_phases">
                    <div class="select-sort">
                      <NSelect
                        v-model:value="issueSettings.ticket_cs_review_project_phases"
                        clearable
                        filterable
                        multiple
                        :options="projectPhaseOptions"
                        placeholder="从项目阶段中选择"
                        :render-tag="renderCsReviewPhaseTag"
                      />
                    </div>
                  </NFormItem>
                </div>
              </section>
            </NTabPane>

            <NTabPane name="issue_config">
              <template #tab>
                <span class="tab-label"
                  >工单配置 <em>{{ submitContentCount }}</em></span
                >
              </template>
              <div class="section-toolbar">
                <div class="section-copy">
                  <strong>{{ activeSection.title }}</strong>
                  <span>{{ activeSection.hint }}</span>
                </div>
                <NButton
                  type="primary"
                  :disabled="settingsLoading"
                  :loading="settingsSaving"
                  @click="saveIssueSettings"
                >
                  <template #icon>
                    <TheIcon icon="mdi-content-save-cog-outline" :size="17" />
                  </template>
                  保存配置
                </NButton>
              </div>
              <section class="submit-section">
                <div class="settings-grid">
                  <NFormItem label="项目阶段" path="ticket_project_phases">
                    <SortableTags v-model:value="issueSettings.ticket_project_phases" />
                  </NFormItem>
                  <NFormItem label="跟踪" path="ticket_issue_types">
                    <SortableTags v-model:value="issueSettings.ticket_issue_types" />
                  </NFormItem>
                  <NFormItem label="状态" path="ticket_statuses">
                    <SortableTags v-model:value="issueSettings.ticket_statuses" />
                  </NFormItem>
                  <NFormItem label="优先级" path="ticket_priorities">
                    <SortableTags v-model:value="issueSettings.ticket_priorities" />
                  </NFormItem>
                  <NFormItem label="影响范围" path="ticket_impact_scopes">
                    <SortableTags v-model:value="issueSettings.ticket_impact_scopes" />
                  </NFormItem>
                  <NFormItem label="问题分类" path="ticket_categories">
                    <SortableTags v-model:value="issueSettings.ticket_categories" />
                  </NFormItem>
                  <NFormItem label="问题根因" path="ticket_root_causes">
                    <SortableTags v-model:value="issueSettings.ticket_root_causes" />
                  </NFormItem>
                  <NFormItem
                    label="问题描述模板"
                    path="ticket_description_templates"
                    class="span-full"
                  >
                    <div class="template-editor">
                      <div
                        v-for="(item, index) in issueSettings.ticket_description_templates"
                        :key="index"
                        class="template-item"
                        :class="{ 'is-dragging': templateDraggingIndex === index }"
                        draggable="true"
                        @dragstart="startTemplateDrag($event, index)"
                        @dragover.prevent
                        @drop.prevent="dropTemplate(index)"
                        @dragend="templateDraggingIndex = -1"
                      >
                        <TheIcon
                          class="drag-handle"
                          icon="material-symbols:drag-indicator"
                          :size="17"
                        />
                        <NInput
                          v-model:value="issueSettings.ticket_description_templates[index]"
                          type="textarea"
                          :autosize="{ minRows: 3, maxRows: 6 }"
                          :placeholder="`模板 ${index + 1}`"
                        />
                        <div class="template-actions">
                          <NButton
                            quaternary
                            type="error"
                            size="small"
                            @click="removeDescriptionTemplate(index)"
                          >
                            删除
                          </NButton>
                        </div>
                      </div>
                      <NButton dashed @click="addDescriptionTemplate">新增模板</NButton>
                    </div>
                  </NFormItem>
                </div>
              </section>
            </NTabPane>

            <NTabPane name="submit_notify">
              <template #tab>
                <span class="tab-label"
                  >提醒规则 <em>{{ submitNotifyCount }}</em></span
                >
              </template>
              <div class="section-toolbar">
                <div class="section-copy">
                  <strong>{{ activeSection.title }}</strong>
                  <span>{{ activeSection.hint }}</span>
                </div>
                <NButton
                  type="primary"
                  :disabled="settingsLoading"
                  :loading="settingsSaving"
                  @click="saveIssueSettings"
                >
                  <template #icon>
                    <TheIcon icon="mdi-content-save-cog-outline" :size="17" />
                  </template>
                  保存配置
                </NButton>
              </div>
              <section class="submit-section">
                <div class="notify-grid">
                  <NFormItem
                    v-for="role in ticketNotifyRoles"
                    :key="role.value"
                    :label="`${role.label}提醒节点`"
                  >
                    <NCheckboxGroup v-model:value="issueSettings.ticket_notify_by_role[role.value]">
                      <div class="notify-options">
                        <NCheckbox
                          v-for="item in ticketNotifyRoleOptions[role.value]"
                          :key="item.value"
                          :value="item.value"
                        >
                          {{ item.label }}
                        </NCheckbox>
                      </div>
                    </NCheckboxGroup>
                  </NFormItem>
                </div>
              </section>
            </NTabPane>

            <NTabPane name="workflows">
              <template #tab>
                <span class="tab-label"
                  >工作流 <em>{{ workflowCount }}</em></span
                >
              </template>
              <div class="section-toolbar">
                <div class="section-copy">
                  <strong>{{ activeSection.title }}</strong>
                  <span>{{ activeSection.hint }}</span>
                </div>
                <NButton type="primary" @click="openEditor('workflows')">
                  <template #icon>
                    <TheIcon icon="mdi-content-save-cog-outline" :size="18" />
                  </template>
                  {{ sectionMap.workflows.button }}
                </NButton>
              </div>
              <div v-if="workflowRoleGroups.length" class="workflow-role-grid">
                <div v-for="group in workflowRoleGroups" :key="group.id" class="workflow-role-card">
                  <div class="workflow-role-head">
                    <strong>{{ group.name }}</strong>
                    <span>{{ group.rows.length }} 条权限</span>
                  </div>
                  <div class="workflow-role-items">
                    <div v-for="row in group.rows" :key="row.key" class="workflow-role-item">
                      <span>{{ workflowLine(row) }}</span>
                      <NSpace :size="4">
                        <NButton quaternary circle size="tiny" @click="openEditor('workflows', row)">
                          <template #icon>
                            <TheIcon icon="material-symbols:edit-outline" :size="15" />
                          </template>
                        </NButton>
                        <NPopconfirm @positive-click="deleteWorkflow(row)">
                          <template #trigger>
                            <NButton quaternary circle size="tiny" type="error">
                              <template #icon>
                                <TheIcon icon="material-symbols:delete-outline" :size="15" />
                              </template>
                            </NButton>
                          </template>
                          删除后该角色在当前状态下将无法执行这些流转，是否确认？
                        </NPopconfirm>
                      </NSpace>
                    </div>
                  </div>
                </div>
              </div>
            </NTabPane>

            <NTabPane name="custom_fields">
              <template #tab>
                <span class="tab-label"
                  >自定义字段 <em>{{ sectionCount('custom_fields') }}</em></span
                >
              </template>
              <div class="section-toolbar">
                <div class="section-copy">
                  <strong>{{ activeSection.title }}</strong>
                  <span>{{ activeSection.hint }}</span>
                </div>
                <NButton type="primary" @click="openEditor('custom_fields')">
                  <template #icon>
                    <TheIcon icon="mdi-content-save-cog-outline" :size="18" />
                  </template>
                  {{ sectionMap.custom_fields.button }}
                </NButton>
              </div>
              <NDataTable
                :loading="loading"
                :columns="customFieldColumns"
                :data="config.custom_fields"
                :scroll-x="1040"
              />
            </NTabPane>
          </NTabs>
        </NForm>
      </div>

      <NDrawer v-model:show="modalVisible" placement="right" :width="drawerWidth">
        <NDrawerContent closable :native-scrollbar="false" class="config-drawer">
          <template #header>
            <div class="drawer-title">
              <strong>{{ drawerTitle }}</strong>
            </div>
          </template>

          <NForm label-placement="top" class="drawer-form">
            <template v-if="editingType === 'workflows'">
              <section class="drawer-section">
                <div class="drawer-section-title">角色权限</div>
                <div class="drawer-grid">
                  <NFormItem label="可操作角色">
                    <NSelect v-model:value="modalForm.role_id" :options="roleOptions" clearable />
                  </NFormItem>
                  <NFormItem label="工单跟踪">
                    <NSelect
                      v-model:value="modalForm.tracker_id"
                      :options="trackerOptions"
                      clearable
                    />
                  </NFormItem>
                </div>
              </section>
              <section class="drawer-section">
                <div class="drawer-section-title">允许流转</div>
                <div class="drawer-grid">
                  <NFormItem label="当前状态">
                    <NSelect
                      v-model:value="modalForm.old_status_id"
                      :options="statusOptions"
                      clearable
                    />
                  </NFormItem>
                  <NFormItem label="可操作到">
                    <NSelect
                      v-model:value="modalForm.new_status_ids"
                      :options="statusOptions"
                      clearable
                      filterable
                      multiple
                    />
                  </NFormItem>
                </div>
              </section>
              <section class="drawer-section">
                <div class="drawer-section-title">执行约束</div>
                <div class="drawer-switches">
                  <NFormItem label="需指派">
                    <NSwitch v-model:value="modalForm.assignee_required" />
                  </NFormItem>
                  <NFormItem label="提交人可执行">
                    <NSwitch v-model:value="modalForm.author_allowed" />
                  </NFormItem>
                  <NFormItem label="指派人可执行">
                    <NSwitch v-model:value="modalForm.assignee_allowed" />
                  </NFormItem>
                </div>
              </section>
            </template>

            <template v-else>
              <section class="drawer-section">
                <div class="drawer-section-title">字段定义</div>
                <div class="drawer-grid">
                  <NFormItem label="名称">
                    <NInput v-model:value="modalForm.name" clearable />
                  </NFormItem>
                  <NFormItem label="排序">
                    <NInputNumber
                      v-model:value="modalForm.position"
                      :min="0"
                      :show-button="false"
                      style="width: 100%"
                    />
                  </NFormItem>
                  <NFormItem label="格式">
                    <NSelect v-model:value="modalForm.field_format" :options="fieldFormatOptions" />
                  </NFormItem>
                  <NFormItem label="默认值">
                    <NInput v-model:value="modalForm.default_value" clearable />
                  </NFormItem>
                  <NFormItem
                    v-if="modalForm.field_format === 'list'"
                    label="可选值"
                    class="span-full"
                  >
                    <NInput
                      v-model:value="possibleValueText"
                      type="textarea"
                      :autosize="{ minRows: 5, maxRows: 10 }"
                    />
                  </NFormItem>
                </div>
              </section>
              <section class="drawer-section">
                <div class="drawer-section-title">字段能力</div>
                <div class="drawer-switches">
                  <NFormItem label="必填">
                    <NSwitch v-model:value="modalForm.is_required" />
                  </NFormItem>
                  <NFormItem label="可筛选">
                    <NSwitch v-model:value="modalForm.is_filter" />
                  </NFormItem>
                  <NFormItem label="列表显示">
                    <NSwitch v-model:value="modalForm.show_in_list" />
                  </NFormItem>
                  <NFormItem label="多选">
                    <NSwitch v-model:value="modalForm.multiple" :disabled="modalForm.field_format !== 'list'" />
                  </NFormItem>
                  <NFormItem label="可见">
                    <NSwitch v-model:value="modalForm.visible" />
                  </NFormItem>
                </div>
              </section>
            </template>
          </NForm>

          <template #footer>
            <NSpace justify="end">
              <NButton @click="modalVisible = false">
                <template #icon>
                  <TheIcon icon="mdi-content-save-cog-outline" :size="16" />
                </template>
                取消
              </NButton>
              <NButton type="primary" :loading="saving" @click="saveCurrent">
                <template #icon>
                  <TheIcon icon="mdi-content-save-cog-outline" :size="17" />
                </template>
                保存
              </NButton>
            </NSpace>
          </template>
        </NDrawerContent>
      </NDrawer>
    </div>
  </CommonPage>
</template>

<style scoped>
.issue-config-page {
  --issue-accent: #0f766e;
  --issue-accent-soft: #e8f5f1;
  --issue-border: #e5e7eb;
  --issue-muted: #64748b;
  --issue-ink: #111827;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.config-shell {
  padding: 14px;
  border: 1px solid var(--issue-border);
  border-radius: 8px;
  background: linear-gradient(180deg, #f8fafc 0%, #fff 94px);
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tab-label em {
  min-width: 22px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--issue-accent-soft);
  color: var(--issue-accent);
  font-size: 11px;
  font-style: normal;
  line-height: 18px;
  text-align: center;
}

.section-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 220px;
}

.section-copy strong {
  color: var(--issue-ink);
  font-size: 15px;
}

.section-copy span {
  color: var(--issue-muted);
  font-size: 12px;
  line-height: 1.5;
}

.submit-section {
  padding: 14px 14px 2px;
  border: 1px solid var(--issue-border);
  border-radius: 8px;
  background: #fff;
}

.submit-section + .submit-section {
  margin-top: 12px;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.sortable-tags,
.select-sort {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.sortable-tag {
  cursor: grab;
}

.sortable-tag.is-dragging,
.template-item.is-dragging {
  opacity: 0.55;
}

.drag-handle {
  color: var(--issue-muted);
  cursor: grab;
}

.sortable-tag:active,
.template-item:active .drag-handle {
  cursor: grabbing;
}

.template-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.template-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.template-item {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: flex-start;
  padding: 4px 0;
}

.notify-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.notify-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(140px, 1fr));
  gap: 8px 12px;
}

:deep(.n-data-table-th) {
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}

:deep(.config-name-cell) {
  color: var(--issue-ink);
  font-weight: 700;
}

.workflow-role-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.workflow-role-card {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--issue-border);
  border-radius: 8px;
  background: #fff;
}

.workflow-role-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.workflow-role-head strong {
  color: var(--issue-ink);
  font-size: 14px;
}

.workflow-role-head span,
.workflow-role-item span {
  color: var(--issue-muted);
  font-size: 12px;
}

.workflow-role-items {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.workflow-role-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-height: 28px;
}

.workflow-role-item span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drawer-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.drawer-title strong {
  color: var(--issue-ink);
  font-size: 17px;
}

.drawer-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-section {
  padding: 14px 14px 2px;
  border: 1px solid var(--issue-border);
  border-radius: 8px;
  background: #fff;
}

.drawer-section-title {
  margin-bottom: 12px;
  color: var(--issue-ink);
  font-size: 14px;
  font-weight: 700;
}

.drawer-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.drawer-switches {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0 14px;
}

.span-full {
  grid-column: 1 / -1;
}

@media (max-width: 720px) {
  .section-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .settings-grid,
  .notify-grid,
  .notify-options,
  .template-item,
  .workflow-role-grid,
  .drawer-grid,
  .drawer-switches {
    grid-template-columns: minmax(0, 1fr);
  }

  .section-copy {
    min-width: 0;
  }
}
</style>
