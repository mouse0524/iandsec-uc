<template>
  <div v-if="challengeEnabled" class="human-challenge">
    <div v-if="effectiveRequiresCaptcha" class="captcha-row">
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
      <div v-if="siteKey && !forceCaptchaFallback" ref="turnstileRef" class="cf-turnstile"></div>
      <NAlert v-else-if="!forceCaptchaFallback" type="warning" :show-icon="false">Cloudflare Turnstile Site Key 未配置</NAlert>
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
const forceCaptchaFallback = ref(false)
let turnstileWidgetId = null

let scriptPromise = window.__turnstileScriptPromise || null
const TURNSTILE_LOAD_TIMEOUT = 8000

const challengeEnabled = computed(() => appStore.loginChallengeEnabled !== false)
const challengeType = computed(() => appStore.loginChallengeType || 'captcha')
const siteKey = computed(() => appStore.turnstileSiteKey || '')
const requiresCaptcha = computed(() => challengeEnabled.value && ['captcha', 'both'].includes(challengeType.value))
const requiresTurnstile = computed(() => challengeEnabled.value && ['turnstile', 'both'].includes(challengeType.value))
const effectiveRequiresCaptcha = computed(() => requiresCaptcha.value || (requiresTurnstile.value && forceCaptchaFallback.value))

function updateCaptchaCode(value) {
  emit('update:captchaCode', value)
}

async function refreshCaptcha() {
  if (!effectiveRequiresCaptcha.value) return
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
    const timer = window.setTimeout(() => {
      scriptPromise = null
      window.__turnstileScriptPromise = null
      script.remove()
      reject(new Error('turnstile script load timeout'))
    }, TURNSTILE_LOAD_TIMEOUT)
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
    script.async = true
    script.defer = true
    script.dataset.turnstileApi = 'true'
    script.onload = () => {
      window.clearTimeout(timer)
      resolve()
    }
    script.onerror = () => {
      window.clearTimeout(timer)
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

async function enableCaptchaFallback(message) {
  emit('update:turnstileToken', '')
  turnstileError.value = message
  forceCaptchaFallback.value = true
  await refreshCaptcha()
}

async function renderTurnstile() {
  if (!requiresTurnstile.value) return
  if (forceCaptchaFallback.value) return
  if (!siteKey.value) {
    await enableCaptchaFallback('Cloudflare Turnstile Site Key 未配置，已切换为图形验证码')
    return
  }
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
        enableCaptchaFallback('Cloudflare Turnstile 加载失败，已切换为图形验证码')
      },
      'unsupported-callback': () => {
        enableCaptchaFallback('当前浏览器不支持 Cloudflare Turnstile，已切换为图形验证码')
      },
    })
  } catch {
    await enableCaptchaFallback('Cloudflare Turnstile 加载失败，已切换为图形验证码')
  }
}

function resetTurnstile() {
  emit('update:turnstileToken', '')
  if (turnstileWidgetId !== null && window.turnstile) {
    window.turnstile.reset(turnstileWidgetId)
  }
}

function retryTurnstile() {
  forceCaptchaFallback.value = false
  resetTurnstile()
  renderTurnstile()
}

defineExpose({ refreshCaptcha, resetTurnstile })

watch(effectiveRequiresCaptcha, (enabled) => {
  if (enabled) refreshCaptcha()
}, { immediate: true })

watch([requiresTurnstile, siteKey], () => {
  emit('update:turnstileToken', '')
  forceCaptchaFallback.value = false
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
