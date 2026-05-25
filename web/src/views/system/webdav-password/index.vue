<script setup>
import { computed, reactive, ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

defineOptions({ name: '密码获取' })

const loadingType = ref('')
const copyingType = ref('')
const generatedAt = reactive({
  serverOps: '',
  replaceDecrypt: '',
})
const passwords = reactive({
  serverOps: '',
  replaceDecrypt: '',
})

const todayText = computed(() => new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}))
const monthText = computed(() => new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: '2-digit',
}))

const passwordItems = computed(() => [
  {
    key: 'serverOps',
    title: '服务器运维工具密码',
    cycleLabel: '每日更新',
    cycleDescription: '工具地址：https://IP:12580, 账号admin',
    periodLabel: '生效日期',
    periodValue: todayText.value,
    value: passwords.serverOps,
    generatedAt: generatedAt.serverOps,
    icon: 'material-symbols:admin-panel-settings-outline-rounded',
    tone: 'teal',
    loader: api.webdavOpsPassword,
  },
  {
    key: 'replaceDecrypt',
    title: '替换/解密工具密码',
    cycleLabel: '每月更新',
    cycleDescription: '',
    periodLabel: '生效月份',
    periodValue: monthText.value,
    value: passwords.replaceDecrypt,
    generatedAt: generatedAt.replaceDecrypt,
    icon: 'material-symbols:lock-open-outline-rounded',
    tone: 'blue',
    loader: api.webdavReplaceDecryptPassword,
  },
])

async function loadPassword(item) {
  const res = await item.loader()
  const payload = res?.data || res || {}
  passwords[item.key] = payload.password || payload.data?.password || ''
  generatedAt[item.key] = new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

async function generatePassword(item) {
  loadingType.value = item.key
  try {
    await loadPassword(item)
    if (passwords[item.key]) {
      $message.success('密码已生成')
    } else {
      $message.error('密码生成失败，请稍后重试')
    }
  } finally {
    loadingType.value = ''
  }
}

async function copyPassword(item) {
  if (!item.value || copyingType.value) return
  copyingType.value = item.key
  try {
    await navigator.clipboard.writeText(item.value)
    $message.success('密码已复制')
  } catch (error) {
    $message.error('复制失败，请手动选中密码复制')
  } finally {
    copyingType.value = ''
  }
}
</script>

<template>
  <CommonPage title="密码获取" :show-header="false" show-footer>
    <div class="password-page">
      <header class="page-head">
        <div class="title-block">
          <div class="icon-box">
            <TheIcon icon="material-symbols:key-outline-rounded" :size="26" />
          </div>
          <div>
            <p class="eyebrow">Outbound Access</p>
            <h1>密码获取</h1>
          </div>
        </div>
      </header>

      <div class="password-layout">
        <section
          v-for="item in passwordItems"
          :key="item.key"
          class="password-container"
          :class="[item.tone, { active: item.value }]"
        >
          <div class="container-head">
            <span class="card-icon">
              <TheIcon :icon="item.icon" :size="22" />
            </span>
            <div>
              <h2>{{ item.title }}</h2>
              <p>{{ item.cycleDescription }}</p>
            </div>
            <span class="cycle-badge">{{ item.cycleLabel }}</span>
          </div>

          <div class="password-display" :class="{ masked: !item.value }">
            <span>当前密码</span>
            <strong v-if="item.value">{{ item.value }}</strong>
            <div v-else class="password-mask" aria-hidden="true">
              <i></i>
              <i></i>
              <i></i>
            </div>
          </div>

          <div class="meta-list">
            <div>
              <span>{{ item.periodLabel }}</span>
              <b>{{ item.periodValue }}</b>
            </div>
            <div>
              <span>生成时间</span>
              <b>{{ item.generatedAt || '-' }}</b>
            </div>
          </div>

          <div class="card-actions">
            <NButton
              type="primary"
              :secondary="!!item.value"
              :loading="loadingType === item.key"
              @click="generatePassword(item)"
            >
              {{ item.title }}
            </NButton>
            <NButton
              v-if="item.value"
              secondary
              :loading="copyingType === item.key"
              @click="copyPassword(item)"
            >
              复制
            </NButton>
          </div>
        </section>
      </div>
    </div>
  </CommonPage>
</template>

<style scoped>
.password-page {
  min-height: calc(100vh - 150px);
  display: flex;
  flex-direction: column;
  padding: 22px;
  background:
    linear-gradient(135deg, rgba(18, 115, 155, 0.08), transparent 42%),
    linear-gradient(315deg, rgba(58, 125, 92, 0.1), transparent 38%);
}

.page-head {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.title-block {
  display: flex;
  align-items: center;
  gap: 14px;
}

.icon-box,
.card-icon {
  display: grid;
  place-items: center;
  border-radius: 8px;
}

.icon-box {
  width: 48px;
  height: 48px;
  color: #0f766e;
  background: rgba(15, 118, 110, 0.12);
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--n-text-color-3);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-head h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.password-layout {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.password-container {
  display: flex;
  min-height: 360px;
  flex-direction: column;
  gap: 18px;
  padding: 24px;
  border: 1px solid rgba(100, 116, 139, 0.22);
  border-radius: 8px;
  background: color-mix(in srgb, var(--n-color) 94%, white 6%);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
}

.password-container.teal.active {
  border-color: rgba(15, 118, 110, 0.35);
}

.password-container.blue.active {
  border-color: rgba(37, 99, 235, 0.32);
}

.container-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.container-head > div {
  min-width: 0;
  flex: 1;
}

.container-head h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}

.container-head p {
  margin: 6px 0 0;
  color: var(--n-text-color-3);
  font-size: 13px;
  line-height: 1.5;
}

.cycle-badge {
  flex: none;
  padding: 5px 10px;
  border: 1px solid rgba(15, 118, 110, 0.22);
  border-radius: 999px;
  color: #0f766e;
  background: rgba(15, 118, 110, 0.09);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.blue .cycle-badge {
  border-color: rgba(37, 99, 235, 0.2);
  color: #2563eb;
  background: rgba(37, 99, 235, 0.09);
}

.card-icon {
  width: 40px;
  height: 40px;
  color: #0f766e;
  background: rgba(15, 118, 110, 0.12);
}

.blue .card-icon {
  color: #2563eb;
  background: rgba(37, 99, 235, 0.12);
}

.password-display {
  position: relative;
  overflow: hidden;
  display: flex;
  min-height: 132px;
  flex-direction: column;
  justify-content: center;
  padding: 22px;
  border: 1px solid rgba(100, 116, 139, 0.16);
  border-radius: 8px;
  background: var(--n-action-color);
}

.password-display.masked {
  background:
    linear-gradient(135deg, rgba(148, 163, 184, 0.12), rgba(255, 255, 255, 0.48)),
    var(--n-action-color);
}

.password-display.masked::after {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(6px);
  content: '';
  pointer-events: none;
}

.active.teal .password-display {
  background: rgba(15, 118, 110, 0.08);
}

.active.blue .password-display {
  background: rgba(37, 99, 235, 0.08);
}

.password-display span,
.meta-list span {
  display: block;
  margin-bottom: 8px;
  color: var(--n-text-color-3);
  font-size: 12px;
}

.password-display strong {
  font-family: Consolas, Monaco, monospace;
  font-size: clamp(30px, 3.2vw, 44px);
  font-weight: 700;
  letter-spacing: 0;
  word-break: break-all;
}

.password-mask {
  display: grid;
  gap: 10px;
}

.password-mask i {
  display: block;
  height: 16px;
  border-radius: 999px;
  background:
    linear-gradient(90deg, rgba(148, 163, 184, 0.16), rgba(148, 163, 184, 0.36), rgba(148, 163, 184, 0.16));
  filter: blur(0.4px);
}

.password-mask i:nth-child(1) {
  width: 78%;
}

.password-mask i:nth-child(2) {
  width: 92%;
}

.password-mask i:nth-child(3) {
  width: 62%;
}

.meta-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.meta-list > div {
  padding: 14px;
  border: 1px solid rgba(100, 116, 139, 0.14);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.42);
}

.meta-list b {
  font-size: 15px;
  font-weight: 700;
}

.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: auto;
}

@media (max-width: 860px) {
  .password-page {
    padding: 14px;
  }

  .page-head {
    align-items: stretch;
    flex-direction: column;
  }

  .password-layout,
  .meta-list {
    grid-template-columns: 1fr;
  }

  .password-container {
    min-height: 360px;
  }
}
</style>
