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
  markdown_optimize_enabled: true,
  markdown_optimize_prompt: '',
  markdown_optimize_max_chars: 30000,
  markdown_optimize_timeout: 45,
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
      markdown_optimize_enabled: llm.markdown_optimize_enabled !== false,
      markdown_optimize_prompt: llm.markdown_optimize_prompt || form.markdown_optimize_prompt,
      markdown_optimize_max_chars: Number(llm.markdown_optimize_max_chars || form.markdown_optimize_max_chars),
      markdown_optimize_timeout: Number(llm.markdown_optimize_timeout || form.markdown_optimize_timeout),
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
  <CommonPage title="LLM设置" :show-header="false" show-footer>
    <div class="settings-workspace">
      <NSpin :show="loading">
        <div class="settings-inner">
          <header class="hero-panel">
            <div>
              <div class="eyebrow">Model Console</div>
              <h1>LLM 与检索配置</h1>
              <p>配置 OpenAI 兼容模型、Embedding、Markdown 分块与 ChromaDB 检索参数。</p>
            </div>
            <NSpace>
              <NButton secondary :loading="testingChat" @click="testChatConnection">测试对话端点</NButton>
              <NButton secondary :loading="testingEmbedding" @click="testEmbeddingConnection">测试 Embedding</NButton>
              <NButton type="primary" :loading="saving" @click="save">保存配置</NButton>
            </NSpace>
          </header>

          <section class="summary-grid">
            <div class="summary-card">
              <span>对话模型</span>
              <b>{{ effectiveSummary.chatModel }}</b>
              <p>{{ effectiveSummary.chatEndpoint }}</p>
            </div>
            <div class="summary-card">
              <span>Embedding 模型</span>
              <b>{{ effectiveSummary.embeddingModel }}</b>
              <p>{{ effectiveSummary.embeddingEndpoint }}</p>
            </div>
            <div class="summary-card">
              <span>Top K / 阈值</span>
              <b>{{ effectiveSummary.topK }} / {{ effectiveSummary.threshold }}</b>
              <p>最大上下文 {{ form.retrieval_max_context_chars }} 字符</p>
            </div>
            <div class="summary-card">
              <span>LLM 超时</span>
              <b>{{ effectiveSummary.timeout }} 秒</b>
              <p>{{ lastTestAt ? `最近测试 ${lastTestAt}` : '尚未测试连接' }}</p>
            </div>
          </section>

          <main class="settings-grid">
            <section class="panel model-panel">
              <div class="panel-head">
                <div>
                  <h3>模型配置</h3>
                  <p>配置对话和向量模型端点，API Key 留空时不会覆盖已保存值。</p>
                </div>
              </div>
              <NForm label-placement="top" class="form-stack">
                <NFormItem label="API Key"><NInput v-model:value="form.llm_api_key" type="password" show-password-on="click" placeholder="留空则不覆盖已保存 Key" /></NFormItem>
                <div v-if="state?.llm?.llm_api_key" class="muted">已保存 Key（脱敏）：{{ state.llm.llm_api_key }}</div>
                <div class="two-col">
                  <NFormItem label="对话端点"><NInput v-model:value="form.llm_chat_base_url" /></NFormItem>
                  <NFormItem label="Chat Model"><NInput v-model:value="form.llm_chat_model" /></NFormItem>
                  <NFormItem label="Embedding 端点"><NInput v-model:value="form.llm_embedding_base_url" /></NFormItem>
                  <NFormItem label="Embedding Model"><NInput v-model:value="form.llm_embedding_model" /></NFormItem>
                </div>
              </NForm>
            </section>

            <section class="panel retrieval-panel">
              <div class="panel-head">
                <div>
                  <h3>检索与分块</h3>
                  <p>控制召回数量、上下文窗口和 Markdown 分块策略。</p>
                </div>
              </div>
              <NForm label-placement="top" class="form-stack compact-form">
                <NFormItem label="检索 Top K"><NInputNumber v-model:value="form.retrieval_top_k" :min="1" :max="30" /></NFormItem>
                <NFormItem label="分数阈值"><NInputNumber v-model:value="form.retrieval_score_threshold" :min="0" :max="1" :step="0.05" /></NFormItem>
                <NFormItem label="最大上下文字符数"><NInputNumber v-model:value="form.retrieval_max_context_chars" :min="2000" :max="500000" :step="1000" /></NFormItem>
                <NFormItem label="分块大小"><NInputNumber v-model:value="form.chunk_size" :min="300" :max="5000" :step="100" /></NFormItem>
                <NFormItem label="分块重叠"><NInputNumber v-model:value="form.chunk_overlap" :min="0" :max="1000" :step="50" /></NFormItem>
                <NFormItem label="分片前优化"><NSwitch v-model:value="form.markdown_optimize_enabled" /></NFormItem>
                <NFormItem label="优化最大字符数"><NInputNumber v-model:value="form.markdown_optimize_max_chars" :min="1000" :max="200000" :step="1000" /></NFormItem>
                <NFormItem label="优化超时秒数"><NInputNumber v-model:value="form.markdown_optimize_timeout" :min="5" :max="300" :step="5" /></NFormItem>
                <NFormItem label="Markdown 优化提示词">
                  <NInput
                    v-model:value="form.markdown_optimize_prompt"
                    type="textarea"
                    placeholder="留空使用默认 markdown-beautifier 提示词"
                    :autosize="{ minRows: 6, maxRows: 12 }"
                  />
                </NFormItem>
              </NForm>
            </section>
          </main>

          <section class="panel health-panel">
            <div class="panel-head">
              <div>
                <h3>连接诊断</h3>
                <p>{{ lastTestAt ? `最近测试时间：${lastTestAt}` : '执行测试后会展示端点状态和错误分类。' }}</p>
              </div>
            </div>
            <div class="test-card-grid">
              <div class="test-card" :class="chatTestCard.success ? 'success-card' : 'error-card'">
                <div class="test-card-head">
                  <b>{{ chatTestCard.title }}</b>
                  <NTag :type="chatTestCard.success ? 'success' : 'warning'" round>{{ chatTestCard.success ? '成功' : errorCategory(chatTestCard.message) }}</NTag>
                </div>
                <div class="test-meta">端点：{{ chatTestCard.endpoint }}</div>
                <div class="test-meta">模型：{{ chatTestCard.model }}</div>
                <div class="test-message">{{ chatTestCard.message }}</div>
                <NSpace class="test-actions" size="small">
                  <NButton size="tiny" quaternary @click="copyDiagnostics('chat')">复制错误信息</NButton>
                  <NButton size="tiny" quaternary @click="copyEndpointConfig('chat')">复制端点配置</NButton>
                </NSpace>
              </div>
              <div class="test-card" :class="embeddingTestCard.success ? 'success-card' : 'error-card'">
                <div class="test-card-head">
                  <b>{{ embeddingTestCard.title }}</b>
                  <NTag :type="embeddingTestCard.success ? 'success' : 'warning'" round>{{ embeddingTestCard.success ? '成功' : errorCategory(embeddingTestCard.message) }}</NTag>
                </div>
                <div class="test-meta">端点：{{ embeddingTestCard.endpoint }}</div>
                <div class="test-meta">模型：{{ embeddingTestCard.model }}</div>
                <div v-if="embeddingTestCard.dimension" class="test-meta">向量维度：{{ embeddingTestCard.dimension }}</div>
                <div class="test-message">{{ embeddingTestCard.message }}</div>
                <NSpace class="test-actions" size="small">
                  <NButton size="tiny" quaternary @click="copyDiagnostics('embedding')">复制错误信息</NButton>
                  <NButton size="tiny" quaternary @click="copyEndpointConfig('embedding')">复制端点配置</NButton>
                </NSpace>
              </div>
            </div>
            <details class="health-json">
              <summary>健康状态原始数据</summary>
              <pre>{{ JSON.stringify(health, null, 2) }}</pre>
            </details>
          </section>
        </div>
      </NSpin>
    </div>
  </CommonPage>
</template>

<style scoped>
.settings-workspace {
  --ai-bg: #f7f7f4;
  --ai-line: rgba(17, 24, 39, .10);
  --ai-text: #111827;
  --ai-muted: #6b7280;
  height: calc(100vh - 96px);
  min-height: 560px;
  overflow: auto;
  border: 1px solid var(--ai-line);
  border-radius: 20px;
  background: linear-gradient(180deg, #fff 0%, var(--ai-bg) 100%);
  box-shadow: 0 18px 50px rgba(15, 23, 42, .08);
}
.settings-inner {
  display: grid;
  gap: 16px;
  padding: 24px max(26px, calc((100% - 1120px) / 2));
}
.hero-panel {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--ai-line);
}
.eyebrow {
  color: #10a37f;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}
h1, h3, p { margin: 0; }
h1, h3 { color: var(--ai-text); font-weight: 800; }
h1 { margin-top: 6px; }
.hero-panel p, .panel-head p, .summary-card p, .muted, .test-meta {
  margin-top: 7px;
  color: var(--ai-muted);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-all;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.summary-card, .panel, .test-card {
  border: 1px solid var(--ai-line);
  background: rgba(255, 255, 255, .86);
  box-shadow: 0 12px 34px rgba(15, 23, 42, .06);
}
.summary-card {
  min-height: 110px;
  padding: 16px;
  border-radius: 18px;
}
.summary-card span {
  color: var(--ai-muted);
  font-size: 12px;
}
.summary-card b {
  display: block;
  margin-top: 8px;
  color: var(--ai-text);
  font-size: 18px;
}
.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, .85fr);
  gap: 16px;
}
.panel {
  overflow: hidden;
  border-radius: 18px;
}
.panel-head {
  padding: 16px;
  border-bottom: 1px solid var(--ai-line);
  background: #fbfbf8;
}
.form-stack {
  padding: 16px;
}
.two-col {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}
.compact-form :deep(.n-input-number) {
  width: 100%;
}
.health-panel {
  margin-bottom: 2px;
}
.test-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  padding: 16px;
}
.test-card {
  padding: 15px;
  border-radius: 16px;
}
.test-card-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.test-message {
  margin-top: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--ai-text);
}
.test-actions {
  margin-top: 12px;
}
.success-card { border-color: rgba(16, 163, 127, .30); }
.error-card { border-color: rgba(245, 158, 11, .26); }
.health-json {
  margin: 0 16px 16px;
  padding: 12px 14px;
  border: 1px solid var(--ai-line);
  border-radius: 14px;
  background: #fff;
  color: var(--ai-muted);
}
.health-json summary {
  cursor: pointer;
  font-weight: 700;
}
pre {
  margin: 12px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--ai-text);
}
@media (max-width: 1100px) {
  .hero-panel { flex-direction: column; }
  .summary-grid, .settings-grid, .test-card-grid { grid-template-columns: 1fr; }
  .two-col { grid-template-columns: 1fr; }
}
</style>
