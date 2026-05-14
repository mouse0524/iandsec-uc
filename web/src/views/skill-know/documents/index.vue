<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'
import { getToken, sanitizeHtml } from '@/utils'

defineOptions({ name: '文档管理' })

const loading = ref(false)
const uploading = ref(false)
const reindexing = ref(false)
const retrying = ref(false)
const recovering = ref(false)
const diagnosing = ref(false)
const saving = ref(false)
const documents = ref([])
const selected = ref(null)
const keyword = ref('')
const fileInput = ref(null)
const chunkPreview = ref(null)
const activeTab = ref('preview')
const pollingTimers = new Map()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const apiBase = (import.meta.env.VITE_BASE_API || '/api/v1').replace(/\/$/, '')
const uploadStage = ref('')
const uploadResumeKeyPrefix = 'skill-know-upload:'
const uploadRetryLimit = 2
const editForm = ref(null)
const route = useRoute()
const highlightedChunkId = ref('')
const chunkRefs = ref({})
const chunkPage = ref(1)
const chunkPageSize = ref(10)
const chunkTotal = ref(0)
const secureAssetUrls = ref({})
const secureAssetObjectUrls = new Set()
const secureAssetQueue = []
const secureAssetQueued = new Set()
let secureAssetActiveCount = 0
let secureAssetObserver = null
let secureAssetGeneration = 0
const maxSecureAssetConcurrency = 3
const indexDiagnosis = ref(null)

const filteredDocuments = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return documents.value
  return documents.value.filter((item) => `${item.title} ${item.filename} ${item.content || ''}`.toLowerCase().includes(kw))
})
const completedDocumentCount = computed(() => documents.value.filter((item) => item.status === 'completed').length)
const runningDocumentCount = computed(() => documents.value.filter((item) => ['pending', 'processing'].includes(item.status)).length)
const failedDocumentCount = computed(() => documents.value.filter((item) => item.status === 'failed').length)

onMounted(loadDocuments)
onUnmounted(() => {
  stopAllPolling()
  revokeSecureAssetUrls()
  secureAssetObserver?.disconnect()
})

const normalizeDocumentAssetPath = (src) => {
  const value = String(src || '').trim().replace(/^\/api\/v1/i, '')
  const match = value.match(/^\/skill-know\/documents\/assets\/\d+\/[^?#]+/i)
  return match ? match[0] : ''
}
const prepareSecureDocumentAssetUrls = (html) => {
  return String(html || '').replace(/(<img\b[^>]*?\bsrc=["'])(\/(?:api\/v1\/)?skill-know\/documents\/assets\/[^"']+)(["'][^>]*>)/gi, (_, prefix, src, suffix) => {
    const assetPath = normalizeDocumentAssetPath(src)
    if (!assetPath) return `${prefix}${src}${suffix}`
    const quote = suffix[0] || '"'
    const rest = suffix.slice(1)
    const lazyAttrs = rest.includes('loading=') ? '' : ' loading="lazy" decoding="async"'
    return `${prefix}${secureAssetUrls.value[assetPath] || ''}${quote} data-secure-asset="${assetPath}"${lazyAttrs}${rest}`
  })
}
const renderedMarkdown = computed(() => prepareSecureDocumentAssetUrls(md.render(selected.value?.content || '')))
const renderMarkdown = (content) => sanitizeHtml(prepareSecureDocumentAssetUrls(md.render(content || '') || '<p>-</p>'))
function revokeSecureAssetUrls() {
  secureAssetGeneration += 1
  secureAssetObjectUrls.forEach((url) => URL.revokeObjectURL(url))
  secureAssetObjectUrls.clear()
  secureAssetQueue.length = 0
  secureAssetQueued.clear()
  secureAssetUrls.value = {}
  secureAssetObserver?.disconnect()
}

function initSecureAssetObserver() {
  if (secureAssetObserver) return secureAssetObserver
  secureAssetObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return
      const path = entry.target?.dataset?.secureAsset
      if (path) queueSecureAsset(path)
      secureAssetObserver.unobserve(entry.target)
    })
  }, { rootMargin: '360px 0px' })
  return secureAssetObserver
}

async function hydrateSecureAssetImages() {
  await nextTick()
  const observer = initSecureAssetObserver()
  document.querySelectorAll('img[data-secure-asset]').forEach((img) => {
    const path = img.dataset.secureAsset
    if (!path || secureAssetUrls.value[path] || secureAssetQueued.has(path)) return
    observer.observe(img)
  })
}

watch(secureAssetUrls, hydrateSecureAssetImages, { flush: 'post' })
watch([selected, highlightedChunkId, chunkPage], hydrateSecureAssetImages, { flush: 'post' })

function queueSecureAsset(path) {
  if (!path || secureAssetUrls.value[path] || secureAssetQueued.has(path)) return
  secureAssetQueued.add(path)
  secureAssetQueue.push(path)
  drainSecureAssetQueue()
}

function drainSecureAssetQueue() {
  while (secureAssetActiveCount < maxSecureAssetConcurrency && secureAssetQueue.length) {
    const path = secureAssetQueue.shift()
    const generation = secureAssetGeneration
    secureAssetActiveCount += 1
    fetchSecureDocumentAsset(path, generation).finally(() => {
      secureAssetActiveCount -= 1
      drainSecureAssetQueue()
    })
  }
}

async function fetchSecureDocumentAsset(path, generation) {
  try {
    const resp = await fetch(`${apiBase}${path}`, {
      headers: { token: getToken() || '' },
    })
    if (!resp.ok) return
    const blobUrl = URL.createObjectURL(await resp.blob())
    if (generation !== secureAssetGeneration) {
      URL.revokeObjectURL(blobUrl)
      return
    }
    secureAssetObjectUrls.add(blobUrl)
    secureAssetUrls.value = { ...secureAssetUrls.value, [path]: blobUrl }
  } catch {
    // 图片预览失败时保留占位，不影响文档正文阅读。
  }
}
const highlightedChunk = computed(() => {
  if (!highlightedChunkId.value) return null
  return (selected.value?.chunks || []).find((chunk) => String(chunk.id) === String(highlightedChunkId.value)) || null
})
const renderedChunks = computed(() => (selected.value?.chunks || []).map((chunk) => ({
  ...chunk,
  rendered: renderMarkdown(chunk.content),
  active: String(chunk.id) === String(highlightedChunkId.value),
})))
const chunkPageCount = computed(() => Math.max(1, Math.ceil((chunkTotal.value || 0) / chunkPageSize.value)))

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
  if (selected.value?.id !== item.id) revokeSecureAssetUrls()
  selected.value = item
  if (['processing', 'pending'].includes(item.status)) startPolling(item.id)
  try {
    const params = {
      document_id: item.id,
      chunk_page: chunkPage.value,
      chunk_page_size: chunkPageSize.value,
    }
    if (highlightedChunkId.value) params.chunk_id = highlightedChunkId.value
    const res = await api.skillKnowGetDocument(params)
    selected.value = res.data
    chunkPage.value = Number(res.data?.chunk_page || chunkPage.value || 1)
    chunkPageSize.value = Number(res.data?.chunk_page_size || chunkPageSize.value || 10)
    chunkTotal.value = Number(res.data?.chunk_total || res.data?.chunks?.length || 0)
    if (highlightedChunkId.value) await scrollToHighlightedChunk()
    if (['processing', 'pending'].includes(res.data?.status)) startPolling(item.id)
    else stopPolling(item.id)
  } catch (error) {
    if (!options.silent) $message.error(error.message || '获取文档详情失败')
  }
}

async function changeChunkPage(page) {
  chunkPage.value = page
  highlightedChunkId.value = ''
  await selectDocument(selected.value, { silent: true })
}

async function changeChunkPageSize(pageSize) {
  chunkPageSize.value = pageSize
  chunkPage.value = 1
  highlightedChunkId.value = ''
  await selectDocument(selected.value, { silent: true })
}

async function uploadFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (uploading.value) {
    $message.warning('已有文件正在上传，请稍候')
    e.target.value = ''
    return
  }
  uploading.value = true
  uploadStage.value = '初始化上传任务'
  try {
    const chunkSize = 2 * 1024 * 1024
    const concurrency = 4
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

    uploadStage.value = `上传文件分片 ${uploadedSet.size}/${totalChunks}`
    const pendingIndexes = Array.from({ length: totalChunks }, (_, index) => index).filter((index) => !uploadedSet.has(index))
    let cursor = 0
    async function uploadChunk(index) {
      const start = index * chunkSize
      const end = Math.min(file.size, start + chunkSize)
      const blob = file.slice(start, end)
      const formData = new FormData()
      formData.append('upload_id', uploadId)
      formData.append('chunk_index', String(index))
      formData.append('total_chunks', String(totalChunks))
      formData.append('file', blob, `${file.name}.part`)
      for (let attempt = 0; attempt <= uploadRetryLimit; attempt += 1) {
        try {
          await api.skillKnowUploadChunk(formData)
          uploadedSet.add(index)
          uploadStage.value = `上传文件分片 ${uploadedSet.size}/${totalChunks}`
          return
        } catch (error) {
          if (attempt >= uploadRetryLimit) throw error
          await new Promise((resolve) => window.setTimeout(resolve, 600 * (attempt + 1)))
        }
      }
    }
    async function worker() {
      while (cursor < pendingIndexes.length) {
        const index = pendingIndexes[cursor]
        cursor += 1
        await uploadChunk(index)
      }
    }
    await Promise.all(Array.from({ length: Math.min(concurrency, pendingIndexes.length) }, worker))

    const finalStatus = await api.skillKnowChunkUploadStatus({ upload_id: uploadId, total_chunks: totalChunks })
    const uploadedCount = Number(finalStatus.data?.uploaded_count || 0)
    if (uploadedCount !== totalChunks) {
      throw new Error(`分片上传未完成：${uploadedCount}/${totalChunks}`)
    }

    uploadStage.value = '提交合并任务'
    const res = await api.skillKnowCompleteChunkUpload({
      upload_id: uploadId,
      filename: file.name,
      title: file.name,
      file_size: file.size,
      total_chunks: totalChunks,
    })
    uploadStage.value = '后台转换 Markdown'
    selected.value = res.data
    $message.success('已开始后台转换，请稍候')
    localStorage.removeItem(resumeKey)
    startPolling(res.data.id)
    await loadDocuments()
  } catch (error) {
    $message.error(error.message || '上传失败，请重新选择同一文件续传')
  } finally {
    uploading.value = false
    uploadStage.value = ''
    e.target.value = ''
  }
}

function startPolling(documentId) {
  if (!documentId || pollingTimers.has(documentId)) return
  const timer = window.setInterval(async () => {
    try {
      const res = await api.skillKnowGetDocument({ document_id: documentId, chunk_page: chunkPage.value, chunk_page_size: chunkPageSize.value })
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

async function retryDocument() {
  if (!selected.value) return
  retrying.value = true
  try {
    const res = await api.skillKnowRetryDocument({ document_id: selected.value.id })
    selected.value = res.data
    $message.success(res.data?.status === 'processing' ? '已重新提交处理任务' : '已根据现有内容重建索引')
    if (['processing', 'pending'].includes(res.data?.status)) startPolling(res.data.id)
    await loadDocuments()
  } finally {
    retrying.value = false
  }
}

async function recoverStuckDocuments() {
  recovering.value = true
  try {
    const res = await api.skillKnowRecoverStuckDocuments({ older_than_minutes: 30 })
    const data = res.data || {}
    $message.success(`已检查 ${data.checked || 0} 个任务，恢复 ${data.recovered || 0} 个，标记失败 ${data.failed || 0} 个`)
    await loadDocuments()
  } finally {
    recovering.value = false
  }
}

async function diagnoseIndex(testEmbedding = false) {
  diagnosing.value = true
  try {
    const res = await api.skillKnowIndexDiagnose({ test_embedding: testEmbedding })
    indexDiagnosis.value = res.data
    const count = res.data?.collections?.skill_know_documents?.count
    const dimension = res.data?.embedding_test?.dimension
    $message.success(`索引诊断完成${Number.isFinite(count) ? `，向量数 ${count}` : ''}${dimension ? `，维度 ${dimension}` : ''}`)
  } finally {
    diagnosing.value = false
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
          <NButton size="small" secondary :loading="loading" @click="loadDocuments">刷新</NButton>
        </div>

        <div class="library-metrics">
          <div class="library-metric">
            <span>文档</span>
            <b>{{ documents.length }}</b>
          </div>
          <div class="library-metric">
            <span>已入库</span>
            <b>{{ completedDocumentCount }}</b>
          </div>
          <div class="library-metric" :class="{ warning: runningDocumentCount }">
            <span>处理中</span>
            <b>{{ runningDocumentCount }}</b>
          </div>
          <div class="library-metric" :class="{ error: failedDocumentCount }">
            <span>失败</span>
            <b>{{ failedDocumentCount }}</b>
          </div>
        </div>

        <input ref="fileInput" type="file" class="hidden" accept=".xlsx,.pptx,.docx,.pdf,.html,.json,.txt,.md" @change="uploadFile" />
        <div class="upload-card" @click="fileInput?.click()">
          <div class="upload-mark">
            <icon-material-symbols:upload-file-outline-rounded text-24 />
          </div>
          <div>
            <b>{{ uploading ? uploadStage : '上传知识文档' }}<span v-if="!uploading">点击选择</span></b>
            <p>XLSX、PPTX、DOCX、PDF、HTML、JSON、TXT、MD 均可转换入库，最大 1G。</p>
          </div>
        </div>
        <div class="sidebar-actions">
          <NInput v-model:value="keyword" class="document-search-input" clearable placeholder="搜索文档、文件名或内容" />
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
            <NSpace class="doc-actions">
              <NButton type="primary" :loading="saving" @click="saveDocument(false)">保存修改</NButton>
              <NButton secondary type="primary" :loading="saving || reindexing" @click="saveDocument(true)">保存并重建索引</NButton>
              <NButton secondary :loading="reindexing" :disabled="selected.status !== 'completed'" @click="reindexDocument">重建索引</NButton>
              <NButton v-if="selected.status === 'failed'" secondary type="warning" :loading="retrying" @click="retryDocument">重试处理</NButton>
              <NButton secondary :loading="recovering" @click="recoverStuckDocuments">恢复卡住任务</NButton>
              <NDropdown
                trigger="click"
                :options="[
                  { label: '仅检查索引库', key: 'basic' },
                  { label: '检查索引库和 Embedding', key: 'embedding' },
                ]"
                @select="(key) => diagnoseIndex(key === 'embedding')"
              >
                <NButton secondary :loading="diagnosing">索引诊断</NButton>
              </NDropdown>
              <NButton secondary type="error" @click="deleteDocument">删除</NButton>
            </NSpace>
          </header>

          <section class="metric-grid">
            <div class="metric-card"><span>状态</span><b>{{ statusText(selected.status) }}</b></div>
            <div class="metric-card"><span>原始类型</span><b>{{ selected.extra_metadata?.original_file_type || '-' }}</b></div>
            <div class="metric-card"><span>分类</span><b>{{ selected.category || '-' }}</b></div>
            <div class="metric-card"><span>索引</span><b>{{ selected.extra_metadata?.index_status || '-' }}<template v-if="selected.extra_metadata?.chunk_count"> / {{ selected.extra_metadata.chunk_count }} 块</template><template v-if="selected.extra_metadata?.vector_count !== undefined"> / {{ selected.extra_metadata.vector_count }} 向量</template></b></div>
          </section>

          <NAlert v-if="['processing', 'pending'].includes(selected.status)" type="info" class="notice-card">
            {{ stageText(selected.extra_metadata?.process_stage) }}，进度 {{ selected.extra_metadata?.process_progress || 5 }}%
            <NProgress type="line" :percentage="selected.extra_metadata?.process_progress || 5" />
          </NAlert>
          <NAlert v-if="highlightedChunkId" type="success" class="notice-card citation-highlight" :show-icon="false">
            已定位到智能对话引用片段，引用块 ID：{{ highlightedChunkId }}。
          </NAlert>
          <NAlert v-if="selected.error_message" type="error" class="notice-card">{{ selected.error_message }}</NAlert>
          <NAlert v-if="indexDiagnosis" type="info" class="notice-card" :show-icon="false">
            Chroma：{{ indexDiagnosis.chromadb_available ? '可用' : '不可用' }}；
            向量数：{{ indexDiagnosis.collections?.skill_know_documents?.count ?? '-' }}；
            Embedding：{{ indexDiagnosis.embedding_provider || '-' }} / {{ indexDiagnosis.embedding_model || '-' }}
            <template v-if="indexDiagnosis.embedding_test">；测试：{{ indexDiagnosis.embedding_test.success ? '成功' : '失败' }}<template v-if="indexDiagnosis.embedding_test.dimension"> / {{ indexDiagnosis.embedding_test.dimension }} 维</template></template>
          </NAlert>

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
              <div v-if="chunkTotal > chunkPageSize" class="chunk-pagination">
                <NPagination
                  :page="chunkPage"
                  :page-size="chunkPageSize"
                  :item-count="chunkTotal"
                  :page-sizes="[10, 20, 50]"
                  show-size-picker
                  @update:page="changeChunkPage"
                  @update:page-size="changeChunkPageSize"
                />
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
.doc-workspace {
  --ai-bg: #f7f7f4;
  --ai-sidebar: #f1f0ea;
  --ai-line: rgba(17, 24, 39, .10);
  --ai-text: #111827;
  --ai-muted: #6b7280;
  --ai-accent: #10a37f;
  --ai-primary: var(--primary-color, #f4511e);
  display: grid;
  grid-template-columns: 352px minmax(0, 1fr);
  height: calc(100vh - 96px);
  min-height: 620px;
  overflow: hidden;
  border: 1px solid var(--ai-line);
  border-radius: 18px;
  background: var(--ai-bg);
  box-shadow: 0 18px 50px rgba(15, 23, 42, .08);
}
.doc-sidebar {
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto auto auto minmax(0, 1fr);
  gap: 14px;
  padding: 18px;
  border-right: 1px solid var(--ai-line);
  background: linear-gradient(180deg, #f3f2ed 0%, var(--ai-sidebar) 100%);
}
.sidebar-head, .doc-header, .panel-head, .preview-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.eyebrow { color: var(--ai-accent); font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
h1, h2, h3, p { margin: 0; }
h1, h2, h3 { color: var(--ai-text); font-weight: 800; }
.sidebar-head h2, .doc-header h1 { margin-top: 6px; }
.sidebar-head p, .doc-header p, .panel-head p, .upload-card p, .item-desc { margin-top: 7px; color: var(--ai-muted); font-size: 13px; line-height: 1.6; }
.library-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.library-metric {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--ai-line);
  border-radius: 12px;
  background: rgba(255, 255, 255, .68);
}
.library-metric span {
  display: block;
  color: var(--ai-muted);
  font-size: 12px;
  white-space: nowrap;
}
.library-metric b {
  display: block;
  margin-top: 5px;
  color: var(--ai-text);
  font-size: 20px;
  line-height: 1;
}
.library-metric.warning b { color: #a16207; }
.library-metric.error b { color: #b4234a; }
.upload-card {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  padding: 14px;
  border: 1px dashed rgba(17, 24, 39, .24);
  border-radius: 14px;
  background: rgba(255, 255, 255, .72);
  cursor: pointer;
  transition: .18s ease;
}
.upload-card:hover {
  transform: translateY(-1px);
  border-color: rgba(16, 163, 127, .48);
  background: #fff;
  box-shadow: 0 12px 26px rgba(15, 23, 42, .07);
}
.upload-card b {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--ai-text);
}
.upload-card b span {
  color: var(--ai-accent);
  font-size: 12px;
  font-weight: 800;
}
.upload-mark {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: #111827;
  color: #fff;
}
.sidebar-actions { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; align-items: center; min-height: 34px; }
.document-search-input { min-width: 0; width: 100%; }
.document-search-input :deep(.n-input-wrapper) { min-height: 34px; }
.doc-sidebar :deep(.n-spin-container),
.doc-sidebar :deep(.n-spin-content) {
  min-height: 0;
  height: 100%;
}
.doc-list { display: grid; align-content: start; gap: 8px; min-height: 0; max-height: 100%; overflow-y: auto; padding-right: 4px; }
.doc-list-item {
  position: relative;
  display: grid;
  gap: 8px;
  width: 100%;
  padding: 13px;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 14px;
  background: transparent;
  cursor: pointer;
  transition: .18s ease;
}
.doc-list-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 999px;
  background: transparent;
}
.doc-list-item:hover, .doc-list-item.active {
  border-color: rgba(17, 24, 39, .12);
  background: rgba(255, 255, 255, .82);
  box-shadow: 0 10px 24px rgba(15, 23, 42, .07);
}
.doc-list-item.active::before { background: var(--ai-primary); }
.item-title {
  overflow: hidden;
  color: var(--ai-text);
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-tags { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.doc-status { display: inline-flex; align-items: center; border-radius: 999px; padding: 2px 10px; font-size: 12px; }
.doc-status.success { color: #0f7a56; background: rgba(16, 163, 127, .12); }
.doc-status.warning { color: #a16207; background: rgba(245, 158, 11, .14); }
.doc-status.error { color: #b4234a; background: rgba(208, 48, 80, .12); }
.doc-main { min-width: 0; min-height: 0; overflow: auto; padding: 24px max(26px, calc((100% - 1040px) / 2)); background: linear-gradient(180deg, #fff 0%, #fbfbf8 100%); }
.doc-header { padding-bottom: 18px; border-bottom: 1px solid var(--ai-line); }
.doc-actions { justify-content: flex-end; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.metric-card, .edit-panel, .preview-panel { border: 1px solid var(--ai-line); border-radius: 16px; background: rgba(255, 255, 255, .86); box-shadow: 0 12px 34px rgba(15, 23, 42, .06); }
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
.markdown-preview :deep(img) {
  display: block;
  max-width: min(100%, 960px);
  height: auto;
  max-height: 70vh;
  margin: 12px auto;
  border: 1px solid rgba(17, 24, 39, .08);
  border-radius: 10px;
  background: #f6f7f8;
  object-fit: contain;
}
.markdown-preview :deep(img[data-secure-asset][src=""]) {
  width: min(100%, 520px);
  min-height: 180px;
}
.chunked-preview { display: grid; gap: 12px; }
.chunk-pagination { display: flex; justify-content: flex-end; padding-top: 2px; }
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
@media (max-width: 1100px) {
  .doc-workspace { grid-template-columns: 1fr; height: auto; min-height: calc(100vh - 96px); }
  .doc-sidebar { border-right: 0; border-bottom: 1px solid var(--ai-line); }
  .doc-header, .panel-head { flex-direction: column; }
  .metric-grid, .two-col { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .library-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .doc-main { padding: 18px; }
  .doc-actions { justify-content: flex-start; }
}
</style>
