<script setup>
import { computed, h, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { NButton, NDataTable, NEmpty, NInput, NSpin, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '知识查看' })

const loading = ref(false)
const previewLoading = ref(false)
const keyword = ref('')
const sources = ref([])
const current = ref(null)
const markdown = ref('')
const previewRef = ref(null)
const objectUrls = []
let imageScrollTarget = null
let imageScrollTimer = null

const filteredSources = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return sources.value
  return sources.value.filter((item) => `${item.title} ${item.filename}`.toLowerCase().includes(q))
})

const previewHtml = computed(() => renderMarkdown(markdown.value))

const columns = [
  { title: '文件', key: 'filename', minWidth: 180, ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render(row) {
      const type = row.status === 'completed' ? 'success' : row.status === 'failed' ? 'error' : 'warning'
      const label = { completed: '已完成', failed: '失败', pending: '待处理', building: '生成中' }[row.status] || row.status
      return h(NTag, { type, size: 'small' }, { default: () => label })
    },
  },
]

function escapeHtml(text) {
  return String(text || '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]))
}

function renderInline(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/!\[([^\]]*)\]\((assets\/[^)]+)\)/g, '<img data-wiki-asset="$2" alt="$1" loading="lazy" />')
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" loading="lazy" />')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
}

function renderMarkdown(value) {
  const lines = String(value || '').split(/\r?\n/)
  const html = []
  let listOpen = false
  let table = []
  const closeList = () => {
    if (listOpen) {
      html.push('</ul>')
      listOpen = false
    }
  }
  const flushTable = () => {
    if (!table.length) return
    const rows = table.map((line) => line.split('|').slice(1, -1).map((cell) => renderInline(cell.trim())))
    const head = rows.shift() || []
    if (rows[0]?.every((cell) => /^:?-{3,}:?$/.test(cell.replace(/<[^>]+>/g, '')))) rows.shift()
    html.push('<table><thead><tr>', ...head.map((cell) => `<th>${cell}</th>`), '</tr></thead><tbody>')
    rows.forEach((row) => html.push('<tr>', ...row.map((cell) => `<td>${cell}</td>`), '</tr>'))
    html.push('</tbody></table>')
    table = []
  }

  lines.forEach((line) => {
    if (/^\|.+\|$/.test(line.trim())) {
      closeList()
      table.push(line.trim())
      return
    }
    flushTable()
    if (!line.trim()) {
      closeList()
      html.push('')
      return
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/)
    if (heading) {
      closeList()
      const level = heading[1].length
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`)
      return
    }
    const item = line.match(/^\s*[-*]\s+(.+)$/)
    if (item) {
      if (!listOpen) {
        html.push('<ul>')
        listOpen = true
      }
      html.push(`<li>${renderInline(item[1])}</li>`)
      return
    }
    closeList()
    html.push(`<p>${renderInline(line)}</p>`)
  })
  flushTable()
  closeList()
  return html.join('\n')
}

function releaseObjectUrls() {
  while (objectUrls.length) URL.revokeObjectURL(objectUrls.pop())
}

function resetImageObserver() {
  if (imageScrollTarget) {
    imageScrollTarget.removeEventListener('scroll', scheduleVisibleImageLoad)
    imageScrollTarget = null
  }
  if (imageScrollTimer) clearTimeout(imageScrollTimer)
  imageScrollTimer = null
  releaseObjectUrls()
}

async function loadPreviewImage(img) {
  const path = img.dataset.wikiAsset
  if (!path || img.dataset.loaded) return
  img.dataset.loaded = '1'
  try {
    const blob = await api.wikiAsset({ path })
    const url = URL.createObjectURL(blob)
    objectUrls.push(url)
    img.src = url
  } catch {
    img.alt = img.alt || '图片加载失败'
  }
}

function setupLazyImages() {
  if (!previewRef.value) return
  const images = [...previewRef.value.querySelectorAll('img[data-wiki-asset]')]
  if (!images.length) return
  imageScrollTarget = previewRef.value.closest('.preview-panel')
  imageScrollTarget?.addEventListener('scroll', scheduleVisibleImageLoad, { passive: true })
  loadVisibleImages()
}

function scheduleVisibleImageLoad() {
  if (imageScrollTimer) return
  imageScrollTimer = setTimeout(() => {
    imageScrollTimer = null
    loadVisibleImages()
  }, 120)
}

function loadVisibleImages() {
  if (!previewRef.value || !imageScrollTarget) return
  const root = imageScrollTarget.getBoundingClientRect()
  const images = [...previewRef.value.querySelectorAll('img[data-wiki-asset]:not([data-loaded])')]
  let count = 0
  for (const img of images) {
    const box = img.getBoundingClientRect()
    if (box.bottom < root.top || box.top > root.bottom) continue
    loadPreviewImage(img)
    count += 1
    if (count >= 2) break
  }
}

async function openSource(row) {
  if (!row?.id || row.status !== 'completed') return
  previewLoading.value = true
  current.value = row
  resetImageObserver()
  try {
    const res = await api.wikiSourceMarkdown({ source_id: row.id })
    markdown.value = res?.data?.content || ''
    await nextTick()
    setupLazyImages()
  } finally {
    previewLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const res = await api.wikiSourceList({ page: 1, page_size: 1000 })
    sources.value = res?.data || []
    const first = sources.value.find((item) => item.status === 'completed')
    if (first) await openSource(first)
  } finally {
    loading.value = false
  }
}

onMounted(load)
onBeforeUnmount(resetImageObserver)
</script>

<template>
  <CommonPage>
    <template #action>
      <NButton :loading="loading" @click="load">刷新</NButton>
    </template>

    <div class="wiki-view-shell">
      <aside class="source-panel">
        <NInput v-model:value="keyword" placeholder="按文件名搜索" clearable />
        <NDataTable
          :loading="loading"
          :columns="columns"
          :data="filteredSources"
          :row-key="(row) => row.id"
          :row-props="(row) => ({ class: current?.id === row.id ? 'active-row' : '', onClick: () => openSource(row) })"
          size="small"
        />
      </aside>

      <main class="preview-panel">
        <NSpin :show="previewLoading">
          <template v-if="current">
            <header class="preview-header">
              <div>
                <h2>{{ current.title || current.filename }}</h2>
                <p>{{ current.filename }}</p>
              </div>
              <NTag size="small" type="info">只读 Markdown 预览</NTag>
            </header>
            <article ref="previewRef" class="markdown-preview" v-html="previewHtml"></article>
          </template>
          <NEmpty v-else description="请选择已完成的来源文件" />
        </NSpin>
      </main>
    </div>
  </CommonPage>
</template>

<style scoped>
.wiki-view-shell { height: calc(100vh - 180px); min-height: 560px; display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 12px; }
.source-panel { min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); gap: 10px; padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; overflow: hidden; }
.source-panel :deep(.n-data-table) { min-height: 0; }
.source-panel :deep(.n-data-table-base-table) { cursor: pointer; }
.source-panel :deep(.active-row td) { background: #eff6ff !important; }
.preview-panel { min-width: 0; min-height: 0; padding: 28px 34px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; overflow: auto; }
.preview-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; padding-bottom: 16px; margin-bottom: 18px; border-bottom: 1px solid #e5e7eb; }
.preview-header h2 { margin: 0; color: #111827; font-size: 24px; line-height: 1.25; letter-spacing: 0; }
.preview-header p { margin: 6px 0 0; color: #64748b; font-size: 13px; }
.markdown-preview { color: #1f2937; font-size: 14px; line-height: 1.8; }
.markdown-preview :deep(h1), .markdown-preview :deep(h2), .markdown-preview :deep(h3) { margin: 22px 0 10px; color: #111827; letter-spacing: 0; }
.markdown-preview :deep(h1) { font-size: 28px; }
.markdown-preview :deep(h2) { padding-bottom: 6px; border-bottom: 1px solid #e5e7eb; font-size: 22px; }
.markdown-preview :deep(h3) { font-size: 18px; }
.markdown-preview :deep(p) { margin: 8px 0; }
.markdown-preview :deep(ul) { padding-left: 22px; margin: 8px 0 14px; }
.markdown-preview :deep(code) { padding: 2px 5px; border-radius: 4px; background: #f1f5f9; color: #0f172a; font-family: Consolas, monospace; }
.markdown-preview :deep(img) { display: block; min-height: 120px; max-width: 100%; margin: 14px 0; border: 1px solid #e5e7eb; border-radius: 8px; background: #f8fafc; }
.markdown-preview :deep(table) { width: 100%; margin: 14px 0; border-collapse: collapse; font-size: 13px; }
.markdown-preview :deep(th), .markdown-preview :deep(td) { padding: 8px 10px; border: 1px solid #e5e7eb; text-align: left; vertical-align: top; }
.markdown-preview :deep(th) { background: #f8fafc; font-weight: 700; }
@media (max-width: 900px) {
  .wiki-view-shell { height: auto; grid-template-columns: 1fr; }
  .source-panel { max-height: 360px; }
  .preview-panel { padding: 20px 16px; }
}
</style>
