<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NDynamicTags,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { useAppStore } from '@/store'

defineOptions({ name: '项目配置' })

const appStore = useAppStore()
const loading = ref(false)
const settingsSaving = ref(false)
const fieldSaving = ref(false)
const settingsFormRef = ref(null)
const fullSettings = ref({})
const settings = ref(defaultProjectSettings())
const customFields = ref([])
const fieldFormats = ref([])
const drawerVisible = ref(false)
const fieldForm = ref(defaultField())

const fieldFormatLabels = {
  string: '单行文本',
  text: '多行文本',
  date: '日期',
  list: '列表',
}
const fieldFormatOptions = computed(() =>
  (fieldFormats.value || [])
    .filter((item) => Object.prototype.hasOwnProperty.call(fieldFormatLabels, item.value))
    .map((item) => ({ ...item, label: fieldFormatLabels[item.value] })),
)
const possibleValueText = computed({
  get: () => (fieldForm.value.possible_values || []).join('\n'),
  set: (value) => {
    fieldForm.value.possible_values = String(value || '')
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean)
  },
})

const SortableTags = {
  name: 'SortableTags',
  props: { value: { type: Array, default: () => [] } },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () =>
      h(NDynamicTags, {
        class: 'sortable-tags',
        value: props.value || [],
        'onUpdate:value': (value) => emit('update:value', value),
      })
  },
}

const rules = {
  project_products: listRule('请至少配置一个项目产品'),
  project_statuses: listRule('请至少配置一个项目状态'),
  project_regions: listRule('请至少配置一个项目区域'),
  project_activity_types: listRule('请至少配置一个运维类型'),
  project_server_versions: listRule('请至少配置一个服务器版本'),
  project_client_versions: listRule('请至少配置一个客户端版本'),
}

const columns = [
  { title: '排序', key: 'position', width: 80, align: 'center' },
  { title: '名称', key: 'name', minWidth: 150, ellipsis: { tooltip: true } },
  {
    title: '格式',
    key: 'field_format',
    width: 120,
    render: (row) => tag(fieldFormatLabels[row.field_format] || row.field_format),
  },
  { title: '必填', key: 'is_required', width: 80, align: 'center', render: (row) => boolTag(row.is_required) },
  { title: '筛选', key: 'is_filter', width: 80, align: 'center', render: (row) => boolTag(row.is_filter) },
  { title: '列表', key: 'show_in_list', width: 80, align: 'center', render: (row) => boolTag(row.show_in_list) },
  { title: '可见', key: 'visible', width: 80, align: 'center', render: (row) => boolTag(row.visible) },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    align: 'center',
    fixed: 'right',
    render: (row) =>
      h(
        NButton,
        { size: 'small', type: 'primary', secondary: true, onClick: () => openField(row) },
        {
          icon: () => h(TheIcon, { icon: 'material-symbols:edit-outline', size: 16 }),
          default: () => '编辑',
        },
      ),
  },
]

onMounted(loadAll)

function defaultProjectSettings() {
  return {
    project_products: ['安得卫士'],
    project_statuses: ['售前', '待实施', '实施中', '待验收', '已验收', '关闭'],
    project_regions: ['华东', '华南', '华北', '华中', '西南', '西北'],
    project_activity_types: ['迁移库', '重做系统', '运维', '其他'],
    project_server_versions: ['5.6.1'],
    project_client_versions: ['2.25'],
  }
}

function defaultField() {
  return {
    type: 'project',
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
    position: nextPosition(),
  }
}

function cleanList(items) {
  const result = []
  ;(items || []).forEach((item) => {
    const text = String(item || '').trim()
    if (text && !result.includes(text)) result.push(text)
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

function tag(value) {
  return h(NTag, { size: 'small', bordered: false }, { default: () => value || '-' })
}

function boolTag(value) {
  return h(
    NTag,
    { size: 'small', type: value ? 'success' : 'default', bordered: false },
    { default: () => (value ? '是' : '否') },
  )
}

function nextPosition() {
  return customFields.value.length
    ? Math.max(...customFields.value.map((item) => Number(item.position || 0))) + 1
    : 1
}

function mergeSettings(data = {}) {
  const defaults = defaultProjectSettings()
  settings.value = {
    project_products: cleanList(data.project_products?.length ? data.project_products : defaults.project_products),
    project_statuses: cleanList(data.project_statuses?.length ? data.project_statuses : defaults.project_statuses),
    project_regions: cleanList(data.project_regions?.length ? data.project_regions : defaults.project_regions),
    project_activity_types: cleanList(
      data.project_activity_types?.length ? data.project_activity_types : defaults.project_activity_types,
    ),
    project_server_versions: cleanList(
      data.project_server_versions?.length ? data.project_server_versions : defaults.project_server_versions,
    ),
    project_client_versions: cleanList(
      data.project_client_versions?.length ? data.project_client_versions : defaults.project_client_versions,
    ),
  }
}

async function loadAll() {
  loading.value = true
  try {
    const [settingsRes, configRes] = await Promise.all([api.getSystemSettings(), api.getIssueAdminConfig()])
    fullSettings.value = settingsRes?.data || {}
    mergeSettings(fullSettings.value)
    const config = configRes?.data || {}
    customFields.value = (config.custom_fields || []).filter((item) => item.type === 'project')
    fieldFormats.value = config.field_formats || []
  } finally {
    loading.value = false
  }
}

function saveSettings() {
  settingsFormRef.value?.validate(async (err) => {
    if (err) return
    settingsSaving.value = true
    try {
      const payload = {
        ...fullSettings.value,
        project_products: cleanList(settings.value.project_products),
        project_statuses: cleanList(settings.value.project_statuses),
        project_regions: cleanList(settings.value.project_regions),
        project_activity_types: cleanList(settings.value.project_activity_types),
        project_server_versions: cleanList(settings.value.project_server_versions),
        project_client_versions: cleanList(settings.value.project_client_versions),
      }
      await api.updateSystemSettings(payload)
      $message.success('项目配置已保存')
      const publicRes = await api.getAppConfig()
      appStore.setSiteConfig(publicRes.data || {})
      await loadAll()
    } finally {
      settingsSaving.value = false
    }
  })
}

function openField(row = null) {
  fieldForm.value = row ? { ...row, _editing: true } : defaultField()
  drawerVisible.value = true
}

async function saveField() {
  if (!fieldForm.value.name?.trim()) {
    $message.warning('请输入字段名称')
    return
  }
  fieldSaving.value = true
  try {
    const payload = { ...fieldForm.value, type: 'project', name: fieldForm.value.name.trim() }
    if (payload.field_format !== 'list') payload.possible_values = []
    delete payload._editing
    await api.saveIssueCustomFieldConfig(payload)
    $message.success('保存成功')
    drawerVisible.value = false
    await loadAll()
  } finally {
    fieldSaving.value = false
  }
}
</script>

<template>
  <CommonPage title="项目配置" :show-header="false">
    <div class="project-config-page">
      <section class="config-section">
        <div class="section-toolbar">
          <div class="section-copy">
            <strong>项目字典</strong>
            <span>维护项目、区域、运维类型和版本字典</span>
          </div>
          <NButton type="primary" :loading="settingsSaving" @click="saveSettings">
            <template #icon>
              <TheIcon icon="mdi-content-save-cog-outline" :size="17" />
            </template>
            保存配置
          </NButton>
        </div>
        <NForm ref="settingsFormRef" :model="settings" :rules="rules" label-placement="top">
          <div class="settings-grid">
            <NFormItem label="项目产品" path="project_products"><SortableTags v-model:value="settings.project_products" /></NFormItem>
            <NFormItem label="项目状态" path="project_statuses"><SortableTags v-model:value="settings.project_statuses" /></NFormItem>
            <NFormItem label="项目区域" path="project_regions"><SortableTags v-model:value="settings.project_regions" /></NFormItem>
            <NFormItem label="运维类型" path="project_activity_types"><SortableTags v-model:value="settings.project_activity_types" /></NFormItem>
            <NFormItem label="服务器版本" path="project_server_versions"><SortableTags v-model:value="settings.project_server_versions" /></NFormItem>
            <NFormItem label="客户端版本" path="project_client_versions"><SortableTags v-model:value="settings.project_client_versions" /></NFormItem>
          </div>
        </NForm>
      </section>

      <section class="config-section">
        <div class="section-toolbar">
          <div class="section-copy">
            <strong>项目自定义字段</strong>
            <span>维护项目新增和详情中的扩展字段</span>
          </div>
          <NButton type="primary" @click="openField()">
            <template #icon>
              <TheIcon icon="mdi-content-save-cog-outline" :size="17" />
            </template>
            新增字段
          </NButton>
        </div>
        <NDataTable :loading="loading" :columns="columns" :data="customFields" :scroll-x="850" />
      </section>

      <NDrawer v-model:show="drawerVisible" placement="right" :width="720">
        <NDrawerContent
          :title="`${fieldForm._editing || fieldForm.id ? '编辑' : '新增'}项目自定义字段`"
          closable
        >
          <NForm label-placement="top" class="drawer-form">
            <NFormItem label="字段名称"><NInput v-model:value="fieldForm.name" placeholder="请输入字段名称" /></NFormItem>
            <div class="drawer-grid">
              <NFormItem label="字段格式">
                <NSelect v-model:value="fieldForm.field_format" :options="fieldFormatOptions" />
              </NFormItem>
              <NFormItem label="排序"><NInputNumber v-model:value="fieldForm.position" :min="0" style="width: 100%" /></NFormItem>
            </div>
            <NFormItem v-if="fieldForm.field_format === 'list'" label="可选值">
              <NInput v-model:value="possibleValueText" type="textarea" placeholder="每行一个选项" :autosize="{ minRows: 4, maxRows: 8 }" />
            </NFormItem>
            <NFormItem label="默认值"><NInput v-model:value="fieldForm.default_value" placeholder="可选" /></NFormItem>
            <NSpace>
              <NSwitch v-model:value="fieldForm.is_required" />必填
              <NSwitch v-model:value="fieldForm.is_filter" />筛选
              <NSwitch v-model:value="fieldForm.show_in_list" />列表显示
              <NSwitch v-model:value="fieldForm.multiple" :disabled="fieldForm.field_format !== 'list'" />多选
              <NSwitch v-model:value="fieldForm.visible" />可见
            </NSpace>
          </NForm>
          <template #footer>
            <div class="drawer-footer">
              <NButton @click="drawerVisible = false">取消</NButton>
              <NButton type="primary" :loading="fieldSaving" @click="saveField">保存</NButton>
            </div>
          </template>
        </NDrawerContent>
      </NDrawer>
    </div>
  </CommonPage>
</template>

<style scoped>
.project-config-page {
  display: grid;
  gap: 16px;
}

.config-section {
  padding: 16px;
  border: 1px solid #edf1f7;
  border-radius: 8px;
  background: #fff;
}

.section-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-copy {
  display: grid;
  gap: 4px;
}

.section-copy strong {
  color: #111827;
  font-size: 16px;
}

.section-copy span {
  color: #64748b;
  font-size: 13px;
}

.settings-grid,
.drawer-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.drawer-form {
  padding-right: 4px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

:deep(.sortable-tags .n-tag) {
  cursor: default;
}

@media (max-width: 720px) {
  .settings-grid,
  .drawer-grid {
    grid-template-columns: 1fr;
  }
}
</style>
