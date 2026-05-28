<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: 'PublicWebdavShareDownload' })

const DOWNLOAD_DELAY_MS = 3000
const REDIRECT_AFTER_STATE_MS = 120
const route = useRoute()
const errorMessage = ref('')
const downloadState = ref('checking')

const statusText = computed(() => {
  if (errorMessage.value) return '链接不可用'
  return downloadState.value === 'downloading' ? '下载中' : '下载准备中'
})

const messageText = computed(() =>
  downloadState.value === 'downloading'
    ? '下载中，请在浏览器下载列表查看文件...'
    : '正在校验链接并跳转下载，请稍候...',
)

onMounted(() => {
  const params = new URLSearchParams()
  ;['code', 'ts', 'sig'].forEach((key) => {
    const value = route.query[key]
    if (Array.isArray(value)) {
      if (value[0]) params.set(key, value[0])
    } else if (value) {
      params.set(key, value)
    }
  })

  if (!params.get('code') || !params.get('ts') || !params.get('sig')) {
    errorMessage.value = '下载链接缺少必要参数，请重新复制最新链接'
    return
  }

  const downloadUrl = `/api/v1/public/webdav/share/download?${params.toString()}`
  window.setTimeout(() => {
    downloadState.value = 'downloading'
    window.setTimeout(() => {
      window.location.replace(downloadUrl)
    }, REDIRECT_AFTER_STATE_MS)
  }, DOWNLOAD_DELAY_MS)
})
</script>

<template>
  <main class="public-download-page">
    <div class="background-grid" aria-hidden="true"></div>

    <section class="download-panel">
      <div class="panel-mark" :class="{ error: errorMessage }">
        <TheIcon
          :icon="
            errorMessage ? 'material-symbols:link-off-rounded' : 'material-symbols:download-rounded'
          "
          :size="34"
        />
      </div>

      <div class="panel-copy">
        <span class="status-badge" :class="{ error: errorMessage }">
          {{ statusText }}
        </span>
        <h1>公开下载</h1>
        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
        <p v-else class="message">{{ messageText }}</p>
      </div>

      <div v-if="!errorMessage" class="progress-wrap" aria-hidden="true">
        <span class="progress-bar"></span>
      </div>
    </section>
  </main>
</template>

<style scoped>
.public-download-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  position: relative;
  overflow: hidden;
  padding: 24px;
  color: #132238;
  background:
    radial-gradient(circle at 18% 18%, rgba(24, 128, 120, 0.14), transparent 34%),
    radial-gradient(circle at 82% 28%, rgba(37, 99, 235, 0.12), transparent 30%),
    linear-gradient(135deg, #f8fbff 0%, #eef6f3 48%, #f6f8fb 100%);
}

.background-grid {
  position: absolute;
  inset: 0;
  opacity: 0.44;
  background-image:
    linear-gradient(rgba(19, 34, 56, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(19, 34, 56, 0.05) 1px, transparent 1px);
  background-size: 36px 36px;
  mask-image: linear-gradient(to bottom, transparent, #000 18%, #000 78%, transparent);
}

.download-panel {
  width: min(460px, 100%);
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  padding: 34px 32px 30px;
  border: 1px solid rgba(114, 132, 154, 0.24);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 22px 70px rgba(19, 34, 56, 0.14);
  text-align: center;
  backdrop-filter: blur(18px);
}

.download-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.76);
}

.panel-mark {
  width: 76px;
  height: 76px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(13, 148, 136, 0.22);
  border-radius: 50%;
  color: #0f766e;
  background: linear-gradient(145deg, rgba(240, 253, 250, 0.94), rgba(219, 234, 254, 0.72));
  box-shadow: 0 16px 34px rgba(13, 148, 136, 0.16);
}

.panel-mark.error {
  border-color: rgba(220, 38, 38, 0.2);
  color: #b42318;
  background: linear-gradient(145deg, #fff5f5, #fff7ed);
  box-shadow: 0 16px 34px rgba(220, 38, 38, 0.12);
}

.panel-copy {
  width: 100%;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  margin-bottom: 12px;
  padding: 0 10px;
  border: 1px solid rgba(13, 148, 136, 0.2);
  border-radius: 999px;
  color: #0f766e;
  background: rgba(240, 253, 250, 0.84);
  font-size: 12px;
  font-weight: 700;
}

.status-badge.error {
  border-color: rgba(220, 38, 38, 0.2);
  color: #b42318;
  background: rgba(254, 242, 242, 0.9);
}

.download-panel h1 {
  margin: 0;
  color: #0f172a;
  font-size: 28px;
  line-height: 1.2;
  font-weight: 700;
}

.message {
  margin: 12px 0 0;
  color: #526173;
  font-size: 15px;
  line-height: 1.7;
}

.error-message {
  margin: 12px 0 0;
  color: #9f1f19;
  font-size: 15px;
  line-height: 1.7;
}

.progress-wrap {
  width: 100%;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: #e5edf4;
}

.progress-bar {
  display: block;
  width: 42%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0f766e, #2563eb);
  animation: progress-slide 1.15s ease-in-out infinite;
}

@keyframes progress-slide {
  0% {
    transform: translateX(-110%);
  }

  100% {
    transform: translateX(250%);
  }
}

@media (max-width: 520px) {
  .public-download-page {
    padding: 18px;
  }

  .download-panel {
    padding: 30px 22px 26px;
  }

  .download-panel h1 {
    font-size: 24px;
  }
}
</style>
