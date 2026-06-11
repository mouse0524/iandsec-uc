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
let turnstileWidgetId = null
let scriptPromise = null

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
  scriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
    script.async = true
    script.defer = true
    script.onload = resolve
    script.onerror = reject
    document.head.appendChild(script)
  })
  return scriptPromise
}

async function renderTurnstile() {
  if (!requiresTurnstile.value || !siteKey.value) return
  await nextTick()
  if (!turnstileRef.value) return
  await loadTurnstileScript()
  if (turnstileWidgetId !== null && window.turnstile) {
    window.turnstile.remove(turnstileWidgetId)
    turnstileWidgetId = null
  }
  turnstileWidgetId = window.turnstile.render(turnstileRef.value, {
    sitekey: siteKey.value,
    callback: (token) => emit('update:turnstileToken', token || ''),
    'expired-callback': () => emit('update:turnstileToken', ''),
    'error-callback': () => emit('update:turnstileToken', ''),
  })
}

function resetTurnstile() {
  emit('update:turnstileToken', '')
  if (turnstileWidgetId !== null && window.turnstile) {
    window.turnstile.reset(turnstileWidgetId)
  }
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
</style>
