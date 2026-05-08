<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '文档管理' })

const loading = ref(false)
const uploading = ref(false)
const reindexing = ref(false)
const saving = ref(false)
const documents = ref([])
const selected = ref(null)
const keyword = ref('')
const fileInput = ref(null)
const activeTab = ref('preview')
const pollingTimers = new Map()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const uploadProgress = ref(0)
const uploadStage = ref('')
const uploadResumeKeyPrefix = 'skill-know-upload:'
const activeAbortControllers = ref([])
const editForm = ref(null)

const filteredDocuments = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return documents.value
  return documents.value.filter((item) => `${item.title} ${item.filename} ${item.content || ''}`.toLowerCase().includes(kw))
})

onMounted(loadDocuments)
onUnmounted(stopAllPolling)

const renderedMarkdown = computed(() => md.render(selected.value?.content || ''))

async function loadDocuments() {
  loading.value = true
  try {
    const res = await api.skillKnowDocuments({ page: 1, page_size: 100 })
    documents.value = res.data || []
    if (!selected.value && documents.value.length) await selectDocument(documents.value[0])
    else if (selected.value) {
      const current = documents.value.find((item) => item.id === selected.value.id) || documents.value[0] || null
      if (current) await selectDocument(current, { silent: true })
      else selected.value = null
    }
  } finally {
    loading.value = false
  }
}

async function selectDocument(item, options = {}) {
  if (!item) return
  selected.value = item
  if (['processing', 'pending'].includes(item.status)) startPolling(item.id)
  try {
    const res = await api.skillKnowGetDocument({ document_id: item.id })
    selected.value = res.data
    if (['processing', 'pending'].includes(res.data?.status)) startPolling(item.id)
    else stopPolling(item.id)
  } catch (error) {
    if (!options.silent) $message.error(error.message || '获取文档详情失败')
  }
}

async function uploadFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  uploadProgress.value = 0
  uploadStage.value = '初始化上传任务'
  try {
    const chunkSize = 2 * 1024 * 1024
    const concurrency = 3
    const totalChunks = Math.max(1, Math.ceil(file.size / chunkSize))
    const resumeKey = `${uploadResumeKeyPrefix}${file.name}:${file.size}:${totalChunks}`
    let uploadId = localStorage.getItem(resumeKey)
    if (!uploadId) {
      const initRes = await api.skillKnowInitChunkUpload({
        filename: file.name,
        title: file.name,
        file_size: file.size,
        total_chunks: totalChunks,
      })
      uploadId = initRes.data?.upload_id
      if (uploadId) localStorage.setItem(resumeKey, uploadId)
    }

    let uploadedSet = new Set()
    if (uploadId) {
      try {
        const statusRes = await api.skillKnowChunkUploadStatus({ upload_id: uploadId, total_chunks: totalChunks })
        uploadedSet = new Set(statusRes.data?.uploaded_chunks || [])
        uploadProgress.value = Math.min(95, statusRes.data?.progress || 0)
      } catch {
        localStorage.removeItem(resumeKey)
        const initRes = await api.skillKnowInitChunkUpload({
          filename: file.name,
          title: file.name,
          file_size: file.size,
          total_chunks: totalChunks,
        })
        uploadId = initRes.data?.upload_id
        if (uploadId) localStorage.setItem(resumeKey, uploadId)
      }
    }

    let uploadedChunks = 0
    uploadStage.value = '上传文件分片'
    uploadedChunks = uploadedSet.size
    for (let batchStart = 0; batchStart < totalChunks; batchStart += concurrency) {
      const tasks = []
      for (let index = batchStart; index < Math.min(totalChunks, batchStart + concurrency); index += 1) {
        if (uploadedSet.has(index)) continue
        const start = index * chunkSize
        const end = Math.min(file.size, start + chunkSize)
        const blob = file.slice(start, end)
        const formData = new FormData()
        formData.append('upload_id', uploadId)
        formData.append('chunk_index', String(index))
        formData.append('total_chunks', String(totalChunks))
        formData.append('file', blob, `${file.name}.part`)
        const controller = new AbortController()
        activeAbortControllers.value.push(controller)
        tasks.push(
          api.skillKnowUploadChunk(formData, controller.signal).finally(() => {
            activeAbortControllers.value = activeAbortControllers.value.filter((item) => item !== controller)
          }),
        )
      }
      if (tasks.length) await Promise.all(tasks)
      uploadedChunks += tasks.length
      uploadProgress.value = Math.min(95, Math.round((uploadedChunks / totalChunks) * 100))
    }

    uploadStage.value = '提交合并任务'
    const res = await api.skillKnowCompleteChunkUpload({
      upload_id: uploadId,
      filename: file.name,
      title: file.name,
      file_size: file.size,
      total_chunks: totalChunks,
    })
    uploadProgress.value = 100
    uploadStage.value = '后台转换 Markdown'
    selected.value = res.data
    $message.success('已开始后台转换，请稍候')
    localStorage.removeItem(resumeKey)
    startPolling(res.data.id)
    await loadDocuments()
  } catch (error) {
    if (error?.code === 'ERR_CANCELED' || error?.error?.code === 'ERR_CANCELED') {
      $message.warning('上传已取消，可重新选择同一文件继续续传')
    }
    else {
      throw error
    }
  } finally {
    uploading.value = false
    activeAbortControllers.value = []
    uploadProgress.value = 0
    uploadStage.value = ''
    e.target.value = ''
  }
}

function cancelUpload() {
  activeAbortControllers.value.forEach((controller) => controller.abort())
}

function startPolling(documentId) {
  if (!documentId || pollingTimers.has(documentId)) return
  const timer = window.setInterval(async () => {
    try {
      const res = await api.skillKnowGetDocument({ document_id: documentId })
      const doc = res.data
      documents.value = documents.value.map((item) => (item.id === doc.id ? { ...item, ...doc, content: undefined } : item))
      if (selected.value?.id === doc.id) selected.value = doc
      if (!['processing', 'pending'].includes(doc.status)) {
        stopPolling(documentId)
        await loadDocuments()
      }
    } catch (error) {
      stopPolling(documentId)
    }
  }, 2000)
  pollingTimers.set(documentId, timer)
}

function stopPolling(documentId) {
  const timer = pollingTimers.get(documentId)
  if (timer) window.clearInterval(timer)
  pollingTimers.delete(documentId)
}

function stopAllPolling() {
  for (const timer of pollingTimers.values()) window.clearInterval(timer)
  pollingTimers.clear()
}

async function reindexDocument() {
  if (!selected.value) return
  reindexing.value = true
  try {
    const res = await api.skillKnowReindexDocument({ document_id: selected.value.id })
    selected.value = res.data
    $message.success('索引已重建')
    await loadDocuments()
  } finally {
    reindexing.value = false
  }
}

function syncEditForm() {
  if (!selected.value) {
    editForm.value = null
    return
  }
  editForm.value = {
    title: selected.value.title || '',
    description: selected.value.description || '',
    abstract: selected.value.abstract || '',
    overview: selected.value.overview || '',
    content: selected.value.content || '',
    category: selected.value.category || '',
  }
}

async function saveDocument(reindexAfterSave = false) {
  if (!selected.value || !editForm.value) return
  saving.value = true
  try {
    const res = await api.skillKnowUpdateDocument({
      document_id: selected.value.id,
      title: editForm.value.title,
      description: editForm.value.description,
      abstract: editForm.value.abstract,
      overview: editForm.value.overview,
      content: editForm.value.content,
      category: editForm.value.category,
    })
    selected.value = res.data
    syncEditForm()
    if (reindexAfterSave) {
      const reindexed = await api.skillKnowReindexDocument({ document_id: selected.value.id })
      selected.value = reindexed.data
      syncEditForm()
      $message.success('已保存并重建索引')
    }
    else {
      $message.success('保存成功')
    }
    await loadDocuments()
  } finally {
    saving.value = false
  }
}

async function deleteDocument() {
  if (!selected.value) return
  window.$dialog.warning({
    title: '确认删除',
    content: `确定删除文档「${selected.value.title}」吗？Markdown 与向量索引都会删除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      await api.skillKnowDeleteDocument({ document_id: selected.value.id })
      selected.value = null
      await loadDocuments()
    },
  })
}

function statusText(status) {
  return { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }[status] || status
}

function stageText(stage) {
  return {
    uploaded: '已上传，等待处理',
    converting: '转换 Markdown 中',
    analyzing: '分析内容中',
    indexing: '分块并写入向量库中',
    completed: '处理完成',
    failed: '处理失败',
  }[stage] || stage || '-'
}

watch(selected, syncEditForm, { immediate: true })

</script>

<template>
  <CommonPage title="文档管理" show-footer>
    <div class="sk-theme-page">
      <div class="sk-hero">
        <h2 class="sk-hero-title">Markdown 知识入库</h2>
        <p class="sk-hero-sub">上传 PDF、PowerPoint、Word、Excel、HTML、CSV、JSON、XML、TXT、MD，统一转 Markdown 后分块写入 ChromaDB，不保留原始文件。</p>
      </div>
      <div class="doc-shell">
        <NCard class="doc-sidebar" :bordered="false">
          <NSpace vertical>
            <input ref="fileInput" type="file" class="hidden" accept=".pdf,.ppt,.pptx,.doc,.docx,.xls,.xlsx,.html,.htm,.csv,.json,.xml,.txt,.md,.markdown" @change="uploadFile" />
            <div class="sk-toolbar-row">
              <NButton class="sk-btn" type="primary" :loading="uploading" @click="fileInput?.click()">上传文档</NButton>
              <NButton class="sk-btn" secondary :loading="loading" @click="loadDocuments">刷新</NButton>
            </div>
            <NAlert v-if="uploading" type="info" :show-icon="false">
              {{ uploadStage }}
              <NProgress type="line" :percentage="uploadProgress" />
              <NSpace justify="end" class="progress-actions">
                <NButton size="tiny" secondary type="error" @click="cancelUpload">取消上传</NButton>
              </NSpace>
            </NAlert>
            <NInput v-model:value="keyword" clearable placeholder="搜索文档标题、文件名或 Markdown 内容" />
            <NSpin :show="loading">
              <div class="doc-list">
                <div
                  v-for="item in filteredDocuments"
                  :key="item.id"
                  class="doc-list-item"
                  :class="{ active: selected?.id === item.id }"
                  @click="selected = item"
                >
                  <div class="item-title">{{ item.title }}</div>
                  <div class="item-desc">
                    Markdown
                    <span v-if="item.extra_metadata?.original_file_type"> · 原始 {{ item.extra_metadata.original_file_type.toUpperCase() }}</span>
                    · {{ Math.max(1, item.file_size / 1024).toFixed(1) }} KB
                  </div>
                  <NSpace size="small" class="item-tags">
                    <span class="sk-status" :class="item.status === 'completed' ? 'success' : item.status === 'failed' ? 'error' : 'warning'">{{ statusText(item.status) }}</span>
                    <NTag v-if="item.extra_metadata?.chunk_count" size="small">{{ item.extra_metadata.chunk_count }} 块</NTag>
                  </NSpace>
                  <NProgress v-if="['processing', 'pending'].includes(item.status)" type="line" :percentage="item.extra_metadata?.process_progress || 5" :show-indicator="false" class="progress" />
                </div>
                <NEmpty v-if="!filteredDocuments.length" description="暂无文档" />
              </div>
            </NSpin>
          </NSpace>
        </NCard>
        <NCard class="doc-detail" :bordered="false">
          <template v-if="selected">
            <NSpace justify="space-between" align="start">
              <div><h2>{{ selected.title }}</h2><p class="muted">{{ selected.description || selected.filename }}</p></div>
              <NSpace>
                <NButton type="primary" :loading="saving" @click="saveDocument(false)">保存修改</NButton>
                <NButton secondary type="primary" :loading="saving || reindexing" @click="saveDocument(true)">保存并重建索引</NButton>
                <NButton secondary :loading="reindexing" :disabled="selected.status !== 'completed'" @click="reindexDocument">重建索引</NButton>
                <NButton secondary type="error" @click="deleteDocument">删除</NButton>
              </NSpace>
            </NSpace>
            <NGrid :cols="4" :x-gap="12" class="metric-grid">
              <NGi><NCard size="small"><div class="metric-label">状态</div><b>{{ statusText(selected.status) }}</b></NCard></NGi>
              <NGi><NCard size="small"><div class="metric-label">原始类型</div><b>{{ selected.extra_metadata?.original_file_type || '-' }}</b></NCard></NGi>
              <NGi><NCard size="small"><div class="metric-label">分类</div><b>{{ selected.category || '-' }}</b></NCard></NGi>
              <NGi><NCard size="small"><div class="metric-label">索引</div><b>{{ selected.extra_metadata?.index_status || '-' }}<span v-if="selected.extra_metadata?.chunk_count"> / {{ selected.extra_metadata.chunk_count }} 块</span></b></NCard></NGi>
            </NGrid>
            <NAlert v-if="['processing', 'pending'].includes(selected.status)" type="info" class="section-card">
              {{ stageText(selected.extra_metadata?.process_stage) }}，进度 {{ selected.extra_metadata?.process_progress || 5 }}%
              <NProgress type="line" :percentage="selected.extra_metadata?.process_progress || 5" />
            </NAlert>
            <NAlert v-if="selected.error_message" type="error" class="section-card">{{ selected.error_message }}</NAlert>
            <NForm v-if="editForm" label-placement="top" class="section-card">
              <NGrid :cols="2" :x-gap="12">
                <NGi><NFormItem label="标题"><NInput v-model:value="editForm.title" /></NFormItem></NGi>
                <NGi><NFormItem label="分类"><NInput v-model:value="editForm.category" /></NFormItem></NGi>
              </NGrid>
              <NFormItem label="描述"><NInput v-model:value="editForm.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" /></NFormItem>
              <NFormItem label="摘要"><NInput v-model:value="editForm.abstract" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" /></NFormItem>
              <NFormItem label="概览"><NInput v-model:value="editForm.overview" type="textarea" :autosize="{ minRows: 6, maxRows: 12 }" /></NFormItem>
            </NForm>
            <NCard size="small" class="section-card">
              <template #header>
                <NSpace justify="space-between" align="center">
                  <span>Markdown 文档</span>
                  <NButtonGroup size="small">
                    <NButton :type="activeTab === 'preview' ? 'primary' : 'default'" @click="activeTab = 'preview'">预览</NButton>
                    <NButton :type="activeTab === 'source' ? 'primary' : 'default'" @click="activeTab = 'source'">源码</NButton>
                  </NButtonGroup>
                </NSpace>
              </template>
              <div v-if="activeTab === 'preview'" class="markdown-preview" v-html="md.render(editForm?.content || '') || '<p>-</p>'" />
              <NInput v-else-if="editForm" v-model:value="editForm.content" type="textarea" :autosize="{ minRows: 18, maxRows: 30 }" />
              <pre v-else>{{ selected.content || '-' }}</pre>
            </NCard>
          </template>
          <NEmpty v-else description="请选择文档" />
        </NCard>
      </div>
    </div>
  </CommonPage>
</template>

<style scoped>
.hidden { display: none; }
.doc-shell { display: grid; grid-template-columns: 380px 1fr; gap: 16px; min-height: calc(100vh - 170px); }
.doc-list { max-height: calc(100vh - 300px); overflow: auto; }
.doc-list-item { padding: 12px; border-radius: 12px; cursor: pointer; border: 1px solid transparent; transition: .2s; }
.doc-list-item:hover, .doc-list-item.active { background: rgba(32, 128, 240, .08); border-color: rgba(32, 128, 240, .22); }
.item-title { font-weight: 700; }
.item-desc, .muted, .metric-label { color: #7b8494; font-size: 12px; }
.item-tags, .metric-grid, .section-card, .progress, .progress-actions, .upload-task-item { margin-top: 12px; }
pre { white-space: pre-wrap; word-break: break-word; margin: 0; max-height: 420px; overflow: auto; }
.markdown-preview { max-height: 620px; overflow: auto; line-height: 1.75; word-break: break-word; }
.markdown-preview :deep(h1), .markdown-preview :deep(h2), .markdown-preview :deep(h3) { margin: 18px 0 10px; font-weight: 800; }
.markdown-preview :deep(p) { margin: 8px 0; }
.markdown-preview :deep(pre) { padding: 12px; border-radius: 10px; background: rgba(15, 23, 42, .08); }
.markdown-preview :deep(code) { padding: 2px 5px; border-radius: 5px; background: rgba(15, 23, 42, .08); }
.markdown-preview :deep(table) { width: 100%; border-collapse: collapse; margin: 12px 0; }
.markdown-preview :deep(th), .markdown-preview :deep(td) { border: 1px solid rgba(148, 163, 184, .35); padding: 8px; text-align: left; }
@media (max-width: 900px) { .doc-shell { grid-template-columns: 1fr; } }
</style>
