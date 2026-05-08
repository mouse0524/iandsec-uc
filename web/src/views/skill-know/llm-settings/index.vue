<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'LLM设置' })

const loading = ref(false)
const testingChat = ref(false)
const testingEmbedding = ref(false)
const saving = ref(false)
const health = ref(null)
const state = ref(null)
const testResult = ref(null)
const lastTestAt = ref('')
const form = reactive({
  llm_api_key: '',
  llm_chat_base_url: 'https://api.openai.com/v1',
  llm_embedding_base_url: 'https://api.openai.com/v1',
  llm_chat_model: 'gpt-4o-mini',
  llm_embedding_model: 'text-embedding-3-small',
  retrieval_top_k: 8,
  retrieval_score_threshold: 0.25,
  retrieval_max_context_chars: 128000,
  chunk_size: 1400,
  chunk_overlap: 150,
})

onMounted(loadState)

async function loadState() {
  loading.value = true
  try {
    const [stateRes, healthRes] = await Promise.all([api.skillKnowSetupState(), api.skillKnowHealthDetail()])
    state.value = stateRes.data
    health.value = healthRes.data
    const llm = stateRes.data?.llm || {}
    const fallbackBaseUrl = llm.llm_base_url || 'https://api.openai.com/v1'
    Object.assign(form, {
      llm_chat_base_url: llm.llm_chat_base_url || fallbackBaseUrl || form.llm_chat_base_url,
      llm_embedding_base_url: llm.llm_embedding_base_url || fallbackBaseUrl || form.llm_embedding_base_url,
      llm_chat_model: llm.llm_chat_model || form.llm_chat_model,
      llm_embedding_model: llm.llm_embedding_model || form.llm_embedding_model,
      retrieval_top_k: Number(llm.retrieval_top_k || form.retrieval_top_k),
      retrieval_score_threshold: Number(llm.retrieval_score_threshold || form.retrieval_score_threshold),
      retrieval_max_context_chars: Number(llm.retrieval_max_context_chars || form.retrieval_max_context_chars),
      chunk_size: Number(llm.chunk_size || form.chunk_size),
      chunk_overlap: Number(llm.chunk_overlap || form.chunk_overlap),
    })
  } finally {
    loading.value = false
  }
}

function buildPayload() {
  const payload = { ...form }
  if (!payload.llm_api_key?.trim()) delete payload.llm_api_key
  return payload
}

async function testChatConnection() {
  testingChat.value = true
  try {
    const payload = buildPayload()
    const res = await api.skillKnowTestConnection(payload)
    testResult.value = res.data
    lastTestAt.value = new Date().toLocaleString()
    if (res.data?.chat?.success) $message.success(res.data.chat.message || '对话端点连接成功')
    else $message.error(res.data?.chat?.message || '对话端点连接失败')
  } finally {
    testingChat.value = false
  }
}

async function testEmbeddingConnection() {
  testingEmbedding.value = true
  try {
    const payload = buildPayload()
    const res = await api.skillKnowTestConnection(payload)
    testResult.value = res.data
    lastTestAt.value = new Date().toLocaleString()
    if (res.data?.embedding?.success) $message.success(res.data.embedding.message || 'Embedding 端点连接成功')
    else $message.error(res.data?.embedding?.message || 'Embedding 端点连接失败')
  } finally {
    testingEmbedding.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const payload = { ...form }
    if (!payload.llm_api_key?.trim()) delete payload.llm_api_key
    const res = await api.skillKnowCompleteSetup(payload)
    state.value = res.data
    form.llm_api_key = ''
    $message.success('保存成功')
    await loadState()
  } finally {
    saving.value = false
  }
}

const chatTestCard = computed(() => ({
  title: '对话端点',
  endpoint: form.llm_chat_base_url,
  model: form.llm_chat_model,
  success: !!testResult.value?.chat?.success,
  message: testResult.value?.chat?.message || '尚未测试',
}))

const embeddingTestCard = computed(() => ({
  title: 'Embedding 端点',
  endpoint: form.llm_embedding_base_url,
  model: form.llm_embedding_model,
  success: !!testResult.value?.embedding?.success,
  message: testResult.value?.embedding?.message || '尚未测试',
  dimension: testResult.value?.embedding?.dimension,
}))

async function copyDiagnostics(type) {
  const card = type === 'chat' ? chatTestCard.value : embeddingTestCard.value
  const text = [
    `类型: ${card.title}`,
    `端点: ${card.endpoint}`,
    `模型: ${card.model}`,
    `状态: ${card.success ? '成功' : '失败'}`,
    `结果: ${card.message}`,
    type === 'embedding' && card.dimension ? `向量维度: ${card.dimension}` : null,
  ].filter(Boolean).join('\n')
  await navigator.clipboard.writeText(text)
  $message.success('诊断信息已复制')
}

async function copyEndpointConfig(type) {
  const data = type === 'chat'
    ? { endpoint: form.llm_chat_base_url, model: form.llm_chat_model }
    : { endpoint: form.llm_embedding_base_url, model: form.llm_embedding_model }
  await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
  $message.success('端点配置已复制')
}

function errorCategory(message) {
  const text = String(message || '').toLowerCase()
  if (!text || text === '尚未测试') return '未测试'
  if (text.includes('timeout') || text.includes('超时')) return '连接超时'
  if (text.includes('401') || text.includes('认证') || text.includes('api key')) return '鉴权失败'
  if (text.includes('403') || text.includes('权限')) return '权限问题'
  if (text.includes('404') || text.includes('not found') || text.includes('模型')) return '端点或模型错误'
  if (text.includes('connect') || text.includes('network') || text.includes('连接')) return '网络问题'
  return '其他错误'
}

const effectiveSummary = computed(() => ({
  chatEndpoint: form.llm_chat_base_url,
  chatModel: form.llm_chat_model,
  embeddingEndpoint: form.llm_embedding_base_url,
  embeddingModel: form.llm_embedding_model,
  timeout: state.value?.llm?.llm_timeout || 120,
  topK: form.retrieval_top_k,
  threshold: form.retrieval_score_threshold,
}))
</script>

<template>
  <CommonPage title="LLM设置" show-footer>
    <div class="sk-theme-page">
      <div class="sk-hero">
        <h2 class="sk-hero-title">LLM 与检索配置</h2>
        <p class="sk-hero-sub">配置 OpenAI 兼容模型、Embedding、Markdown 分块与 ChromaDB 检索参数。</p>
      </div>
      <NSpin :show="loading">
        <div class="settings-shell">
          <NCard :bordered="false" title="模型配置">
            <NForm label-placement="top">
              <NFormItem label="API Key"><NInput v-model:value="form.llm_api_key" type="password" show-password-on="click" placeholder="留空则不覆盖已保存 Key" /></NFormItem>
              <div v-if="state?.llm?.llm_api_key" class="muted">已保存 Key（脱敏）：{{ state.llm.llm_api_key }}</div>
              <NFormItem label="对话端点"><NInput v-model:value="form.llm_chat_base_url" /></NFormItem>
              <NFormItem label="Chat Model"><NInput v-model:value="form.llm_chat_model" /></NFormItem>
              <NFormItem label="Embedding 端点"><NInput v-model:value="form.llm_embedding_base_url" /></NFormItem>
              <NFormItem label="Embedding Model"><NInput v-model:value="form.llm_embedding_model" /></NFormItem>
            </NForm>
          </NCard>
          <NCard :bordered="false" title="当前生效配置摘要">
            <div class="test-meta">对话端点：{{ effectiveSummary.chatEndpoint }}</div>
            <div class="test-meta">对话模型：{{ effectiveSummary.chatModel }}</div>
            <div class="test-meta">Embedding 端点：{{ effectiveSummary.embeddingEndpoint }}</div>
            <div class="test-meta">Embedding 模型：{{ effectiveSummary.embeddingModel }}</div>
            <div class="test-meta">LLM 超时：{{ effectiveSummary.timeout }} 秒</div>
            <div class="test-meta">Top K / 阈值：{{ effectiveSummary.topK }} / {{ effectiveSummary.threshold }}</div>
          </NCard>
          <NCard :bordered="false" title="检索与分块">
            <NForm label-placement="top">
              <NFormItem label="检索 Top K"><NInputNumber v-model:value="form.retrieval_top_k" :min="1" :max="30" /></NFormItem>
              <NFormItem label="分数阈值"><NInputNumber v-model:value="form.retrieval_score_threshold" :min="0" :max="1" :step="0.05" /></NFormItem>
              <NFormItem label="最大上下文字符数"><NInputNumber v-model:value="form.retrieval_max_context_chars" :min="2000" :max="500000" :step="1000" /></NFormItem>
              <NFormItem label="分块大小"><NInputNumber v-model:value="form.chunk_size" :min="300" :max="5000" :step="100" /></NFormItem>
              <NFormItem label="分块重叠"><NInputNumber v-model:value="form.chunk_overlap" :min="0" :max="1000" :step="50" /></NFormItem>
            </NForm>
          </NCard>
          <NCard :bordered="false" title="健康状态">
            <pre>{{ JSON.stringify(health, null, 2) }}</pre>
            <div v-if="lastTestAt" class="test-meta section-card">最近测试时间：{{ lastTestAt }}</div>
            <div class="test-card-grid section-card">
              <NCard size="small" :title="chatTestCard.title" :class="chatTestCard.success ? 'success-card' : 'error-card'">
                <div class="test-meta">端点：{{ chatTestCard.endpoint }}</div>
                <div class="test-meta">模型：{{ chatTestCard.model }}</div>
                <NTag :type="chatTestCard.success ? 'success' : 'error'" class="test-tag">{{ chatTestCard.success ? '成功' : '未通过 / 未测试' }}</NTag>
                <NTag size="small" :type="chatTestCard.success ? 'success' : 'warning'">{{ errorCategory(chatTestCard.message) }}</NTag>
                <div class="test-message">{{ chatTestCard.message }}</div>
                <NSpace class="test-actions" size="small">
                  <NButton size="tiny" quaternary @click="copyDiagnostics('chat')">复制错误信息</NButton>
                  <NButton size="tiny" quaternary @click="copyEndpointConfig('chat')">复制端点配置</NButton>
                </NSpace>
              </NCard>
              <NCard size="small" :title="embeddingTestCard.title" :class="embeddingTestCard.success ? 'success-card' : 'error-card'">
                <div class="test-meta">端点：{{ embeddingTestCard.endpoint }}</div>
                <div class="test-meta">模型：{{ embeddingTestCard.model }}</div>
                <NTag :type="embeddingTestCard.success ? 'success' : 'error'" class="test-tag">{{ embeddingTestCard.success ? '成功' : '未通过 / 未测试' }}</NTag>
                <NTag size="small" :type="embeddingTestCard.success ? 'success' : 'warning'">{{ errorCategory(embeddingTestCard.message) }}</NTag>
                <div class="test-message">{{ embeddingTestCard.message }}</div>
                <div v-if="embeddingTestCard.dimension" class="test-meta">向量维度：{{ embeddingTestCard.dimension }}</div>
                <NSpace class="test-actions" size="small">
                  <NButton size="tiny" quaternary @click="copyDiagnostics('embedding')">复制错误信息</NButton>
                  <NButton size="tiny" quaternary @click="copyEndpointConfig('embedding')">复制端点配置</NButton>
                </NSpace>
              </NCard>
            </div>
            <NSpace class="actions">
              <NButton secondary :loading="testingChat" @click="testChatConnection">测试对话端点</NButton>
              <NButton secondary :loading="testingEmbedding" @click="testEmbeddingConnection">测试 Embedding 端点</NButton>
              <NButton type="primary" :loading="saving" @click="save">保存配置</NButton>
            </NSpace>
          </NCard>
        </div>
      </NSpin>
    </div>
  </CommonPage>
</template>

<style scoped>
.settings-shell { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.settings-shell > :last-child { grid-column: 1 / -1; }
.muted { color: #7b8494; margin: -8px 0 8px; }
.actions { margin-top: 16px; }
.section-card { margin-top: 16px; }
.test-card-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.test-meta { color: #64748b; margin-bottom: 6px; word-break: break-all; }
.test-tag { margin: 6px 0 10px; }
.test-message { line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.test-actions { margin-top: 12px; }
.success-card { border: 1px solid rgba(24, 160, 88, .28); }
.error-card { border: 1px solid rgba(208, 48, 80, .24); }
pre { white-space: pre-wrap; margin: 0; }
@media (max-width: 900px) { .settings-shell, .test-card-grid { grid-template-columns: 1fr; } }
</style>
