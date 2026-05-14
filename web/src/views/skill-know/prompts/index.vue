<script setup>
import { computed, onMounted, ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '提示词管理' })

const loading = ref(false)
const saving = ref(false)
const syncing = ref(false)
const prompts = ref([])
const selected = ref(null)
const activeCategory = ref('all')

const categoryOptions = [
  { label: '全部', value: 'all' },
  { label: '对话', value: 'chat' },
  { label: '系统', value: 'system' },
  { label: '技能', value: 'skill' },
  { label: '分类', value: 'classification' },
  { label: '搜索', value: 'search' },
]

const categoryLabels = {
  chat: '对话',
  system: '系统',
  skill: '技能',
  classification: '分类',
  search: '搜索',
}

const filteredPrompts = computed(() => {
  if (activeCategory.value === 'all') return prompts.value
  return prompts.value.filter((item) => item.category === activeCategory.value)
})

const skillPrompt = computed(() => prompts.value.find((item) => item.key === 'markdown.beautifier'))

onMounted(loadPrompts)

async function loadPrompts() {
  loading.value = true
  try {
    const res = await api.skillKnowPrompts({ include_inactive: true })
    prompts.value = res.data?.items || []
    if (!selected.value && skillPrompt.value) selected.value = skillPrompt.value
    if (!selected.value && prompts.value.length) selected.value = prompts.value[0]
    if (selected.value) {
      selected.value = prompts.value.find((item) => item.key === selected.value.key) || filteredPrompts.value[0] || prompts.value[0] || null
    }
  } finally {
    loading.value = false
  }
}

async function syncDefaultPrompts() {
  syncing.value = true
  try {
    const res = await api.skillKnowSyncDefaultPrompts()
    const created = res.data?.created || 0
    const updated = res.data?.updated || 0
    const deleted = res.data?.deleted || 0
    const changes = [
      created ? `新增 ${created}` : '',
      updated ? `更新 ${updated}` : '',
      deleted ? `删除 ${deleted}` : '',
    ].filter(Boolean)
    $message.success(changes.length ? `默认提示词已同步：${changes.join('，')}` : '默认提示词已是最新')
    await loadPrompts()
    if (skillPrompt.value) {
      activeCategory.value = 'skill'
      selected.value = skillPrompt.value
    }
  } finally {
    syncing.value = false
  }
}

async function savePrompt() {
  if (!selected.value) return
  saving.value = true
  try {
    await api.skillKnowUpdatePrompt(selected.value.key, { content: selected.value.content, is_active: selected.value.is_active })
    $message.success('保存成功')
    await loadPrompts()
  } finally {
    saving.value = false
  }
}

async function resetPrompt() {
  if (!selected.value) return
  const res = await api.skillKnowResetPrompt(selected.value.key)
  selected.value = res.data
  $message.success('已重置默认提示词')
}
</script>

<template>
  <CommonPage title="提示词管理" :show-header="false" show-footer>
    <div class="ai-workspace prompt-workspace">
      <aside class="ai-sidebar prompt-sidebar">
        <div class="sidebar-head">
          <div>
            <div class="eyebrow">Prompt Studio</div>
            <h2>提示词</h2>
            <p>管理检索、生成和对话输出的系统模板。</p>
          </div>
          <NTag size="small" round>{{ prompts.length }} 个模板</NTag>
        </div>

        <div class="sidebar-tools">
          <div class="category-tabs">
            <button
              v-for="item in categoryOptions"
              :key="item.value"
              type="button"
              :class="{ active: activeCategory === item.value }"
              @click="activeCategory = item.value"
            >
              {{ item.label }}
            </button>
          </div>
          <NButton size="small" secondary :loading="syncing" @click="syncDefaultPrompts">同步默认</NButton>
        </div>

        <NSpin :show="loading">
          <div class="prompt-list">
            <button
              v-for="item in filteredPrompts"
              :key="item.key"
              class="prompt-item"
              :class="{ active: selected?.key === item.key }"
              type="button"
              @click="selected = item"
            >
              <span class="prompt-name">{{ item.name }}</span>
              <span class="prompt-desc">{{ item.description }}</span>
              <span class="prompt-meta">
                <NTag size="small" round>{{ categoryLabels[item.category] || item.category }}</NTag>
                <span :class="['status-dot', item.is_active ? 'online' : 'offline']" />
              </span>
            </button>
            <NEmpty v-if="!filteredPrompts.length" description="暂无提示词" />
          </div>
        </NSpin>
      </aside>

      <section class="ai-main prompt-main">
        <template v-if="selected">
          <header class="main-header">
            <div>
              <div class="eyebrow">{{ selected.key }}</div>
              <h1>{{ selected.name }}</h1>
              <p>{{ selected.description || '编辑当前提示词内容和启用状态。' }}</p>
            </div>
            <NSpace align="center">
              <div class="switch-wrap">
                <span>{{ selected.is_active ? '已启用' : '已停用' }}</span>
                <NSwitch v-model:value="selected.is_active" />
              </div>
              <NButton secondary @click="resetPrompt">重置</NButton>
              <NButton type="primary" :loading="saving" @click="savePrompt">保存</NButton>
            </NSpace>
          </header>

          <div class="variable-panel">
            <div>
              <b>可用变量</b>
              <p>这些变量会在运行时由知识库上下文或用户问题填充。</p>
            </div>
            <div class="var-list">
              <NTag v-for="item in selected.variables" :key="item" size="small" round>{{ item }}</NTag>
              <span v-if="!selected.variables?.length" class="muted">暂无变量</span>
            </div>
          </div>

          <div class="editor-shell">
            <div class="editor-toolbar">
              <span>Template</span>
              <span>{{ selected.content?.length || 0 }} 字符</span>
            </div>
            <NInput v-model:value="selected.content" class="prompt-textarea" type="textarea" :autosize="{ minRows: 20, maxRows: 34 }" />
          </div>
        </template>
        <NEmpty v-else class="empty-state" description="请选择提示词" />
      </section>
    </div>
  </CommonPage>
</template>

<style scoped>
.ai-workspace {
  --ai-bg: #f7f7f4;
  --ai-sidebar: #f1f0ea;
  --ai-line: rgba(17, 24, 39, .10);
  --ai-text: #111827;
  --ai-muted: #6b7280;
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  height: calc(100vh - 96px);
  min-height: 560px;
  overflow: hidden;
  border: 1px solid var(--ai-line);
  border-radius: 20px;
  background: var(--ai-bg);
  box-shadow: 0 18px 50px rgba(15, 23, 42, .08);
}
.ai-sidebar {
  min-height: 0;
  border-right: 1px solid var(--ai-line);
  background: var(--ai-sidebar);
  padding: 18px;
  overflow: hidden;
}
.sidebar-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}
.sidebar-tools {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}
.category-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}
.category-tabs button {
  min-height: 30px;
  border: 1px solid var(--ai-line);
  border-radius: 8px;
  color: var(--ai-muted);
  background: rgba(255, 255, 255, .58);
  font-size: 12px;
  cursor: pointer;
}
.category-tabs button.active {
  border-color: rgba(16, 163, 127, .35);
  color: #0f766e;
  background: rgba(16, 163, 127, .12);
  font-weight: 700;
}
.eyebrow {
  color: #10a37f;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}
h1, h2, p { margin: 0; }
.sidebar-head h2, .main-header h1 {
  margin-top: 6px;
  color: var(--ai-text);
  font-weight: 800;
}
.sidebar-head p, .main-header p, .variable-panel p, .muted {
  margin-top: 8px;
  color: var(--ai-muted);
  font-size: 13px;
  line-height: 1.6;
}
.prompt-list {
  display: grid;
  gap: 8px;
  max-height: calc(100vh - 205px);
  overflow: auto;
  padding-right: 4px;
}
.prompt-item {
  display: grid;
  gap: 8px;
  width: 100%;
  padding: 13px;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 14px;
  background: transparent;
  cursor: pointer;
  transition: .18s ease;
}
.prompt-item:hover, .prompt-item.active {
  border-color: rgba(17, 24, 39, .12);
  background: rgba(255, 255, 255, .72);
}
.prompt-item.active {
  box-shadow: 0 10px 24px rgba(15, 23, 42, .08);
}
.prompt-name {
  color: var(--ai-text);
  font-weight: 800;
}
.prompt-desc {
  color: var(--ai-muted);
  font-size: 12px;
  line-height: 1.55;
}
.prompt-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #9ca3af;
}
.status-dot.online { background: #10a37f; box-shadow: 0 0 0 4px rgba(16, 163, 127, .12); }
.status-dot.offline { background: #ef4444; box-shadow: 0 0 0 4px rgba(239, 68, 68, .10); }
.ai-main {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 16px;
  overflow: auto;
  padding: 24px max(26px, calc((100% - 980px) / 2));
  background: linear-gradient(180deg, #fff 0%, #fbfbf8 100%);
}
.main-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--ai-line);
}
.switch-wrap {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--ai-line);
  border-radius: 999px;
  color: var(--ai-muted);
  background: #fff;
  font-size: 13px;
}
.variable-panel, .editor-shell {
  border: 1px solid var(--ai-line);
  border-radius: 18px;
  background: rgba(255, 255, 255, .86);
  box-shadow: 0 12px 34px rgba(15, 23, 42, .06);
}
.variable-panel {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
}
.var-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  max-width: 56%;
}
.editor-shell {
  min-height: 0;
  overflow: hidden;
}
.editor-toolbar {
  display: flex;
  justify-content: space-between;
  padding: 12px 16px;
  color: var(--ai-muted);
  font-size: 12px;
  border-bottom: 1px solid var(--ai-line);
  background: #fbfbf8;
}
.prompt-textarea :deep(.n-input__textarea-el) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  line-height: 1.75;
}
.prompt-textarea :deep(.n-input-wrapper) {
  border-radius: 0;
}
.empty-state {
  align-self: center;
}
@media (max-width: 980px) {
  .ai-workspace { grid-template-columns: 1fr; height: auto; min-height: calc(100vh - 96px); }
  .ai-sidebar { border-right: 0; border-bottom: 1px solid var(--ai-line); }
  .main-header, .variable-panel { flex-direction: column; }
  .var-list { max-width: none; justify-content: flex-start; }
}
</style>
