<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NPopconfirm, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '版本发布记录' })

const route = useRoute()
const LEGACY_STORAGE_KEY = 'outbound_release_records'
const formRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const editorVisible = ref(false)
const activeRecordId = ref(null)
const records = ref([])
const form = ref(createEmptyForm())
const isViewMode = computed(() => route.path.endsWith('/release-view'))

const rules = {
  product: { required: true, message: '请输入产品名称', trigger: ['input', 'blur'] },
  version: { required: true, message: '请输入版本号', trigger: ['input', 'blur'] },
  packagePath: { required: true, message: '请输入获取目录', trigger: ['input', 'blur'] },
}
const channelOptions = [
  { label: '正式版本', value: '正式版本' },
  { label: '测试版本', value: '测试版本' },
  { label: '补丁包', value: '补丁包' },
]
const statusOptions = [
  { label: '待发布', value: '待发布' },
  { label: '已发布', value: '已发布' },
  { label: '已撤回', value: '已撤回' },
]
const statusType = {
  待发布: 'warning',
  已发布: 'success',
  已撤回: 'default',
}
const stats = computed(() => ({
  total: records.value.length,
  published: records.value.filter((item) => item.status === '已发布').length,
  pending: records.value.filter((item) => item.status === '待发布').length,
}))
const releaseDate = computed(() => formatDate(form.value.publishDate))
const releaseDateTime = computed(() => formatDateTime(form.value.publishDate))
const versionItems = computed(() =>
  [
    ['服务器', form.value.serverVersion],
    ['Windows', form.value.windowsVersion],
    ['Linux', form.value.linuxVersion],
    ['Mac', form.value.macVersion],
    ['手机', form.value.mobileVersion],
  ]
    .filter(([, value]) => String(value || '').trim())
    .map(([label, value]) => ({ label, value }))
)
const highlights = computed(() => parsePairs(form.value.highlightsText, '亮点'))
const fixes = computed(() => parsePairs(form.value.fixesText, '问题'))
const details = computed(() => parsePairs(form.value.detailsText, '模块'))
const columns = computed(() => {
  const baseColumns = [
    { title: '产品', key: 'product', minWidth: 160, ellipsis: { tooltip: true } },
    { title: '版本', key: 'version', width: 130, align: 'center' },
    { title: '类型', key: 'channel', width: 110, align: 'center' },
    {
      title: '状态',
      key: 'status',
      width: 100,
      align: 'center',
      render(row) {
        return h(NTag, { type: statusType[row.status] || 'default', bordered: false }, { default: () => row.status || '-' })
      },
    },
    { title: '发布日期', key: 'publishDateText', width: 160, align: 'center' },
    { title: '获取目录', key: 'packagePath', minWidth: 200, ellipsis: { tooltip: true } },
  ]
  return [
    ...baseColumns,
    {
      title: '操作',
      key: 'actions',
      width: isViewMode.value ? 90 : 130,
      align: 'center',
      render(row) {
        if (isViewMode.value) {
          return h(NButton, { size: 'small', quaternary: true, type: 'primary', onClick: () => viewRecord(row) }, { default: () => '查看' })
        }
        return h('div', { class: 'row-actions' }, [
          h(NButton, { size: 'small', quaternary: true, type: 'primary', onClick: () => editRecord(row) }, { default: () => '编辑' }),
          h(
            NPopconfirm,
            { onPositiveClick: () => removeRecord(row.id) },
            {
              trigger: () => h(NButton, { size: 'small', type: 'error', quaternary: true }, { default: () => '删除' }),
              default: () => '确认删除该发布记录？',
            }
          ),
        ])
      },
    },
  ]
})

onMounted(loadRecords)

function createEmptyForm() {
  return {
    product: '',
    version: '',
    channel: '',
    status: '',
    publishDate: null,
    serverVersion: '',
    windowsVersion: '',
    linuxVersion: '',
    macVersion: '',
    mobileVersion: '',
    packagePath: '',
    packageNote: '',
    footerNote: '',
    highlightsText: '',
    fixesText: '',
    detailsText: '',
  }
}

function createTemplateForm() {
  return {
    product: 'AndSec',
    version: 'V6.0.9',
    channel: '正式版本',
    status: '已发布',
    publishDate: Date.now(),
    serverVersion: '6.0.9.1149',
    windowsVersion: '6.0.9.211',
    linuxVersion: '6.0.39',
    macVersion: '6.0.33',
    mobileVersion: '6.0.9',
    packagePath: '网盘 609 目录',
    packageNote: '内部获取',
    footerNote: '© 2026 AndSec · 内部发布记录',
    highlightsText:
      '权限管理|按密级、部门/用户授权，批量制作权限文件，细粒度管控\n远程维护 & 屏幕监控|内外网穿透，跨网远程运维与录屏，支持进程触发\n上网行为审计|刻录、打印、USB拷贝、共享拷贝等外发行为审计\n版权隔离|进程级网络隔离，内置设计软件模板，规避版权风险\nDLP 统一管理|URL黑白名单、目录白名单、自动识别密级文件，与网络DLP联动\nLinux / Mac 增强|Linux支持UOS/CentOS/Ubuntu最新内核；Mac支持数据沙盒及M4/M5密文阅读',
    fixesText:
      '蓝屏问题|修复 Win10 数据沙盒场景下偶发蓝屏问题\n兼容性问题|修复部分 Linux 内核版本升级后客户端状态异常问题',
    detailsText:
      '权限管理|支持给个人、部门制作权限文件；制作支持不同密级权限文件；支持权限申请与权限修改\n屏幕监控|支持跨网屏幕监控；录屏支持根据进程启动、活动进程触发；录屏视频展现效果更新\n远程维护|支持跨网远程维护；提供远程维护工具下载；支持WEB直接操作与终端文件传输\n上网行为|微信支持获取接收到的消息；扩展支持审计USB、SMB、ftp、刻录、打印、网盘上传\n终端 DLP|支持URL黑白名单；目录白名单；新增响应动作：制作密级权限文件\nMac 新增|支持数据沙盒；支持M5、M4设备阅读密文、加密密文',
  }
}

async function loadRecords(selectedId = activeRecordId.value) {
  loading.value = true
  try {
    const res = isViewMode.value ? await api.releaseViewList() : await api.releaseList()
    records.value = Array.isArray(res.data) ? res.data : []
    if (!isViewMode.value && !records.value.length && (await migrateLegacyRecords())) {
      const retry = await api.releaseList()
      records.value = Array.isArray(retry.data) ? retry.data : []
    }
    if (isViewMode.value) {
      const current = records.value.find((item) => item.id === selectedId) || records.value[0]
      if (current) viewRecord(current)
    }
  } finally {
    loading.value = false
  }
}

async function migrateLegacyRecords() {
  try {
    const legacy = JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEY) || '[]')
    if (!Array.isArray(legacy) || !legacy.length) return false
    for (const record of legacy) {
      await api.releaseSave(record)
    }
    localStorage.removeItem(LEGACY_STORAGE_KEY)
    $message.success('已导入历史发布记录')
    return true
  } catch {
    return false
  }
}

function parsePairs(text, fallback) {
  return String(text || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [title, ...rest] = line.split('|')
      return {
        title: title.trim() || `${fallback}${index + 1}`,
        content: rest.join('|').trim().replace(/[；;]/g, '\n'),
      }
    })
}

function formatDate(value) {
  if (value == null || value === '') return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replaceAll('/', '-')
}

function formatDateTime(value) {
  if (value == null || value === '') return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', { hour12: false })
}

function resetForm() {
  activeRecordId.value = null
  form.value = createEmptyForm()
}

function newFromTemplate() {
  activeRecordId.value = null
  form.value = createTemplateForm()
  editorVisible.value = true
}

function submitRelease() {
  formRef.value?.validate(async (errors) => {
    if (errors) return
    saving.value = true
    try {
      const res = await api.releaseSave({
        ...form.value,
        id: activeRecordId.value,
        publishDateText: releaseDateTime.value,
      })
      const savedId = res.data?.id || null
      form.value = { ...createEmptyForm(), ...res.data }
      await loadRecords(savedId)
      editorVisible.value = false
      $message.success('发布记录已保存')
    } finally {
      saving.value = false
    }
  })
}

function viewRecord(row) {
  form.value = { ...createEmptyForm(), ...row }
  activeRecordId.value = row.id || null
}

function editRecord(row) {
  viewRecord(row)
  editorVisible.value = true
}

async function removeRecord(id) {
  await api.releaseDelete({ id })
  if (activeRecordId.value === id) resetForm()
  await loadRecords()
  $message.success('发布记录已删除')
}

async function clearRecords() {
  await api.releaseClear()
  resetForm()
  await loadRecords()
  $message.success('发布记录已清空')
}
</script>

<template>
  <CommonPage :title="isViewMode ? '版本发布' : '版本发布记录'" :show-header="false" show-footer>
    <NSpin :show="loading">
    <div class="release-page" :class="{ 'view-mode': isViewMode }">
      <NModal
        v-if="!isViewMode"
        v-model:show="editorVisible"
        preset="card"
        :title="activeRecordId ? '编辑版本发布记录' : '新增版本发布记录'"
        class="release-editor-modal"
        :style="{ width: 'min(980px, 96vw)' }"
        :bordered="false"
      >
      <section class="editor">
        <div class="page-head">
          <div>
            <p class="eyebrow">Outbound Release</p>
            <h1>版本发布记录</h1>
          </div>
          <div class="stats">
            <div><span>全部</span><b>{{ stats.total }}</b></div>
            <div><span>已发布</span><b>{{ stats.published }}</b></div>
            <div><span>待发布</span><b>{{ stats.pending }}</b></div>
          </div>
        </div>

        <NForm ref="formRef" :model="form" :rules="rules" label-placement="top">
          <div class="form-section">
            <div class="section-title">基础信息</div>
            <div class="form-grid">
              <NFormItem label="产品名称" path="product">
                <NInput v-model:value="form.product" />
              </NFormItem>
              <NFormItem label="版本号" path="version">
                <NInput v-model:value="form.version" />
              </NFormItem>
              <NFormItem label="版本类型">
                <NSelect v-model:value="form.channel" :options="channelOptions" />
              </NFormItem>
              <NFormItem label="发布状态">
                <NSelect v-model:value="form.status" :options="statusOptions" />
              </NFormItem>
              <NFormItem label="发布日期">
                <NDatePicker v-model:value="form.publishDate" type="date" :clearable="false" class="full-input" />
              </NFormItem>
            </div>
          </div>

          <div class="form-section">
            <div class="section-title">版本明细</div>
            <div class="form-grid">
              <NFormItem label="服务器">
                <NInput v-model:value="form.serverVersion" />
              </NFormItem>
              <NFormItem label="Windows">
                <NInput v-model:value="form.windowsVersion" />
              </NFormItem>
              <NFormItem label="Linux">
                <NInput v-model:value="form.linuxVersion" />
              </NFormItem>
              <NFormItem label="Mac">
                <NInput v-model:value="form.macVersion" />
              </NFormItem>
              <NFormItem label="手机">
                <NInput v-model:value="form.mobileVersion" />
              </NFormItem>
            </div>
          </div>

          <div class="form-section">
            <div class="section-title">获取方式</div>
            <div class="form-grid">
              <NFormItem label="获取目录" path="packagePath">
                <NInput v-model:value="form.packagePath" />
              </NFormItem>
              <NFormItem label="获取备注">
                <NInput v-model:value="form.packageNote" />
              </NFormItem>
            </div>
          </div>

          <div class="form-section">
            <div class="section-title">主要新增功能</div>
            <NFormItem label="亮点内容">
              <NInput
                v-model:value="form.highlightsText"
                type="textarea"
                :autosize="{ minRows: 5, maxRows: 9 }"
                placeholder="权限管理|按密级、部门/用户授权"
              />
            </NFormItem>
          </div>

          <div class="form-section">
            <div class="section-title">主要修复问题</div>
            <NFormItem label="修复问题">
              <NInput
                v-model:value="form.fixesText"
                type="textarea"
                :autosize="{ minRows: 4, maxRows: 8 }"
                placeholder="蓝屏问题|修复 Win10 数据沙盒场景下的蓝屏问题"
              />
            </NFormItem>
          </div>

          <div class="form-section">
            <div class="section-title">主要新增功能清单</div>
            <NFormItem label="新增功能清单">
              <NInput
                v-model:value="form.detailsText"
                type="textarea"
                :autosize="{ minRows: 7, maxRows: 12 }"
                placeholder="权限管理|支持个人授权；支持部门授权"
              />
            </NFormItem>
            <NFormItem label="页脚">
              <NInput v-model:value="form.footerNote" />
            </NFormItem>
          </div>

          <div class="actions">
            <NButton type="primary" :loading="saving" @click="submitRelease">
              {{ activeRecordId ? '更新发布记录' : '保存发布记录' }}
            </NButton>
            <NButton tertiary @click="resetForm">清空</NButton>
          </div>
        </NForm>
      </section>
      </NModal>

      <section v-if="isViewMode && records.length" class="preview">
        <article class="release-sheet">
          <header class="release-header">
            <h2><span>发布记录</span>{{ form.product }} {{ form.version }}</h2>
            <div class="meta">
              <span>发布日期：{{ releaseDate }}</span>
              <span>{{ form.channel }}</span>
              <span>状态：{{ form.status }}</span>
            </div>
          </header>

          <div class="version-grid">
            <span v-for="item in versionItems" :key="item.label" class="version-item">{{ item.label }} {{ item.value }}</span>
          </div>

          <div class="download-box">
            <div>
              <strong>{{ form.packagePath }}</strong>
              <span v-if="form.packageNote">（{{ form.packageNote }}）</span>
            </div>
          </div>

          <div class="sheet-title">
            <span>主要新增功能</span>
            <i></i>
          </div>
          <div class="highlight-list">
            <div v-for="(item, index) in highlights" :key="`${item.title}-${index}`" class="highlight-item">
              <b>{{ index + 1 }}</b>
              <div>
                <h3>{{ item.title }}</h3>
                <p>{{ item.content }}</p>
              </div>
            </div>
          </div>

          <div class="sheet-title">
            <span>主要修复问题</span>
            <i></i>
          </div>
          <div class="highlight-list">
            <div v-for="(item, index) in fixes" :key="`${item.title}-${index}`" class="highlight-item fix-item">
              <b>{{ index + 1 }}</b>
              <div>
                <h3>{{ item.title }}</h3>
                <p>{{ item.content }}</p>
              </div>
            </div>
          </div>

          <div class="sheet-title">
            <span>主要新增功能清单</span>
            <i></i>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>功能模块</th>
                  <th>功能项</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in details" :key="`${item.title}-${index}`">
                  <td>{{ item.title }}</td>
                  <td>{{ item.content }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <footer class="release-footer">
            <span>{{ form.footerNote }}</span>
            <span>版本状态：{{ form.channel }}</span>
          </footer>
        </article>
      </section>

      <section v-else-if="isViewMode" class="empty-view">
        <NEmpty description="暂无版本发布记录" />
      </section>

      <section class="records" :class="{ 'pipeline-panel': isViewMode }">
        <div class="table-head">
          <div class="section-title">{{ isViewMode ? '历史版本' : '记录列表' }}</div>
          <div v-if="!isViewMode" class="table-actions">
            <NButton size="small" type="primary" @click="newFromTemplate">新增</NButton>
            <NPopconfirm :disabled="!records.length" @positive-click="clearRecords">
              <template #trigger>
                <NButton size="small" tertiary type="error" :disabled="!records.length">清空</NButton>
              </template>
              确认清空所有发布记录？
            </NPopconfirm>
          </div>
        </div>
        <div v-if="isViewMode" class="pipeline">
          <button
            v-for="record in records"
            :key="record.id"
            type="button"
            class="pipeline-card"
            :class="{ active: record.id === activeRecordId }"
            @click="viewRecord(record)"
          >
            <span class="pipeline-dot"></span>
            <span class="pipeline-date">{{ record.publishDateText || '-' }}</span>
            <strong>{{ record.product }} {{ record.version }}</strong>
            <span class="pipeline-meta">
              <i :class="statusType[record.status] || 'default'">{{ record.status || '-' }}</i>
              <em>{{ record.channel || '-' }}</em>
            </span>
          </button>
        </div>
        <NDataTable
          v-else
          :columns="columns"
          :data="records"
          :pagination="{ pageSize: 8 }"
          :scroll-x="980"
          :bordered="false"
        />
      </section>
    </div>
    </NSpin>
  </CommonPage>
</template>

<style scoped>
.release-page {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  padding: 20px;
  background: #eef3f8;
}

.release-page.view-mode {
  align-items: start;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
}

.release-page.view-mode .records {
  grid-column: 1;
  grid-row: 1;
}

.release-page.view-mode .preview,
.release-page.view-mode .empty-view {
  grid-column: 2;
  grid-row: 1;
}

.release-page.view-mode .release-sheet {
  max-width: none;
  margin: 0;
}

.editor,
.preview,
.records,
.empty-view {
  min-width: 0;
}

.editor,
.records {
  padding: 20px;
  border: 1px solid #dfe7f0;
  border-radius: 8px;
  background: #fff;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.eyebrow {
  margin: 0;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-head h1 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 24px;
  font-weight: 800;
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(62px, 1fr));
  gap: 8px;
}

.stats > div {
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.stats span {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.stats b {
  display: block;
  margin-top: 2px;
  color: #0f172a;
  font-size: 20px;
}

.form-section {
  padding-top: 14px;
  border-top: 1px solid #eef2f6;
}

.form-section:first-of-type {
  border-top: 0;
  padding-top: 0;
}

.section-title {
  margin-bottom: 12px;
  color: #0f172a;
  font-size: 15px;
  font-weight: 800;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.full-input {
  width: 100%;
}

.actions,
.table-head,
.table-actions,
:deep(.row-actions) {
  display: flex;
  align-items: center;
  gap: 10px;
}

.table-head {
  justify-content: space-between;
}

.preview {
  overflow-x: auto;
}

.empty-view {
  display: grid;
  min-height: 260px;
  place-items: center;
  border: 1px solid #dfe7f0;
  border-radius: 8px;
  background: #fff;
}

.release-sheet {
  max-width: 1100px;
  min-width: 720px;
  margin: 0 auto;
  padding: 42px 46px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #1e293b;
  box-shadow: 0 14px 38px rgba(15, 23, 42, 0.08);
}

.release-header {
  padding-bottom: 22px;
  border-bottom: 2px solid #e9edf2;
}

.release-header h2 {
  margin: 0;
  color: #0f172a;
  font-size: 30px;
  font-weight: 800;
  letter-spacing: 0;
}

.release-header h2 span {
  display: inline-block;
  margin-right: 10px;
  padding: 2px 16px;
  border-radius: 999px;
  background: #eef2ff;
  color: #2563eb;
  font-size: 14px;
  vertical-align: middle;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 26px;
  margin-top: 12px;
  color: #475569;
  font-size: 15px;
}

.version-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
  margin: 28px 0;
  padding: 16px 22px;
  border: 1px solid #edf2f7;
  border-radius: 8px;
  background: #f8fafc;
}

.version-item {
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
}

.download-box {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 32px;
  padding: 18px 22px;
  border-left: 5px solid #2563eb;
  border-radius: 8px;
  background: #f1f6fd;
}

.download-box strong {
  display: inline-block;
  padding: 4px 14px;
  border: 1px solid #dbeafe;
  border-radius: 999px;
  background: #fff;
  color: #1e293b;
  font-family: Consolas, 'Microsoft YaHei', sans-serif;
  font-size: 14px;
}

.sheet-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 28px 0 16px;
  color: #0f172a;
  font-size: 21px;
  font-weight: 800;
}

.sheet-title i {
  height: 1px;
  flex: 1;
  background: linear-gradient(to right, #e2e8f0, transparent);
}

.highlight-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}

.highlight-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 15px 18px;
  border: 1px solid #eef2f6;
  border-radius: 8px;
  background: #fafcff;
}

.highlight-item b {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  place-items: center;
  border-radius: 999px;
  background: #e8effb;
  color: #2563eb;
  font-size: 14px;
}

.highlight-item h3 {
  margin: 0 0 4px;
  color: #0f172a;
  font-size: 15px;
}

.highlight-item p {
  margin: 0;
  color: #475569;
  font-size: 14px;
  white-space: pre-line;
}

.fix-item b {
  background: #fff1f2;
  color: #be123c;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #e9edf2;
  border-radius: 8px;
}

table {
  width: 100%;
  min-width: 600px;
  border-collapse: collapse;
  font-size: 14px;
}

thead {
  background: #f1f6fc;
}

th,
td {
  padding: 13px 18px;
  border-bottom: 1px solid #f0f2f5;
  text-align: left;
  vertical-align: top;
}

th {
  color: #1e293b;
  font-weight: 800;
}

td:first-child {
  width: 130px;
  color: #0f172a;
  font-weight: 800;
  white-space: nowrap;
}

td:last-child {
  color: #334155;
  white-space: pre-line;
}

tbody tr:last-child td {
  border-bottom: 0;
}

.release-footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
  margin-top: 34px;
  padding-top: 18px;
  border-top: 1px solid #e9edf2;
  color: #94a3b8;
  font-size: 14px;
}

.records {
  grid-column: 1 / -1;
}

.pipeline-panel {
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 120px);
  padding: 22px 24px;
  overflow-y: auto;
}

.pipeline {
  position: relative;
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  padding: 8px 0 4px 28px;
}

.pipeline::before {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 7px;
  width: 2px;
  background: #dbe7f5;
  content: '';
}

.pipeline-card {
  position: relative;
  display: grid;
  gap: 8px;
  min-height: 112px;
  padding: 14px 16px;
  border: 1px solid #dbe7f5;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  text-align: left;
  cursor: pointer;
  box-shadow: 0 10px 24px rgba(15, 23, 42, .06);
}

.pipeline-card.active {
  border-color: #2563eb;
  box-shadow: 0 12px 28px rgba(37, 99, 235, .16);
}

.pipeline-dot {
  position: absolute;
  top: 18px;
  left: -29px;
  width: 16px;
  height: 16px;
  border: 3px solid #fff;
  border-radius: 50%;
  background: #2563eb;
  box-shadow: 0 0 0 2px #bfdbfe;
}

.pipeline-date {
  color: #64748b;
  font-size: 12px;
}

.pipeline-card strong {
  overflow-wrap: anywhere;
  font-size: 16px;
}

.pipeline-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pipeline-meta i,
.pipeline-meta em {
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-style: normal;
}

.pipeline-meta i {
  background: #f1f5f9;
  color: #475569;
}

.pipeline-meta i.success {
  background: #dcfce7;
  color: #15803d;
}

.pipeline-meta i.warning {
  background: #fef3c7;
  color: #b45309;
}

.pipeline-meta em {
  background: #eef2ff;
  color: #2563eb;
}

@media (max-width: 1280px) {
  .release-page {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .release-page {
    padding: 12px;
  }

  .page-head {
    flex-direction: column;
  }

  .stats,
  .form-grid {
    width: 100%;
    grid-template-columns: 1fr;
  }

  .release-sheet {
    min-width: 0;
    padding: 28px 20px;
  }

  .release-header h2 {
    font-size: 24px;
  }

  .download-box {
    align-items: flex-start;
    flex-direction: column;
  }

  .release-page.view-mode {
    grid-template-columns: 1fr;
  }

  .release-page.view-mode .records,
  .release-page.view-mode .preview,
  .release-page.view-mode .empty-view {
    grid-column: 1;
  }

  .release-page.view-mode .records {
    grid-row: 1;
  }

  .release-page.view-mode .preview,
  .release-page.view-mode .empty-view {
    grid-row: 2;
  }

  .pipeline-panel {
    position: static;
    max-height: none;
  }
}
</style>
