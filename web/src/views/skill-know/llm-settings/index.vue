<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'LLM设置' })

const loading = ref(false)
const testing = ref(false)
const saving = ref(false)
const debugging = ref(false)
const goldenRunning = ref(false)
const health = ref(null)
const state = ref(null)
const testResult = ref(null)
const retrievalDebug = ref(null)
const goldenResult = ref(null)
const goldenCases = ref([])
const goldenSaving = ref(false)
const debugQuery = ref('落地解密在哪里配置')
const lastTestAt = ref('')
const providerOptions = [
  { label: 'OpenAI 兼容', value: 'openai' },
  { label: 'Ollama', value: 'ollama' },
]
const form = reactive({
  llm_api_key: '',
  llm_chat_api_key: '',
  llm_chat_provider: 'openai',
  llm_chat_base_url: 'https://api.openai.com/v1',
  llm_chat_model: 'gpt-4o-mini',
})
const goldenForm = reactive({
  id: '',
  question: '',
  expected_heading_contains: '',
  expected_document_id: null,
  expected_section_id: null,
  enabled: true,
})

onMounted(loadState)

async function loadState() {
  loading.value = true
  try {
    const [stateRes, healthRes, goldenRes] = await Promise.all([
      api.skillKnowSetupState(),
      api.skillKnowHealthDetail(),
      api.skillKnowGoldenCases(),
    ])
    state.value = stateRes.data
    health.value = healthRes.data
    goldenCases.value = Array.isArray(goldenRes.data) ? goldenRes.data : []
    const llm = stateRes.data?.llm || {}
    Object.assign(form, {
      llm_chat_provider: llm.llm_chat_provider || form.llm_chat_provider,
      llm_chat_base_url: llm.llm_chat_base_url || llm.llm_base_url || form.llm_chat_base_url,
      llm_chat_model: llm.llm_chat_model || form.llm_chat_model,
    })
  } finally {
    loading.value = false
  }
}

function resetGoldenForm() {
  Object.assign(goldenForm, {
    id: '',
    question: '',
    expected_heading_contains: '',
    expected_document_id: null,
    expected_section_id: null,
    enabled: true,
  })
}

function editGoldenCase(item) {
  Object.assign(goldenForm, {
    id: item.id || '',
    question: item.question || '',
    expected_heading_contains: item.expected_heading_contains || '',
    expected_document_id: item.expected_document_id ?? null,
    expected_section_id: item.expected_section_id ?? null,
    enabled: item.enabled !== false,
  })
}

async function loadGoldenCases() {
  const res = await api.skillKnowGoldenCases()
  goldenCases.value = Array.isArray(res.data) ? res.data : []
}

async function saveGoldenCase() {
  if (!goldenForm.question?.trim()) {
    $message.warning('请填写黄金问题')
    return
  }
  goldenSaving.value = true
  try {
    const payload = {
      ...goldenForm,
      question: goldenForm.question.trim(),
      expected_heading_contains: goldenForm.expected_heading_contains?.trim() || null,
      expected_document_id: goldenForm.expected_document_id || null,
      expected_section_id: goldenForm.expected_section_id || null,
    }
    if (!payload.id) delete payload.id
    await api.skillKnowSaveGoldenCase(payload)
    $message.success('黄金问题已保存')
    resetGoldenForm()
    await loadGoldenCases()
  } finally {
    goldenSaving.value = false
  }
}

async function removeGoldenCase(item) {
  if (!item?.id) return
  if (!window.confirm(`确认删除黄金问题：${item.question || item.id}？`)) return
  await api.skillKnowDeleteGoldenCase({ case_id: item.id })
  $message.success('已删除')
  if (goldenForm.id === item.id) resetGoldenForm()
  await loadGoldenCases()
}

function buildPayload() {
  const payload = { ...form }
  if (!payload.llm_api_key?.trim()) delete payload.llm_api_key
  if (!payload.llm_chat_api_key?.trim()) delete payload.llm_chat_api_key
  return payload
}

async function testConnection() {
  testing.value = true
  try {
    const res = await api.skillKnowTestConnection(buildPayload())
    testResult.value = res.data
    lastTestAt.value = new Date().toLocaleString()
    if (res.data?.chat?.success) $message.success(res.data.chat.message || '对话端点连接成功')
    else $message.error(res.data?.chat?.message || '对话端点连接失败')
  } finally {
    testing.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const res = await api.skillKnowCompleteSetup(buildPayload())
    state.value = res.data
    form.llm_api_key = ''
    form.llm_chat_api_key = ''
    $message.success('保存成功')
    await loadState()
  } finally {
    saving.value = false
  }
}

async function runRetrievalDebug() {
  if (!debugQuery.value?.trim()) {
    $message.warning('请输入调试问题')
    return
  }
  debugging.value = true
  try {
    const res = await api.skillKnowRetrievalDebug({ query: debugQuery.value.trim(), top_k: 8 })
    retrievalDebug.value = res.data
  } finally {
    debugging.value = false
  }
}

async function runGoldenEval() {
  goldenRunning.value = true
  try {
    const res = await api.skillKnowGoldenEval({ top_k: 8 })
    goldenResult.value = res.data
  } finally {
    goldenRunning.value = false
  }
}

const chatTestCard = computed(() => ({
  endpoint: form.llm_chat_base_url,
  model: form.llm_chat_model,
  success: !!testResult.value?.chat?.success,
  message: testResult.value?.chat?.message || '尚未测试',
}))

const effectiveSummary = computed(() => ({
  provider: form.llm_chat_provider === 'ollama' ? 'Ollama' : 'OpenAI 兼容',
  endpoint: form.llm_chat_base_url,
  model: form.llm_chat_model,
  timeout: state.value?.llm?.llm_timeout || 120,
}))

const maskedChatKey = computed(() => state.value?.llm?.llm_chat_api_key || state.value?.llm?.llm_api_key || '')

function applyProviderDefaults() {
  if (form.llm_chat_provider === 'ollama') {
    form.llm_chat_base_url = 'http://127.0.0.1:11434'
    if (!form.llm_chat_model || form.llm_chat_model === 'gpt-4o-mini') form.llm_chat_model = 'llama3.1'
    return
  }
  if (!form.llm_chat_base_url || form.llm_chat_base_url.includes('127.0.0.1:11434')) form.llm_chat_base_url = 'https://api.openai.com/v1'
  if (!form.llm_chat_model || form.llm_chat_model === 'llama3.1') form.llm_chat_model = 'gpt-4o-mini'
}
</script>

<template>
  <CommonPage title="LLM设置" :show-header="false" show-footer>
    <div class="settings-workspace">
      <NSpin :show="loading">
        <div class="settings-inner">
          <header class="hero-panel">
            <div>
              <div class="eyebrow">Reader Agent</div>
              <h1>模型配置</h1>
              <p>Document Reading Agent 使用对话模型读取原文证据；文档解析与索引在本地确定性完成。</p>
            </div>
            <NSpace>
              <NButton secondary :loading="testing" @click="testConnection">测试对话端点</NButton>
              <NButton type="primary" :loading="saving" @click="save">保存配置</NButton>
            </NSpace>
          </header>

          <section class="summary-grid">
            <div class="summary-card">
              <span>对话模型</span>
              <b>{{ effectiveSummary.model }}</b>
              <p>{{ effectiveSummary.provider }} · {{ effectiveSummary.endpoint }}</p>
            </div>
            <div class="summary-card">
              <span>LLM 超时</span>
              <b>{{ effectiveSummary.timeout }} 秒</b>
              <p>{{ lastTestAt ? `最近测试 ${lastTestAt}` : '尚未测试连接' }}</p>
            </div>
          </section>

          <main class="settings-grid single">
            <section class="panel model-panel">
              <div class="panel-head">
                <div>
                  <h3>对话模型</h3>
                  <p>Key 留空时不会覆盖已保存值。</p>
                </div>
              </div>
              <NForm label-placement="top" class="form-stack">
                <div class="endpoint-title">
                  <b>模型端点</b>
                  <span v-if="maskedChatKey">已保存 Key：{{ maskedChatKey }}</span>
                </div>
                <NFormItem label="提供商"><NSelect v-model:value="form.llm_chat_provider" :options="providerOptions" @update:value="applyProviderDefaults" /></NFormItem>
                <NFormItem v-if="form.llm_chat_provider !== 'ollama'" label="对话 API Key"><NInput v-model:value="form.llm_chat_api_key" type="password" show-password-on="click" placeholder="留空则不覆盖已保存 Key" /></NFormItem>
                <NFormItem label="对话端点 URL"><NInput v-model:value="form.llm_chat_base_url" /></NFormItem>
                <NFormItem label="Chat Model"><NInput v-model:value="form.llm_chat_model" /></NFormItem>
              </NForm>
            </section>

          </main>

          <section class="panel health-panel">
            <div class="panel-head">
              <div>
                <h3>连接诊断</h3>
                <p>{{ lastTestAt ? `最近测试时间：${lastTestAt}` : '执行测试后会展示端点状态。' }}</p>
              </div>
            </div>
            <div class="test-card" :class="chatTestCard.success ? 'success-card' : 'error-card'">
              <div class="test-card-head">
                <b>对话端点</b>
                <NTag :type="chatTestCard.success ? 'success' : 'warning'" round>{{ chatTestCard.success ? '成功' : '未通过' }}</NTag>
              </div>
              <div class="test-meta">端点：{{ chatTestCard.endpoint }}</div>
              <div class="test-meta">模型：{{ chatTestCard.model }}</div>
              <div class="test-message">{{ chatTestCard.message }}</div>
            </div>
            <details class="health-json">
              <summary>健康状态原始数据</summary>
              <pre>{{ JSON.stringify(health, null, 2) }}</pre>
            </details>
          </section>

          <section class="panel debug-panel">
            <div class="panel-head">
              <div>
                <h3>检索调试</h3>
                <p>查看实际搜索词、强关键词、召回阶段、排序分数和命中章节。</p>
              </div>
              <NSpace>
                <NButton secondary :loading="goldenRunning" @click="runGoldenEval">运行黄金评估</NButton>
                <NButton type="primary" :loading="debugging" @click="runRetrievalDebug">调试检索</NButton>
              </NSpace>
            </div>
            <div class="debug-body">
              <NInput v-model:value="debugQuery" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="输入技术支持问题" />
              <div v-if="retrievalDebug" class="debug-summary">
                <NTag type="info">terms: {{ retrievalDebug.terms?.length || 0 }}</NTag>
                <NTag type="success">strong: {{ retrievalDebug.strong_terms?.join(' / ') || '-' }}</NTag>
                <NTag>version: {{ retrievalDebug.domain_terms_version }}</NTag>
              </div>
              <div v-if="retrievalDebug?.items?.length" class="debug-results">
                <div v-for="item in retrievalDebug.items" :key="item.section_id" class="debug-item">
                  <div class="debug-item-head">
                    <b>#{{ item.rank }} {{ item.heading_path || item.heading || item.title }}</b>
                    <NTag size="small" type="success">{{ item.score }}</NTag>
                  </div>
                  <p>{{ item.title }} · {{ item.start_line }}-{{ item.end_line }} · {{ item.stage }}</p>
                  <p>命中词：{{ item.matched_terms?.join(' / ') || '-' }}</p>
                  <p>{{ item.preview }}</p>
                </div>
              </div>
              <div v-if="goldenResult" class="golden-box">
                <b>黄金评估</b>
                <p>
                  Top1: {{ goldenResult.top1_accuracy }} · Top3: {{ goldenResult.top3_accuracy }} ·
                  TopK: {{ goldenResult.top_k_accuracy }} · 平均耗时: {{ goldenResult.avg_latency_ms }}ms
                </p>
                <p v-if="goldenResult.case_source">用例文件：{{ goldenResult.case_source }}</p>
              </div>
              <details v-if="retrievalDebug || goldenResult" class="health-json">
                <summary>检索调试原始数据</summary>
                <pre>{{ JSON.stringify({ retrievalDebug, goldenResult }, null, 2) }}</pre>
              </details>
            </div>
          </section>

          <section class="panel golden-panel">
            <div class="panel-head">
              <div>
                <h3>黄金问题集</h3>
                <p>把高频技术支持问题维护成固定评估集，用来持续验证检索是否又快又准。</p>
              </div>
              <NSpace>
                <NButton secondary @click="resetGoldenForm">清空表单</NButton>
                <NButton type="primary" :loading="goldenSaving" @click="saveGoldenCase">保存问题</NButton>
              </NSpace>
            </div>
            <div class="golden-editor">
              <NForm label-placement="top" class="golden-form">
                <NFormItem label="问题">
                  <NInput v-model:value="goldenForm.question" placeholder="例如：共享盘全盘落地解密怎么配置" />
                </NFormItem>
                <NFormItem label="期望命中标题包含">
                  <NInput v-model:value="goldenForm.expected_heading_contains" placeholder="例如：加解密、移动客户端、网关" />
                </NFormItem>
                <div class="golden-form-grid">
                  <NFormItem label="期望文档 ID">
                    <NInputNumber v-model:value="goldenForm.expected_document_id" clearable class="full-input" />
                  </NFormItem>
                  <NFormItem label="期望章节 ID">
                    <NInputNumber v-model:value="goldenForm.expected_section_id" clearable class="full-input" />
                  </NFormItem>
                  <NFormItem label="启用">
                    <NSwitch v-model:value="goldenForm.enabled" />
                  </NFormItem>
                </div>
              </NForm>
              <div class="golden-list">
                <div v-if="!goldenCases.length" class="empty-hint">暂无黄金问题。</div>
                <div v-for="item in goldenCases" :key="item.id" class="golden-item">
                  <div class="golden-main">
                    <div class="golden-title">
                      <b>{{ item.question }}</b>
                      <NTag size="small" :type="item.enabled === false ? 'default' : 'success'">
                        {{ item.enabled === false ? '停用' : '启用' }}
                      </NTag>
                    </div>
                    <p>
                      标题包含：{{ item.expected_heading_contains || '-' }} · 文档ID：{{ item.expected_document_id || '-' }} ·
                      章节ID：{{ item.expected_section_id || '-' }}
                    </p>
                  </div>
                  <NSpace>
                    <NButton size="small" secondary @click="editGoldenCase(item)">编辑</NButton>
                    <NButton size="small" secondary type="error" @click="removeGoldenCase(item)">删除</NButton>
                  </NSpace>
                </div>
              </div>
            </div>
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
}
.settings-inner { display: grid; gap: 16px; padding: 24px max(26px, calc((100% - 1120px) / 2)); }
.hero-panel { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; padding-bottom: 18px; border-bottom: 1px solid var(--ai-line); }
.eyebrow { color: #10a37f; font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
h1, h3, p { margin: 0; }
h1, h3 { color: var(--ai-text); font-weight: 800; }
h1 { margin-top: 6px; }
.hero-panel p, .panel-head p, .summary-card p, .test-meta { margin-top: 7px; color: var(--ai-muted); font-size: 13px; line-height: 1.6; word-break: break-all; }
.summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.summary-card, .panel, .test-card { border: 1px solid var(--ai-line); background: rgba(255, 255, 255, .86); box-shadow: 0 12px 34px rgba(15, 23, 42, .06); }
.summary-card { min-height: 110px; padding: 16px; border-radius: 18px; }
.summary-card span { color: var(--ai-muted); font-size: 12px; }
.summary-card b { display: block; margin-top: 8px; color: var(--ai-text); font-size: 18px; }
.settings-grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(320px, .9fr); gap: 16px; }
.settings-grid.single { grid-template-columns: minmax(0, 1fr); }
.panel { overflow: hidden; border-radius: 18px; }
.panel-head { padding: 16px; border-bottom: 1px solid var(--ai-line); background: #fbfbf8; }
.form-stack { display: grid; gap: 14px; padding: 16px; }
.endpoint-title { display: flex; justify-content: space-between; gap: 12px; color: var(--ai-text); }
.endpoint-title span { color: var(--ai-muted); font-size: 12px; }
.compact-form :deep(.n-input-number) { width: 100%; }
.test-card { margin: 16px; padding: 15px; border-radius: 16px; }
.test-card-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.test-message { margin-top: 12px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; color: var(--ai-text); }
.success-card { border-color: rgba(16, 163, 127, .30); }
.error-card { border-color: rgba(245, 158, 11, .26); }
.health-json { margin: 0 16px 16px; padding: 12px 14px; border: 1px solid var(--ai-line); border-radius: 14px; background: #fff; color: var(--ai-muted); }
.health-json summary { cursor: pointer; font-weight: 700; }
.debug-body { display: grid; gap: 14px; padding: 16px; }
.debug-summary { display: flex; flex-wrap: wrap; gap: 8px; }
.debug-results { display: grid; gap: 10px; }
.debug-item { padding: 12px; border: 1px solid var(--ai-line); border-radius: 12px; background: #fff; }
.debug-item-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.debug-item p, .golden-box p { margin-top: 6px; color: var(--ai-muted); line-height: 1.6; word-break: break-word; }
.golden-box { padding: 12px; border: 1px solid rgba(16, 163, 127, .28); border-radius: 12px; background: rgba(16, 163, 127, .06); }
.golden-editor { display: grid; gap: 14px; padding: 16px; }
.golden-form { display: grid; gap: 8px; padding: 14px; border: 1px solid var(--ai-line); border-radius: 14px; background: #fff; }
.golden-form-grid { display: grid; grid-template-columns: minmax(160px, .6fr) minmax(0, 1fr) 100px; gap: 12px; align-items: start; }
.full-input { width: 100%; }
.golden-list { display: grid; gap: 10px; }
.golden-item { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; padding: 12px; border: 1px solid var(--ai-line); border-radius: 12px; background: #fff; }
.golden-main { min-width: 0; }
.golden-title { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; color: var(--ai-text); }
.golden-main p, .empty-hint { margin-top: 6px; color: var(--ai-muted); line-height: 1.6; word-break: break-word; }
pre { margin: 12px 0 0; white-space: pre-wrap; word-break: break-word; color: var(--ai-text); }
@media (max-width: 1100px) {
  .hero-panel { flex-direction: column; }
  .summary-grid, .settings-grid { grid-template-columns: 1fr; }
  .golden-form-grid, .golden-item { grid-template-columns: 1fr; display: grid; }
}
</style>
