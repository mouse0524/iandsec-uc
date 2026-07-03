<template>
  <div v-if="challengeEnabled" class="human-challenge">
    <div v-if="requiresCaptcha" class="captcha-row">
      <NInput
        :value="captchaCode"
        :placeholder="captchaPlaceholder"
        style="width: 180px"
        @update:value="updateCaptchaCode"
      />
      <img :src="captchaImage" alt="captcha" class="captcha-img" @click="refreshCaptcha" />
      <NButton text type="primary" @click="refreshCaptcha">换一张</NButton>
    </div>
    <div v-if="requiresTurnstile" class="turnstile-wrap">
      <div v-if="siteKey" ref="turnstileRef" class="cf-turnstile"></div>
      <NAlert v-else type="warning" :show-icon="false">Cloudflare Turnstile Site Key 未配置</NAlert>
      <NAlert v-if="turnstileError" type="error" :show-icon="false" class="turnstile-error">
        {{ turnstileError }}
        <NButton text type="primary" @click="retryTurnstile">重试</NButton>
      </NAlert>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { NAlert, NButton, NInput } from 'naive-ui'
import api from '@/api'
import { useAppStore } from '@/store'

const props = defineProps({
  captchaId: { type: String, default: '' },
  captchaCode: { type: String, default: '' },
  turnstileToken: { type: String, default: '' },
  captchaPlaceholder: { type: String, default: '请输入验证码' },
})

const emit = defineEmits([
  'update:captchaId',
  'update:captchaCode',
  'update:turnstileToken',
  'refreshed',
])

const appStore = useAppStore()
const captchaImage = ref('')
const turnstileRef = ref(null)
const turnstileError = ref('')
let turnstileWidgetId = null

let scriptPromise = window.__turnstileScriptPromise || null

const challengeEnabled = computed(() => appStore.loginChallengeEnabled !== false)
const challengeType = computed(() => appStore.loginChallengeType || 'captcha')
const siteKey = computed(() => appStore.turnstileSiteKey || '')
const requiresCaptcha = computed(() => challengeEnabled.value && ['captcha', 'both'].includes(challengeType.value))
const requiresTurnstile = computed(() => challengeEnabled.value && ['turnstile', 'both'].includes(challengeType.value))

function updateCaptchaCode(value) {
  emit('update:captchaCode', value)
}

async function refreshCaptcha() {
  if (!requiresCaptcha.value) return
  const res = await api.getCaptcha()
  emit('update:captchaId', res.data.captcha_id)
  emit('update:captchaCode', '')
  captchaImage.value = `data:image/png;base64,${res.data.image_base64}`
  emit('refreshed')
}

function loadTurnstileScript() {
  if (window.turnstile) return Promise.resolve()
  if (scriptPromise) return scriptPromise
  document.querySelector('script[data-turnstile-api="true"]')?.remove()
  scriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
    script.async = true
    script.defer = true
    script.dataset.turnstileApi = 'true'
    script.onload = resolve
    script.onerror = () => {
      scriptPromise = null
      window.__turnstileScriptPromise = null
      script.remove()
      reject(new Error('turnstile script load failed'))
    }
    document.head.appendChild(script)
  })
  window.__turnstileScriptPromise = scriptPromise
  return scriptPromise
}

async function renderTurnstile() {
  if (!requiresTurnstile.value || !siteKey.value) return
  await nextTick()
  if (!turnstileRef.value) return
  try {
    turnstileError.value = ''
    await loadTurnstileScript()
    if (turnstileWidgetId !== null && window.turnstile) {
      window.turnstile.remove(turnstileWidgetId)
      turnstileWidgetId = null
    }
    turnstileWidgetId = window.turnstile.render(turnstileRef.value, {
      sitekey: siteKey.value,
      callback: (token) => {
        turnstileError.value = ''
        emit('update:turnstileToken', token || '')
      },
      'expired-callback': () => emit('update:turnstileToken', ''),
      'error-callback': () => {
        emit('update:turnstileToken', '')
        turnstileError.value = 'Cloudflare Turnstile 加载失败，请点击重试'
      },
      'unsupported-callback': () => {
        emit('update:turnstileToken', '')
        turnstileError.value = '当前浏览器不支持 Cloudflare Turnstile，请更换浏览器或关闭跟踪拦截后重试'
      },
    })
  } catch {
    emit('update:turnstileToken', '')
    turnstileError.value = 'Cloudflare Turnstile 加载失败，请点击重试'
  }
}

function resetTurnstile() {
  emit('update:turnstileToken', '')
  if (turnstileWidgetId !== null && window.turnstile) {
    window.turnstile.reset(turnstileWidgetId)
  }
}

function retryTurnstile() {
  resetTurnstile()
  renderTurnstile()
}

defineExpose({ refreshCaptcha, resetTurnstile })

watch(requiresCaptcha, (enabled) => {
  if (enabled) refreshCaptcha()
}, { immediate: true })

watch([requiresTurnstile, siteKey], () => {
  emit('update:turnstileToken', '')
  renderTurnstile()
}, { immediate: true })

onBeforeUnmount(() => {
  if (turnstileWidgetId !== null && window.turnstile) {
    window.turnstile.remove(turnstileWidgetId)
  }
})
</script>

<style scoped>
.human-challenge {
  display: grid;
  gap: 10px;
}

.captcha-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.captcha-img {
  flex: none;
  width: 122px;
  height: 36px;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  cursor: pointer;
  object-fit: cover;
}

.turnstile-wrap {
  min-height: 65px;
}

.turnstile-error {
  margin-top: 8px;
}
</style>
