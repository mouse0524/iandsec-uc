<script setup>
import { onMounted, reactive, ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'LLM设置' })

const loading = ref(false)
const testing = ref(false)
const saving = ref(false)
const health = ref(null)
const state = ref(null)
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

async function testConnection() {
  testing.value = true
  try {
    const payload = { ...form }
    if (!payload.llm_api_key?.trim()) delete payload.llm_api_key
    const res = await api.skillKnowTestConnection(payload)
    if (res.data?.success) $message.success(res.data.message || '连接成功')
    else $message.error(res.data?.message || '连接失败')
  } finally {
    testing.value = false
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
            <NSpace class="actions"><NButton secondary :loading="testing" @click="testConnection">测试连接</NButton><NButton type="primary" :loading="saving" @click="save">保存配置</NButton></NSpace>
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
pre { white-space: pre-wrap; margin: 0; }
@media (max-width: 900px) { .settings-shell { grid-template-columns: 1fr; } }
</style>
