<script setup>
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import 'vue-files-preview/lib/style.css'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

defineOptions({ name: 'WebdavFilePreview' })

const previewLoaders = {
  audio: () => import('vue-files-preview/es/packages/preview/supports/audio-preview/index.vue.mjs'),
  code: () => import('vue-files-preview/es/packages/preview/supports/code-preview/index.vue.mjs'),
  docx: () => import('vue-files-preview/es/packages/preview/supports/docx-preview/index.vue.mjs'),
  epub: () => import('vue-files-preview/es/packages/preview/supports/epub-preview/index.vue.mjs'),
  md: () => import('vue-files-preview/es/packages/preview/supports/md-preview/index.vue.mjs'),
  msg: () => import('vue-files-preview/es/packages/preview/supports/msg-preview/index.vue.mjs'),
  pdf: () => import('vue-files-preview/es/packages/preview/supports/pdf-preview/index.vue.mjs'),
  pic: () => import('vue-files-preview/es/packages/preview/supports/pic-preview/index.vue.mjs'),
  ppt: () => import('vue-files-preview/es/packages/preview/supports/ppt-preview/index.vue.mjs'),
  txt: () => import('vue-files-preview/es/packages/preview/supports/txt-preview/index.vue.mjs'),
  unknown: () => import('vue-files-preview/es/packages/preview/supports/unknown-preview/index.vue.mjs'),
  video: () => import('vue-files-preview/es/packages/preview/supports/video-preview/index.vue.mjs'),
  xlsx: () => import('vue-files-preview/es/packages/preview/supports/xlsx-preview/index.vue.mjs'),
}

const previewTypes = {
  audio: ['mp3', 'wav', 'wma', 'ogg', 'aac', 'flac'],
  code: ['html', 'css', 'less', 'scss', 'js', 'json', 'ts', 'vue', 'c', 'cpp', 'java', 'py', 'go', 'php', 'lua', 'rb', 'pl', 'swift', 'vb', 'cs', 'sh', 'rs', 'vim', 'log', 'lock', 'mod', 'mht', 'mhtml', 'xml'],
  docx: ['docx'],
  epub: ['epub'],
  md: ['md'],
  msg: ['msg'],
  pdf: ['pdf'],
  pic: ['jpg', 'png', 'jpeg', 'webp', 'gif', 'bmp', 'svg', 'ico'],
  ppt: ['ppt', 'pptx', 'fodp', 'odp', 'otp', 'pot', 'potm', 'potx', 'pps', 'ppsm', 'ppsx', 'pptm'],
  txt: ['txt'],
  unknown: ['doc', 'docm', 'dot', 'dotm', 'dotx', 'fodt', 'odt', 'ott', 'rtf', 'djvu', 'xps'],
  video: ['mp4', 'webm', 'ogg', 'mkv', 'avi', 'mpeg', 'flv', 'mov', 'wmv'],
  xlsx: ['xlsx', 'xls', 'csv', 'fods', 'ods', 'ots', 'xlsm', 'xlt', 'xltm'],
}

function previewType(name) {
  const ext = String(name || '').split('.').pop()?.toLowerCase()
  return Object.keys(previewTypes).find((type) => previewTypes[type].includes(ext)) || 'unknown'
}

const route = useRoute()
const fileUrl = ref('')
const loading = ref(false)
const errorMessage = ref('')

const fileName = computed(() => {
  const value = route.query.name
  return Array.isArray(value) ? value[0] || '文件预览' : value || '文件预览'
})

const filePath = computed(() => {
  const value = route.query.path
  return Array.isArray(value) ? value[0] || '' : value || ''
})

const PreviewComponent = computed(() => defineAsyncComponent(previewLoaders[previewType(fileName.value)]))

function buildAbsoluteApiUrl(apiUrl) {
  if (!apiUrl) return ''
  if (/^https?:\/\//i.test(apiUrl)) return apiUrl
  const path = apiUrl.startsWith('/') ? apiUrl : `/${apiUrl}`
  return `${window.location.origin}${path}`
}

async function preparePreview() {
  if (!filePath.value) {
    errorMessage.value = '预览参数不完整，请返回网盘页面重新打开文件。'
    return
  }
  try {
    loading.value = true
    errorMessage.value = ''
    const res = await api.webdavPreviewCache({ path: filePath.value })
    const previewUrl = buildAbsoluteApiUrl(res?.data?.preview_url || '')
    if (!previewUrl) {
      errorMessage.value = '预览链接生成失败，请稍后重试。'
      return
    }
    fileUrl.value = previewUrl
  } catch (error) {
    errorMessage.value = error?.message || error?.msg || '文件缓存失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

function downloadFile() {
  if (!fileUrl.value) return
  const link = document.createElement('a')
  link.href = fileUrl.value
  link.target = '_blank'
  link.rel = 'noopener noreferrer'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

onMounted(() => {
  preparePreview()
})
</script>

<template>
  <main class="preview-page">
    <header class="preview-header">
      <div class="title-block">
        <div class="title-icon" aria-hidden="true">
          <TheIcon icon="material-symbols:preview-rounded" :size="24" />
        </div>
        <div class="title-copy">
          <h1>{{ fileName }}</h1>
          <span>{{ fileUrl ? '在线查看' : '正在准备预览' }}</span>
        </div>
      </div>
      <button class="download-button" type="button" :disabled="!fileUrl" @click="downloadFile">
        下载
      </button>
    </header>

    <section v-if="fileUrl" class="preview-shell">
      <component :is="PreviewComponent" :url="fileUrl" :name="fileName" height="100%" overflow="auto" />
    </section>
    <section v-else class="empty-state">
      <TheIcon
        :icon="errorMessage ? 'material-symbols:link-off-rounded' : 'line-md:loading-twotone-loop'"
        :size="42"
      />
      <h2>{{ errorMessage || '正在缓存文件' }}</h2>
      <p>{{ errorMessage || '文件准备好后会自动打开预览。' }}</p>
    </section>
  </main>
</template>

<style scoped>
.preview-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: #102033;
  background: #f6f8fb;
}

.preview-header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 18px;
  border-bottom: 1px solid rgba(15, 23, 42, .1);
  background: rgba(255, 255, 255, .96);
}

.title-block {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #0f766e;
  background: #e6f7f4;
}

.title-copy {
  min-width: 0;
}

.title-copy h1 {
  margin: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 16px;
  line-height: 1.35;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-copy span {
  color: #64748b;
  font-size: 12px;
}

.download-button {
  min-width: 72px;
  height: 34px;
  border: 1px solid rgba(15, 118, 110, .22);
  border-radius: 8px;
  color: #0f766e;
  background: #ecfdf5;
  font-weight: 800;
  cursor: pointer;
}

.download-button:disabled {
  opacity: .55;
  cursor: not-allowed;
}

.preview-shell {
  flex: 1;
  min-height: 0;
  height: calc(100vh - 64px);
  overflow: auto;
  padding: 12px;
}

.preview-shell :deep(.vue-files-preview) {
  height: 100% !important;
  min-height: 100%;
  overflow: auto !important;
}

.preview-shell :deep(.docx-preview) {
  min-height: 100%;
}

.empty-state {
  flex: 1;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: #64748b;
  text-align: center;
}

.empty-state h2 {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
}

.empty-state p {
  margin: 0;
}

@media (max-width: 640px) {
  .preview-header {
    height: auto;
    align-items: stretch;
    flex-direction: column;
    padding: 12px;
  }

  .download-button {
    width: 100%;
  }
}
</style>
