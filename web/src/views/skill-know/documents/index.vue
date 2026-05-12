<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'
import { sanitizeHtml } from '@/utils'

defineOptions({ name: '文档管理' })

const loading = ref(false)
const uploading = ref(false)
const reindexing = ref(false)
const saving = ref(false)
const documents = ref([])
const selected = ref(null)
const keyword = ref('')
const fileInput = ref(null)
const chunkPreview = ref(null)
const activeTab = ref('preview')
const pollingTimers = new Map()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const uploadProgress = ref(0)
const uploadStage = ref('')
const uploadResumeKeyPrefix = 'skill-know-upload:'
const activeAbortControllers = ref([])
const editForm = ref(null)
const route = useRoute()
const highlightedChunkId = ref('')
const chunkRefs = ref({})

const filteredDocuments = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return documents.value
  return documents.value.filter((item) => `${item.title} ${item.filename} ${item.content || ''}`.toLowerCase().includes(kw))
})

onMounted(loadDocuments)
onUnmounted(stopAllPolling)

const renderedMarkdown = computed(() => md.render(selected.value?.content || ''))
const renderMarkdown = (content) => sanitizeHtml(md.render(content || '') || '<p>-</p>')
const highlightedChunk = computed(() => {
  if (!highlightedChunkId.value) return null
  return (selected.value?.chunks || []).find((chunk) => String(chunk.id) === String(highlightedChunkId.value)) || null
})
const renderedChunks = computed(() => (selected.value?.chunks || []).map((chunk) => ({
  ...chunk,
  rendered: renderMarkdown(chunk.content),
  active: String(chunk.id) === String(highlightedChunkId.value),
})))

async function loadDocuments() {
  loading.value = true
  try {
    const res = await api.skillKnowDocuments({ page: 1, page_size: 100 })
    documents.value = res.data || []
    const queryDocumentId = Number(route.query.document_id || 0)
    const queryDocument = queryDocumentId ? documents.value.find((item) => item.id === queryDocumentId) : null
    if (queryDocument) {
      highlightedChunkId.value = String(route.query.chunk_id || '')
      activeTab.value = 'preview'
      await selectDocument(queryDocument)
      await scrollToHighlightedChunk()
    }
    else if (!selected.value && documents.value.length) await selectDocument(documents.value[0])
    else if (selected.value) {
      const current = documents.value.find((item) => item.id === selected.value.id) || documents.value[0] || null
      if (current) await selectDocument(current, { silent: true })
      else selected.value = null
    }
  } finally {
    loading.value = false
  }
}

async function scrollToHighlightedChunk() {
  await nextTick()
  const target = chunkRefs.value[String(highlightedChunkId.value)] || chunkPreview.value
  target?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

function setChunkRef(id, el) {
  if (!id) return
  if (el) chunkRefs.value[String(id)] = el
  else delete chunkRefs.value[String(id)]
}

watch(
  () => route.query.document_id,
  async () => {
    if (route.path !== '/skill-know/documents') return
    await loadDocuments()
  },
)

watch(
  () => route.query.chunk_id,
  async (chunkId) => {
    highlightedChunkId.value = String(chunkId || '')
    if (route.path !== '/skill-know/documents' || !highlightedChunkId.value) return
    activeTab.value = 'preview'
    await scrollToHighlightedChunk()
  },
)

async function selectDocument(item, options = {}) {
  if (!item) return
  selected.value = item
  if (['processing', 'pending'].includes(item.status)) startPolling(item.id)
  try {
    const res = await api.skillKnowGetDocument({ document_id: item.id })
    selected.value = res.data
    if (highlightedChunkId.value) await scrollToHighlightedChunk()
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
  <CommonPage title="文档管理" :show-header="false" show-footer>
    <div class="doc-workspace">
      <aside class="doc-sidebar">
        <div class="sidebar-head">
          <div>
            <div class="eyebrow">Knowledge Library</div>
            <h2>知识文档</h2>
            <p>上传文件并转为 Markdown 分块入库，支持从智能对话引用回跳定位。</p>
          </div>
          <NTag size="small" round>{{ documents.length }} 篇</NTag>
        </div>

        <input ref="fileInput" type="file" class="hidden" accept=".pdf,.ppt,.pptx,.doc,.docx,.xls,.xlsx,.html,.htm,.csv,.json,.xml,.txt,.md,.markdown" @change="uploadFile" />
        <div class="upload-card" @click="fileInput?.click()">
          <div class="upload-mark">+</div>
          <div>
            <b>{{ uploading ? uploadStage : '上传知识文档' }}</b>
            <p>PDF、Office、HTML、CSV、JSON、TXT、MD 均可转换入库。</p>
          </div>
        </div>
        <div v-if="uploading" class="upload-progress">
          <NProgress type="line" :percentage="uploadProgress" />
          <NSpace justify="end" class="progress-actions">
            <NButton size="tiny" secondary type="error" @click="cancelUpload">取消上传</NButton>
          </NSpace>
        </div>

        <div class="sidebar-actions">
          <NInput v-model:value="keyword" clearable placeholder="搜索文档、文件名或内容" />
          <NButton secondary :loading="loading" @click="loadDocuments">刷新</NButton>
        </div>

        <NSpin :show="loading">
          <div class="doc-list">
            <button
              v-for="item in filteredDocuments"
              :key="item.id"
              class="doc-list-item"
              :class="{ active: selected?.id === item.id }"
              type="button"
              @click="selectDocument(item)"
            >
              <span class="item-title">{{ item.title }}</span>
              <span class="item-desc">
                Markdown
                <span v-if="item.extra_metadata?.original_file_type"> · {{ item.extra_metadata.original_file_type.toUpperCase() }}</span>
                · {{ Math.max(1, item.file_size / 1024).toFixed(1) }} KB
              </span>
              <span class="item-tags">
                <span class="doc-status" :class="item.status === 'completed' ? 'success' : item.status === 'failed' ? 'error' : 'warning'">{{ statusText(item.status) }}</span>
                <NTag v-if="item.extra_metadata?.chunk_count" size="small" round>{{ item.extra_metadata.chunk_count }} 块</NTag>
              </span>
              <NProgress v-if="['processing', 'pending'].includes(item.status)" type="line" :percentage="item.extra_metadata?.process_progress || 5" :show-indicator="false" />
            </button>
            <NEmpty v-if="!filteredDocuments.length" description="暂无文档" />
          </div>
        </NSpin>
      </aside>

      <section class="doc-main">
        <template v-if="selected">
          <header class="doc-header">
            <div>
              <div class="eyebrow">{{ selected.category || 'Document' }}</div>
              <h1>{{ selected.title }}</h1>
              <p>{{ selected.description || selected.filename }}</p>
            </div>
            <NSpace>
              <NButton type="primary" :loading="saving" @click="saveDocument(false)">保存修改</NButton>
              <NButton secondary type="primary" :loading="saving || reindexing" @click="saveDocument(true)">保存并重建索引</NButton>
              <NButton secondary :loading="reindexing" :disabled="selected.status !== 'completed'" @click="reindexDocument">重建索引</NButton>
              <NButton secondary type="error" @click="deleteDocument">删除</NButton>
            </NSpace>
          </header>

          <section class="metric-grid">
            <div class="metric-card"><span>状态</span><b>{{ statusText(selected.status) }}</b></div>
            <div class="metric-card"><span>原始类型</span><b>{{ selected.extra_metadata?.original_file_type || '-' }}</b></div>
            <div class="metric-card"><span>分类</span><b>{{ selected.category || '-' }}</b></div>
            <div class="metric-card"><span>索引</span><b>{{ selected.extra_metadata?.index_status || '-' }}<template v-if="selected.extra_metadata?.chunk_count"> / {{ selected.extra_metadata.chunk_count }} 块</template></b></div>
          </section>

          <NAlert v-if="['processing', 'pending'].includes(selected.status)" type="info" class="notice-card">
            {{ stageText(selected.extra_metadata?.process_stage) }}，进度 {{ selected.extra_metadata?.process_progress || 5 }}%
            <NProgress type="line" :percentage="selected.extra_metadata?.process_progress || 5" />
          </NAlert>
          <NAlert v-if="highlightedChunkId" type="success" class="notice-card citation-highlight" :show-icon="false">
            已定位到智能对话引用片段，引用块 ID：{{ highlightedChunkId }}。
          </NAlert>
          <NAlert v-if="selected.error_message" type="error" class="notice-card">{{ selected.error_message }}</NAlert>

          <section class="edit-panel">
            <div class="panel-head">
              <div>
                <h3>文档信息</h3>
                <p>调整标题、分类、摘要和概览，保存后可选择同步重建索引。</p>
              </div>
            </div>
            <NForm v-if="editForm" label-placement="top" class="doc-form">
              <div class="two-col">
                <NFormItem label="标题"><NInput v-model:value="editForm.title" /></NFormItem>
                <NFormItem label="分类"><NInput v-model:value="editForm.category" /></NFormItem>
              </div>
              <NFormItem label="描述"><NInput v-model:value="editForm.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" /></NFormItem>
              <NFormItem label="摘要"><NInput v-model:value="editForm.abstract" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" /></NFormItem>
              <NFormItem label="概览"><NInput v-model:value="editForm.overview" type="textarea" :autosize="{ minRows: 5, maxRows: 10 }" /></NFormItem>
            </NForm>
          </section>

          <section class="preview-panel">
            <div class="panel-head preview-head">
              <div>
                <h3>Markdown 文档</h3>
                <p>按索引分块展示，引用片段会自动高亮。</p>
              </div>
              <NButtonGroup size="small">
                <NButton :type="activeTab === 'preview' ? 'primary' : 'default'" @click="activeTab = 'preview'">预览</NButton>
                <NButton :type="activeTab === 'source' ? 'primary' : 'default'" @click="activeTab = 'source'">源码</NButton>
              </NButtonGroup>
            </div>

            <div v-if="activeTab === 'preview'" class="preview-stack">
              <div v-if="highlightedChunk" ref="chunkPreview">
                <NAlert type="info" class="chunk-preview" :show-icon="false">
                  <div class="chunk-preview-title">引用片段 #{{ highlightedChunk.chunk_index + 1 }} <span v-if="highlightedChunk.heading">· {{ highlightedChunk.heading }}</span></div>
                  <div class="markdown-preview chunk-markdown" v-html="renderMarkdown(highlightedChunk.content)" />
                </NAlert>
              </div>
              <div v-else-if="highlightedChunkId" ref="chunkPreview">
                <NAlert type="warning" class="chunk-preview" :show-icon="false">
                  未找到引用块 {{ highlightedChunkId }}，可能文档已重新索引。下方显示完整文档。
                </NAlert>
              </div>
              <div class="chunked-preview markdown-preview">
                <section
                  v-for="chunk in renderedChunks"
                  :key="chunk.id"
                  :ref="(el) => setChunkRef(chunk.id, el)"
                  class="doc-chunk"
                  :class="{ active: chunk.active }"
                >
                  <div class="doc-chunk-meta">
                    <span>片段 #{{ chunk.chunk_index + 1 }}</span>
                    <span v-if="chunk.heading">{{ chunk.heading }}</span>
                  </div>
                  <div class="doc-chunk-content" v-html="chunk.rendered" />
                </section>
                <div v-if="!renderedChunks.length" v-html="renderMarkdown(editForm?.content)" />
              </div>
            </div>
            <NInput v-else-if="editForm" v-model:value="editForm.content" class="source-editor" type="textarea" :autosize="{ minRows: 20, maxRows: 34 }" />
            <pre v-else>{{ selected.content || '-' }}</pre>
          </section>
        </template>
        <NEmpty v-else class="empty-state" description="请选择文档" />
      </section>
    </div>
  </CommonPage>
</template>

<style scoped>
.hidden { display: none; }
.doc-workspace { --ai-bg: #f7f7f4; --ai-sidebar: #f1f0ea; --ai-line: rgba(17, 24, 39, .10); --ai-text: #111827; --ai-muted: #6b7280; display: grid; grid-template-columns: 360px minmax(0, 1fr); height: calc(100vh - 96px); min-height: 560px; overflow: hidden; border: 1px solid var(--ai-line); border-radius: 20px; background: var(--ai-bg); box-shadow: 0 18px 50px rgba(15, 23, 42, .08); }
.doc-sidebar { min-height: 0; display: grid; grid-template-rows: auto auto auto minmax(0, 1fr); gap: 14px; padding: 18px; border-right: 1px solid var(--ai-line); background: var(--ai-sidebar); }
.sidebar-head, .doc-header, .panel-head, .preview-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.eyebrow { color: #10a37f; font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
h1, h2, h3, p { margin: 0; }
h1, h2, h3 { color: var(--ai-text); font-weight: 800; }
.sidebar-head h2, .doc-header h1 { margin-top: 6px; }
.sidebar-head p, .doc-header p, .panel-head p, .upload-card p, .item-desc { margin-top: 7px; color: var(--ai-muted); font-size: 13px; line-height: 1.6; }
.upload-card { display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: 12px; align-items: center; padding: 14px; border: 1px dashed rgba(17, 24, 39, .22); border-radius: 18px; background: rgba(255, 255, 255, .62); cursor: pointer; transition: .18s ease; }
.upload-card:hover { border-color: rgba(16, 163, 127, .48); background: #fff; }
.upload-mark { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 14px; background: #111827; color: #fff; font-size: 24px; }
.upload-progress { padding: 10px; border: 1px solid var(--ai-line); border-radius: 14px; background: #fff; }
.sidebar-actions { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; }
.doc-list { display: grid; gap: 8px; min-height: 0; overflow: auto; padding-right: 4px; }
.doc-list-item { display: grid; gap: 8px; width: 100%; padding: 13px; text-align: left; border: 1px solid transparent; border-radius: 14px; background: transparent; cursor: pointer; transition: .18s ease; }
.doc-list-item:hover, .doc-list-item.active { border-color: rgba(17, 24, 39, .12); background: rgba(255, 255, 255, .76); box-shadow: 0 10px 24px rgba(15, 23, 42, .07); }
.item-title { color: var(--ai-text); font-weight: 800; }
.item-tags { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.doc-status { display: inline-flex; align-items: center; border-radius: 999px; padding: 2px 10px; font-size: 12px; }
.doc-status.success { color: #0f7a56; background: rgba(16, 163, 127, .12); }
.doc-status.warning { color: #a16207; background: rgba(245, 158, 11, .14); }
.doc-status.error { color: #b4234a; background: rgba(208, 48, 80, .12); }
.doc-main { min-width: 0; min-height: 0; overflow: auto; padding: 24px max(26px, calc((100% - 1040px) / 2)); background: linear-gradient(180deg, #fff 0%, #fbfbf8 100%); }
.doc-header { padding-bottom: 18px; border-bottom: 1px solid var(--ai-line); }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.metric-card, .edit-panel, .preview-panel { border: 1px solid var(--ai-line); border-radius: 18px; background: rgba(255, 255, 255, .86); box-shadow: 0 12px 34px rgba(15, 23, 42, .06); }
.metric-card { padding: 16px; }
.metric-card span { color: var(--ai-muted); font-size: 12px; }
.metric-card b { display: block; margin-top: 8px; color: var(--ai-text); }
.notice-card, .edit-panel, .preview-panel { margin-top: 16px; }
.citation-highlight { border: 1px solid rgba(16, 163, 127, .32); box-shadow: 0 10px 24px rgba(16, 163, 127, .10); }
.panel-head { padding: 16px; border-bottom: 1px solid var(--ai-line); background: #fbfbf8; }
.doc-form { padding: 16px; }
.two-col { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
.preview-stack { display: grid; gap: 14px; padding: 16px; }
.chunk-preview { border: 1px solid rgba(37, 99, 235, .32); box-shadow: 0 14px 30px rgba(37, 99, 235, .12); }
.chunk-preview-title { margin-bottom: 8px; color: #1d4ed8; font-weight: 800; }
.chunk-markdown { max-height: none; border-radius: 12px; padding: 12px; background: rgba(239, 246, 255, .76); }
.markdown-preview { line-height: 1.75; word-break: break-word; }
.chunked-preview { display: grid; gap: 12px; }
.doc-chunk { border: 1px solid rgba(17, 24, 39, .10); border-radius: 16px; padding: 16px; background: #fff; transition: .18s ease; }
.doc-chunk.active { border-color: rgba(37, 99, 235, .42); background: rgba(239, 246, 255, .92); box-shadow: 0 12px 28px rgba(37, 99, 235, .14); }
.doc-chunk-meta { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 10px; color: var(--ai-muted); font-size: 12px; font-weight: 800; }
.source-editor { padding: 16px; }
.source-editor :deep(.n-input__textarea-el) { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; line-height: 1.75; }
pre { white-space: pre-wrap; word-break: break-word; margin: 16px; line-height: 1.75; }
.doc-chunk-content :deep(p), .markdown-preview :deep(p) { margin: 8px 0; }
.doc-chunk-content :deep(pre), .markdown-preview :deep(pre) { padding: 12px; border-radius: 10px; background: rgba(15, 23, 42, .08); overflow: auto; }
.doc-chunk-content :deep(code), .markdown-preview :deep(code) { padding: 2px 5px; border-radius: 5px; background: rgba(15, 23, 42, .08); }
.markdown-preview :deep(h1), .markdown-preview :deep(h2), .markdown-preview :deep(h3) { margin: 18px 0 10px; font-weight: 800; }
.markdown-preview :deep(table) { width: 100%; border-collapse: collapse; margin: 12px 0; }
.markdown-preview :deep(th), .markdown-preview :deep(td) { border: 1px solid rgba(148, 163, 184, .35); padding: 8px; text-align: left; }
.empty-state { margin-top: 20vh; }
@media (max-width: 1100px) { .doc-workspace { grid-template-columns: 1fr; height: auto; min-height: calc(100vh - 96px); } .doc-sidebar { border-right: 0; border-bottom: 1px solid var(--ai-line); } .doc-header, .panel-head { flex-direction: column; } .metric-grid, .two-col { grid-template-columns: 1fr; } }
</style>
