<script setup>
import { computed, h, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'
import { NButton, NProgress, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import RichTextEditor from '@/components/editor/RichTextEditor.vue'
import api from '@/api'
import { getToken, sanitizeHtml } from '@/utils'

defineOptions({ name: '文档管理' })

const loading = ref(false)
const detailLoading = ref(false)
const uploading = ref(false)
const reindexing = ref(false)
const retrying = ref(false)
const recovering = ref(false)
const saving = ref(false)
const detailVisible = ref(false)
const documents = ref([])
const selected = ref(null)
const keyword = ref('')
const fileInput = ref(null)
const chunkPreview = ref(null)
const activeTab = ref('editor')
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
const documentPage = ref(1)
const documentPageSize = ref(12)
const documentTotal = ref(0)
const secureAssetUrls = ref({})
const secureAssetObjectUrls = new Set()
const secureAssetQueue = []
const secureAssetQueued = new Set()
let secureAssetActiveCount = 0
let secureAssetObserver = null
let secureAssetGeneration = 0
const maxSecureAssetConcurrency = 3

const completedDocumentCount = computed(
  () => documents.value.filter((item) => item.status === 'completed').length,
)
const runningDocumentCount = computed(
  () => documents.value.filter((item) => ['pending', 'processing'].includes(item.status)).length,
)
const failedDocumentCount = computed(
  () => documents.value.filter((item) => item.status === 'failed').length,
)
const highlightedChunk = computed(() => {
  if (!highlightedChunkId.value) return null
  return (
    (selected.value?.chunks || []).find(
      (chunk) => String(chunk.id) === String(highlightedChunkId.value),
    ) || null
  )
})
const renderedChunks = computed(() =>
  (selected.value?.chunks || []).map((chunk) => ({
    ...chunk,
    rendered: renderDocumentContent(chunk.content),
    active: String(chunk.id) === String(highlightedChunkId.value),
  })),
)

const documentColumns = [
  {
    title: '文档名称',
    key: 'title',
    minWidth: 260,
    ellipsis: { tooltip: true },
    render: (row) => row.title || row.filename || `文档 ${row.id}`,
  },
  {
    title: '文件名',
    key: 'filename',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => row.filename || '-',
  },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render: (row) => statusTag(row.status),
  },
  {
    title: '处理进度',
    key: 'progress',
    width: 150,
    render: (row) =>
      ['processing', 'pending'].includes(row.status)
        ? h(NProgress, {
            type: 'line',
            percentage: row.extra_metadata?.process_progress || 5,
            showIndicator: false,
          })
        : '-',
  },
  {
    title: '类型',
    key: 'type',
    width: 110,
    render: (row) => row.extra_metadata?.original_file_type?.toUpperCase?.() || '-',
  },
  {
    title: '大小',
    key: 'file_size',
    width: 110,
    render: (row) => formatSize(row.file_size),
  },
  {
    title: '索引',
    key: 'index',
    width: 130,
    render: (row) => {
      const count = row.extra_metadata?.chunk_count || row.extra_metadata?.section_count
      return count ? `${count} 片段` : row.extra_metadata?.index_status || '-'
    },
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 180,
    render: (row) => row.updated_at || row.created_at || '-',
  },
  {
    title: '操作',
    key: 'actions',
    width: 110,
    fixed: 'right',
    render: (row) =>
      h(
        NButton,
        { size: 'small', type: 'primary', secondary: true, onClick: () => selectDocument(row) },
        { default: () => '详情' },
      ),
  },
]

const documentPagination = computed(() => ({
  page: documentPage.value,
  pageSize: documentPageSize.value,
  itemCount: documentTotal.value,
  pageSizes: [10, 12, 20, 50],
  showSizePicker: true,
  prefix: ({ itemCount }) => `共 ${itemCount} 条`,
}))

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

const prepareSecureDocumentAssetUrls = (html) =>
  String(html || '').replace(
    /(<img\b[^>]*?\bsrc=["'])(\/(?:api\/v1\/)?skill-know\/documents\/assets\/[^"']+)(["'][^>]*>)/gi,
    (_, prefix, src, suffix) => {
      const assetPath = normalizeDocumentAssetPath(src)
      if (!assetPath) return `${prefix}${src}${suffix}`
      const quote = suffix[0] || '"'
      const rest = suffix.slice(1)
      const lazyAttrs = rest.includes('loading=') ? '' : ' loading="lazy" decoding="async"'
      return `${prefix}${secureAssetUrls.value[assetPath] || ''}${quote} data-secure-asset="${assetPath}"${lazyAttrs}${rest}`
    },
  )

const isHtmlContent = (content) =>
  /<\/?(?:p|div|br|h[1-6]|ul|ol|li|table|thead|tbody|tr|th|td|blockquote|pre|img)\b/i.test(
    String(content || ''),
  )
const toEditorHtml = (content) => {
  const value = String(content || '').trim()
  if (!value) return ''
  const html = isHtmlContent(value) ? value : md.render(value)
  return sanitizeHtml(prepareSecureDocumentAssetUrls(html))
}
const renderDocumentContent = (content) =>
  sanitizeHtml(
    prepareSecureDocumentAssetUrls(isHtmlContent(content) ? content : md.render(content || '') || '<p>-</p>'),
  )

const restoreSecureAssetUrlsForSave = (html) => {
  const temp = document.createElement('div')
  temp.innerHTML = sanitizeHtml(String(html || ''))
  temp.querySelectorAll('img[data-secure-asset]').forEach((img) => {
    const assetPath = img.getAttribute('data-secure-asset') || ''
    if (assetPath) img.setAttribute('src', assetPath)
    img.removeAttribute('data-secure-asset')
    img.removeAttribute('loading')
    img.removeAttribute('decoding')
  })
  return sanitizeHtml(temp.innerHTML)
}

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
  secureAssetObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        const path = entry.target?.dataset?.secureAsset
        if (path) queueSecureAsset(path)
        secureAssetObserver.unobserve(entry.target)
      })
    },
    { rootMargin: '360px 0px' },
  )
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
watch([selected, highlightedChunkId, chunkPage, detailVisible], hydrateSecureAssetImages, { flush: 'post' })

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
    // 图片预览失败不阻断正文展示。
  }
}

async function loadDocuments(page = documentPage.value, pageSize = documentPageSize.value) {
  loading.value = true
  try {
    const params = { page, page_size: pageSize }
    const kw = keyword.value.trim()
    if (kw) params.keyword = kw
    const res = await api.skillKnowDocuments(params)
    documents.value = res.data || []
    documentTotal.value = Number(res.total || 0)
    documentPage.value = Number(res.page || page)
    documentPageSize.value = Number(res.page_size || pageSize)

    const queryDocumentId = Number(route.query.document_id || 0)
    if (queryDocumentId && !detailVisible.value) {
      highlightedChunkId.value = String(route.query.chunk_id || '')
      activeTab.value = 'reader'
      await selectDocument({ id: queryDocumentId, title: '文档详情' })
      await scrollToHighlightedChunk()
    } else if (selected.value?.id) {
      const current = documents.value.find((item) => item.id === selected.value.id)
      if (current) selected.value = { ...selected.value, ...current }
    }
  } finally {
    loading.value = false
  }
}

function handleTablePageChange(page) {
  documentPage.value = page
  loadDocuments(page, documentPageSize.value)
}

function handleTablePageSizeChange(pageSize) {
  documentPageSize.value = pageSize
  documentPage.value = 1
  loadDocuments(1, pageSize)
}

function handleSearch() {
  documentPage.value = 1
  loadDocuments(1, documentPageSize.value)
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
    highlightedChunkId.value = String(route.query.chunk_id || '')
    if (route.query.document_id) {
      activeTab.value = 'reader'
      await selectDocument({ id: Number(route.query.document_id), title: '文档详情' })
    } else {
      await loadDocuments()
    }
  },
)

watch(
  () => route.query.chunk_id,
  async (chunkId) => {
    highlightedChunkId.value = String(chunkId || '')
    if (route.path !== '/skill-know/documents' || !highlightedChunkId.value) return
    activeTab.value = 'reader'
    await scrollToHighlightedChunk()
  },
)

async function selectDocument(item, options = {}) {
  if (!item) return
  if (selected.value?.id !== item.id) {
    revokeSecureAssetUrls()
    chunkPage.value = 1
    chunkRefs.value = {}
  }
  selected.value = { ...item, chunks: selected.value?.id === item.id ? selected.value?.chunks || [] : [] }
  detailVisible.value = true
  if (['processing', 'pending'].includes(item.status)) startPolling(item.id)
  detailLoading.value = true
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
  } finally {
    detailLoading.value = false
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
    const pendingIndexes = Array.from({ length: totalChunks }, (_, index) => index).filter(
      (index) => !uploadedSet.has(index),
    )
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
    uploadStage.value = '后台解析文档'
    selected.value = res.data
    detailVisible.value = true
    $message.success('已开始后台转换，请稍候')
    localStorage.removeItem(resumeKey)
    startPolling(res.data.id)
    await loadDocuments(1, documentPageSize.value)
    await selectDocument(res.data, { silent: true })
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
      const res = await api.skillKnowGetDocument({
        document_id: documentId,
        chunk_page: chunkPage.value,
        chunk_page_size: chunkPageSize.value,
      })
      const doc = res.data
      documents.value = documents.value.map((item) =>
        item.id === doc.id ? { ...item, ...doc, content: undefined, chunks: undefined } : item,
      )
      if (selected.value?.id === doc.id) selected.value = doc
      if (!['processing', 'pending'].includes(doc.status)) {
        stopPolling(documentId)
        await loadDocuments()
      }
    } catch {
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
    $message.success('已开始后台重建索引')
    if (res.data?.id) startPolling(res.data.id)
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
    content: toEditorHtml(selected.value.content || ''),
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
      content: restoreSecureAssetUrlsForSave(editForm.value.content),
      category: editForm.value.category,
    })
    selected.value = res.data
    syncEditForm()
    if (reindexAfterSave) {
      const reindexed = await api.skillKnowReindexDocument({ document_id: selected.value.id })
      selected.value = reindexed.data
      syncEditForm()
      $message.success('已保存，索引将在后台重建')
      if (reindexed.data?.id) startPolling(reindexed.data.id)
    } else {
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
    content: `确定删除文档「${selected.value.title}」吗？文档内容与阅读索引都会删除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      await api.skillKnowDeleteDocument({ document_id: selected.value.id })
      selected.value = null
      detailVisible.value = false
      await loadDocuments()
    },
  })
}

function statusText(status) {
  return { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }[status] || status
}

function statusTag(status) {
  const type = status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'warning'
  return h(NTag, { size: 'small', type, bordered: false }, { default: () => statusText(status) })
}

function stageText(stage) {
  return {
    uploaded: '已上传，等待处理',
    converting: '解析文档内容中',
    analyzing: '分析内容中',
    indexing: '构建章节与行号阅读索引中',
    completed: '处理完成',
    failed: '处理失败',
  }[stage] || stage || '-'
}

function formatSize(size) {
  const value = Number(size || 0)
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, value / 1024).toFixed(1)} KB`
}

watch(selected, syncEditForm, { immediate: true })
</script>

<template>
  <CommonPage title="文档管理" :show-header="false" show-footer>
    <div class="doc-workspace">
      <header class="doc-table-header">
        <div>
          <div class="eyebrow">Knowledge Library</div>
          <h1>知识文档</h1>
          <p>上传文件后解析正文、图片和表格，构建章节与行号阅读索引；点击“详情”查看和编辑文档。</p>
        </div>
        <NSpace>
          <input ref="fileInput" type="file" class="hidden" accept=".xlsx,.pptx,.docx,.pdf,.html,.json,.txt,.md" @change="uploadFile" />
          <NButton type="primary" :loading="uploading" @click="fileInput?.click()">
            {{ uploading ? uploadStage : '上传文档' }}
          </NButton>
          <NButton secondary :loading="recovering" @click="recoverStuckDocuments">恢复卡住任务</NButton>
          <NButton secondary :loading="loading" @click="loadDocuments()">刷新</NButton>
        </NSpace>
      </header>

      <section class="library-metrics">
        <div class="library-metric">
          <span>文档总数</span>
          <b>{{ documentTotal }}</b>
        </div>
        <div class="library-metric">
          <span>本页已入库</span>
          <b>{{ completedDocumentCount }}</b>
        </div>
        <div class="library-metric" :class="{ warning: runningDocumentCount }">
          <span>本页处理中</span>
          <b>{{ runningDocumentCount }}</b>
        </div>
        <div class="library-metric" :class="{ error: failedDocumentCount }">
          <span>本页失败</span>
          <b>{{ failedDocumentCount }}</b>
        </div>
      </section>

      <section class="table-panel">
        <div class="table-toolbar">
          <NInput
            v-model:value="keyword"
            clearable
            placeholder="搜索文档名称、文件名、描述或分类"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
          <NButton type="primary" secondary @click="handleSearch">搜索</NButton>
        </div>

        <NDataTable
          :columns="documentColumns"
          :data="documents"
          :loading="loading"
          :pagination="documentPagination"
          remote
          size="small"
          :scroll-x="1360"
          @update:page="handleTablePageChange"
          @update:page-size="handleTablePageSizeChange"
        />
      </section>
    </div>

    <NDrawer v-model:show="detailVisible" :width="1040" placement="right">
      <NDrawerContent :title="selected?.title || '文档详情'" closable>
        <NSpin :show="detailLoading">
          <template v-if="selected">
            <header class="doc-header">
              <div>
                <div class="eyebrow">{{ selected.category || 'Document' }}</div>
                <h2>{{ selected.title }}</h2>
                <p>{{ selected.description || selected.filename }}</p>
              </div>
              <NSpace class="doc-actions">
                <NButton type="primary" :loading="saving" @click="saveDocument(false)">保存修改</NButton>
                <NButton secondary type="primary" :loading="saving || reindexing" @click="saveDocument(true)">保存并重建索引</NButton>
                <NButton secondary :loading="reindexing" :disabled="selected.status !== 'completed'" @click="reindexDocument">重建索引</NButton>
                <NButton v-if="selected.status === 'failed'" secondary type="warning" :loading="retrying" @click="retryDocument">重试处理</NButton>
                <NButton secondary type="error" @click="deleteDocument">删除</NButton>
              </NSpace>
            </header>

            <section class="metric-grid">
              <div class="metric-card"><span>状态</span><b>{{ statusText(selected.status) }}</b></div>
              <div class="metric-card"><span>原始类型</span><b>{{ selected.extra_metadata?.original_file_type || '-' }}</b></div>
              <div class="metric-card"><span>分类</span><b>{{ selected.category || '-' }}</b></div>
              <div class="metric-card">
                <span>阅读索引</span>
                <b>
                  {{ selected.extra_metadata?.index_status || '-' }}
                  <template v-if="selected.extra_metadata?.section_count"> / {{ selected.extra_metadata.section_count }} 章</template>
                  <template v-if="selected.extra_metadata?.line_count"> / {{ selected.extra_metadata.line_count }} 行</template>
                </b>
              </div>
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
                  <p>调整标题、分类、摘要和概览，保存后可选择同步重建阅读索引。</p>
                </div>
              </div>
              <NForm v-if="editForm" label-placement="top" class="doc-form">
                <div class="two-col">
                  <NFormItem label="标题"><NInput v-model:value="editForm.title" /></NFormItem>
                  <NFormItem label="分类"><NInput v-model:value="editForm.category" /></NFormItem>
                </div>
                <NFormItem label="描述"><NInput v-model:value="editForm.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" /></NFormItem>
                <NFormItem label="摘要"><NInput v-model:value="editForm.abstract" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" /></NFormItem>
                <NFormItem label="概览"><NInput v-model:value="editForm.overview" type="textarea" :autosize="{ minRows: 4, maxRows: 8 }" /></NFormItem>
              </NForm>
            </section>

            <section class="preview-panel">
              <div class="panel-head preview-head">
                <div>
                  <h3>文档内容</h3>
                  <p>在线编辑完整内容，或按阅读片段分页查看索引内容。</p>
                </div>
                <NButtonGroup size="small">
                  <NButton :type="activeTab === 'editor' ? 'primary' : 'default'" @click="activeTab = 'editor'">在线编辑</NButton>
                  <NButton :type="activeTab === 'reader' ? 'primary' : 'default'" @click="activeTab = 'reader'">阅读片段</NButton>
                </NButtonGroup>
              </div>

              <div v-if="activeTab === 'editor' && editForm" class="editor-stack">
                <RichTextEditor
                  v-model="editForm.content"
                  placeholder="编辑文档内容，保存后可重建阅读索引"
                  :min-height="520"
                  :max-height="760"
                />
              </div>
              <div v-else-if="activeTab === 'reader'" class="preview-stack">
                <div v-if="highlightedChunk" ref="chunkPreview">
                  <NAlert type="info" class="chunk-preview" :show-icon="false">
                    <div class="chunk-preview-title">引用片段 #{{ highlightedChunk.chunk_index + 1 }} <span v-if="highlightedChunk.heading">/ {{ highlightedChunk.heading }}</span></div>
                    <div class="markdown-preview chunk-markdown" v-html="renderDocumentContent(highlightedChunk.content)" />
                  </NAlert>
                </div>
                <div v-else-if="highlightedChunkId" ref="chunkPreview">
                  <NAlert type="warning" class="chunk-preview" :show-icon="false">
                    未找到引用块 {{ highlightedChunkId }}，可能文档已重新索引。下方显示当前页文档片段。
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
                  <div v-if="!renderedChunks.length" v-html="renderDocumentContent(editForm?.content)" />
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
              <pre v-else>{{ selected.content || '-' }}</pre>
            </section>
          </template>
          <NEmpty v-else description="暂无文档详情" />
        </NSpin>
      </NDrawerContent>
    </NDrawer>
  </CommonPage>
</template>

<style scoped>
.hidden { display: none; }
.doc-workspace {
  --line: rgba(17, 24, 39, 0.1);
  --text: #111827;
  --muted: #6b7280;
  --accent: #0f766e;
  min-height: calc(100vh - 128px);
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}
.doc-table-header,
.doc-header,
.panel-head,
.preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.eyebrow {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
h1,
h2,
h3,
p {
  margin: 0;
}
h1 {
  margin-top: 4px;
  color: var(--text);
  font-size: 24px;
  font-weight: 700;
}
h2,
h3 {
  color: var(--text);
  font-weight: 700;
}
.doc-table-header p,
.doc-header p,
.panel-head p {
  margin-top: 6px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
}
.library-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}
.library-metric,
.metric-card,
.edit-panel,
.preview-panel,
.table-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}
.library-metric {
  min-width: 0;
  padding: 12px;
  background: #fafafa;
}
.library-metric span,
.metric-card span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}
.library-metric b {
  display: block;
  margin-top: 6px;
  color: var(--text);
  font-size: 22px;
  line-height: 1;
}
.library-metric.warning b { color: #a16207; }
.library-metric.error b { color: #b4234a; }
.table-panel {
  margin-top: 16px;
  padding: 14px;
}
.table-toolbar {
  display: grid;
  grid-template-columns: minmax(240px, 420px) auto;
  gap: 10px;
  margin-bottom: 12px;
}
.doc-header {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}
.doc-actions {
  justify-content: flex-end;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}
.metric-card {
  min-width: 0;
  padding: 12px;
  background: #fafafa;
}
.metric-card b {
  display: block;
  margin-top: 6px;
  overflow: hidden;
  color: var(--text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.notice-card,
.edit-panel,
.preview-panel {
  margin-top: 16px;
}
.citation-highlight {
  border: 1px solid rgba(15, 118, 110, 0.32);
}
.panel-head {
  padding: 14px;
  border-bottom: 1px solid var(--line);
  background: #fafafa;
}
.doc-form,
.preview-stack,
.editor-stack {
  padding: 14px;
}
.two-col {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}
.editor-stack :deep(.ql-editor) {
  line-height: 1.75;
  word-break: break-word;
}
.editor-stack :deep(.ql-editor img),
.markdown-preview :deep(img) {
  display: block;
  max-width: min(100%, 960px);
  height: auto;
  max-height: 70vh;
  margin: 12px auto;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  object-fit: contain;
}
.markdown-preview :deep(img[data-secure-asset][src='']) {
  width: min(100%, 520px);
  min-height: 180px;
}
.preview-stack {
  display: grid;
  gap: 14px;
}
.chunk-preview {
  border: 1px solid rgba(37, 99, 235, 0.32);
}
.chunk-preview-title {
  margin-bottom: 8px;
  color: #1d4ed8;
  font-weight: 700;
}
.chunk-markdown {
  max-height: none;
  border-radius: 8px;
  padding: 12px;
  background: rgba(239, 246, 255, 0.76);
}
.markdown-preview {
  line-height: 1.75;
  word-break: break-word;
}
.chunked-preview {
  display: grid;
  gap: 12px;
}
.chunk-pagination {
  display: flex;
  justify-content: flex-end;
}
.doc-chunk {
  border: 1px solid rgba(17, 24, 39, 0.1);
  border-radius: 8px;
  padding: 14px;
  background: #fff;
}
.doc-chunk.active {
  border-color: rgba(37, 99, 235, 0.42);
  background: rgba(239, 246, 255, 0.92);
}
.doc-chunk-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}
pre {
  margin: 14px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}
.doc-chunk-content :deep(p),
.markdown-preview :deep(p) {
  margin: 8px 0;
}
.doc-chunk-content :deep(pre),
.markdown-preview :deep(pre) {
  padding: 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.08);
  overflow: auto;
}
.doc-chunk-content :deep(code),
.markdown-preview :deep(code) {
  padding: 2px 5px;
  border-radius: 5px;
  background: rgba(15, 23, 42, 0.08);
}
.markdown-preview :deep(h1),
.markdown-preview :deep(h2),
.markdown-preview :deep(h3) {
  margin: 18px 0 10px;
  font-weight: 700;
}
.markdown-preview :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}
.markdown-preview :deep(th),
.markdown-preview :deep(td) {
  border: 1px solid rgba(148, 163, 184, 0.35);
  padding: 8px;
  text-align: left;
}
@media (max-width: 900px) {
  .doc-table-header,
  .doc-header,
  .panel-head {
    display: grid;
  }
  .library-metrics,
  .metric-grid,
  .two-col {
    grid-template-columns: 1fr;
  }
  .table-toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
