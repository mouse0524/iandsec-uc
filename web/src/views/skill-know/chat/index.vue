<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'
import { getToken } from '@/utils'

defineOptions({ name: '智能对话' })

const input = ref('')
const loading = ref(false)
const sending = ref(false)
const conversations = ref([])
const messages = ref([])
const conversationId = ref(null)
const currentConversation = ref(null)
const scroller = ref(null)
const progressSteps = ref([])
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const streamDebugEnabled = ref(false)
const streamDebug = ref({ deltaCount: 0, firstTokenAt: '' })
const sidebarCollapsed = ref(true)
const router = useRouter()

onMounted(async () => {
  await loadConversations()
  if (conversations.value.length) await openConversation(conversations.value[0])
})

async function loadConversations() {
  const res = await api.skillKnowConversations({ page: 1, page_size: 50 })
  conversations.value = res.data || []
}

async function openConversation(item) {
  if (!item?.id) return
  loading.value = true
  try {
    const res = await api.skillKnowGetConversation({ conversation_id: item.id })
    currentConversation.value = res.data
    conversationId.value = res.data.id
    messages.value = (res.data.messages || []).filter((msg) => ['user', 'assistant'].includes(msg.role))
    await scrollToBottom()
  } finally {
    loading.value = false
  }
}

function newConversation() {
  conversationId.value = null
  currentConversation.value = null
  messages.value = []
  input.value = ''
  progressSteps.value = []
  streamDebug.value = { deltaCount: 0, firstTokenAt: '' }
}

async function send() {
  const text = input.value.trim()
  return await sendMessage(text)
}

async function sendMessage(text) {
  if (!text || sending.value) return
  input.value = ''
  streamDebug.value = { deltaCount: 0, firstTokenAt: '' }
  progressSteps.value = [
    { key: 'retrieve', label: '检索知识库', status: 'active' },
    { key: 'reason', label: '整理上下文', status: 'pending' },
    { key: 'answer', label: '生成回答', status: 'pending' },
  ]
  const localUser = { id: `local-user-${Date.now()}`, role: 'user', content: text }
  const localAssistant = { id: `local-assistant-${Date.now()}`, role: 'assistant', content: '', pending: true, citationsCollapsed: true }
  messages.value.push(localUser, localAssistant)
  await scrollToBottom()
  sending.value = true
  let rawAnswer = ''
  let revealedLength = 0
  let revealTimer = null
  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms))
  const startRevealTimer = () => {
    if (revealTimer) return
    revealTimer = window.setInterval(async () => {
      if (revealedLength >= rawAnswer.length) return
      revealedLength = Math.min(rawAnswer.length, revealedLength + 3)
      localAssistant.content = compactAssistantContent(rawAnswer.slice(0, revealedLength), { trimEnd: false })
      await scrollToBottom()
    }, 24)
  }
  const waitForReveal = async () => {
    while (revealedLength < rawAnswer.length) await sleep(24)
    localAssistant.content = compactAssistantContent(rawAnswer)
    if (revealTimer) {
      window.clearInterval(revealTimer)
      revealTimer = null
    }
  }
  startRevealTimer()
  try {
    const resp = await fetch(`${import.meta.env.VITE_BASE_API}/skill-know/chat/agent/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', token: getToken() || '' },
      body: JSON.stringify({ message: text, conversation_id: conversationId.value }),
    })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (let index = 0; index < parts.length; index += 1) {
        const part = parts[index]
        const line = part.split('\n').find((i) => i.startsWith('data:'))
        if (!line) continue
        const item = JSON.parse(line.replace(/^data:\s*/, ''))

        if (item.type === 'phase.changed') {
          progressSteps.value = [
            { key: 'retrieve', label: '检索知识库', status: 'active' },
            { key: 'reason', label: '整理上下文', status: 'pending' },
            { key: 'answer', label: '生成回答', status: 'pending' },
          ]
        }
        else if (item.type === 'search.results') {
          progressSteps.value = [
            { key: 'retrieve', label: '检索知识库', status: 'done' },
            { key: 'reason', label: '整理上下文', status: 'active' },
            { key: 'answer', label: '生成回答', status: 'pending' },
          ]
        }
        else if (item.type === 'llm.call.started') {
          progressSteps.value = [
            { key: 'retrieve', label: '检索知识库', status: 'done' },
            { key: 'reason', label: '整理上下文', status: 'done' },
            { key: 'answer', label: '生成回答', status: 'active' },
          ]
        }
        else if (item.type === 'assistant.delta') {
          streamDebug.value.deltaCount += 1
          if (!streamDebug.value.firstTokenAt) streamDebug.value.firstTokenAt = new Date().toLocaleTimeString()
          rawAnswer += item.payload?.content || ''
        }
        else if (item.type === 'final') {
          const data = item.payload || {}
          progressSteps.value = [
            { key: 'retrieve', label: '检索知识库', status: 'done' },
            { key: 'reason', label: '整理上下文', status: 'done' },
            { key: 'answer', label: '生成回答', status: 'done' },
          ]
          conversationId.value = data.conversation_id || conversationId.value
          rawAnswer = data.content || rawAnswer || '未返回内容'
          await waitForReveal()
          Object.assign(localAssistant, {
            id: data.message_id || localAssistant.id,
            content: compactAssistantContent(rawAnswer),
            pending: false,
            extra_metadata: { citations: data.citations || [] },
            citationsCollapsed: true,
          })
        }
        else if (item.type === 'error') {
          rawAnswer = item.payload?.message || '对话失败，请稍后重试'
          await waitForReveal()
          localAssistant.content = item.payload?.message || '对话失败，请稍后重试'
          localAssistant.pending = false
          progressSteps.value = []
        }
        if (index % 20 === 0) await sleep(0)
      }
    }

    await loadConversations()
    const current = conversations.value.find((item) => item.id === conversationId.value)
    if (current) currentConversation.value = current
  } catch (error) {
    if (revealTimer) window.clearInterval(revealTimer)
    localAssistant.content = error.message || '对话失败，请稍后重试'
    localAssistant.pending = false
    progressSteps.value = []
  } finally {
    if (revealTimer) window.clearInterval(revealTimer)
    sending.value = false
    await scrollToBottom()
  }
}

function sanitizeAssistantContent(content) {
  return compactAssistantContent(content)
}

function compactAssistantContent(content, options = {}) {
  const result = String(content || '')
    .replace(/<system-reminder>[\s\S]*?<\/system-reminder>/gi, '')
    .replace(/[ \t]+$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
  return options.trimEnd === false ? result.replace(/^\s+/, '') : result.trim()
}

async function rateMessage(msg, rating, isHelpful) {
  if (!msg.id || String(msg.id).startsWith('local-')) return
  await api.skillKnowFeedbackMessage({ message_id: msg.id, rating, is_helpful: isHelpful })
  msg.rated = true
  $message.success('评分已提交')
}

async function copyMessage(msg) {
  await navigator.clipboard.writeText(sanitizeAssistantContent(msg.content || ''))
  $message.success('已复制')
}

function continueAsk(msg) {
  input.value = '请基于上面的回答继续说明：'
  nextTick(() => document.querySelector('.input-bar textarea')?.focus())
}

function citationLabel(cite, index) {
  return `来源 ${index + 1}：${cite.title || cite.filename || '未命名文档'}${cite.heading ? ` · ${cite.heading}` : ''}`
}

function openCitation(cite) {
  if (!cite?.document_id) return $message.warning('该引用缺少文档 ID，无法跳转')
  router.push({ path: '/skill-know/documents', query: { document_id: cite.document_id, chunk_id: cite.chunk_id || '' } })
}

async function retryFromMessage(msg) {
  const userMessageId = msg.extra_metadata?.user_message_id
  const userMessage = messages.value.find((item) => item.id === userMessageId)
  if (!userMessage?.content) return $message.warning('未找到对应问题，无法重新回答')
  await sendMessage(userMessage.content)
}

async function deleteConversation(item) {
  if (!item?.id) return
  window.$dialog.warning({
    title: '删除会话',
    content: `确定删除「${item.title || `会话 ${item.id}`}」吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      await api.skillKnowDeleteConversation({ conversation_id: item.id })
      if (conversationId.value === item.id) newConversation()
      await loadConversations()
    },
  })
}

async function scrollToBottom() {
  await nextTick()
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}

function conversationTitle(item) {
  return item?.title || `会话 ${item?.id || ''}`
}

function renderMessage(content) {
  return md.render(sanitizeAssistantContent(content || ''))
}

function handleInputKeydown(event) {
  if (event.key !== 'Enter') return
  if (event.shiftKey) return
  event.preventDefault()
  send()
}
</script>

<template>
  <CommonPage title="智能对话" :show-header="false" show-footer>
    <div class="sk-theme-page chat-page" :class="{ expanded: !sidebarCollapsed }">
      <aside v-if="!sidebarCollapsed" class="conversation-sidebar">
        <NButton type="primary" block @click="newConversation">开启新会话</NButton>
        <div class="conversation-list">
          <div
            v-for="item in conversations"
            :key="item.id"
            class="conversation-item"
            :class="{ active: item.id === conversationId }"
            @click="openConversation(item)"
          >
            <div class="conversation-title">{{ conversationTitle(item) }}</div>
            <div v-if="item.last_message_preview" class="conversation-preview">{{ item.last_message_preview }}</div>
            <div class="conversation-time">{{ item.updated_at || item.created_at }}</div>
            <NButton size="tiny" quaternary type="error" @click.stop="deleteConversation(item)">删除</NButton>
          </div>
          <NEmpty v-if="!conversations.length" description="暂无历史会话" />
        </div>
      </aside>

      <section class="chat-main">
        <div class="chat-header">
          <div class="header-bar header-bar-compact">
            <NButton secondary size="small" @click="sidebarCollapsed = !sidebarCollapsed">{{ sidebarCollapsed ? '展开会话' : '收起会话' }}</NButton>
          </div>
        </div>

        <div v-if="progressSteps.length" class="progress-strip">
          <div class="progress-tools">
            <NSwitch v-model:value="streamDebugEnabled" size="small" />
            <span class="debug-switch-label">调试模式</span>
          </div>
          <div v-for="step in progressSteps" :key="step.key" class="progress-step" :class="step.status">
            <span class="step-dot" />
            <span>{{ step.label }}</span>
          </div>
        </div>

        <div v-if="streamDebugEnabled && (sending || streamDebug.deltaCount)" class="stream-debug-bar">
          <NTag size="small" type="info">STREAM MODE</NTag>
          <NTag size="small">delta: {{ streamDebug.deltaCount }}</NTag>
          <NTag v-if="streamDebug.firstTokenAt" size="small">first token: {{ streamDebug.firstTokenAt }}</NTag>
        </div>

        <div ref="scroller" class="message-scroll" :class="{ loading }">
          <NSpin v-if="loading" class="message-loading" size="small" />
          <NEmpty v-if="!messages.length" description="输入问题开始对话，历史会话会自动保存" />
          <div v-for="msg in messages" :key="msg.id" class="message-row" :class="msg.role">
            <div class="message-bubble">
              <div class="message-role">{{ msg.role === 'user' ? '你' : 'AI 助手' }}</div>
              <template v-if="msg.role === 'assistant'">
                <div v-if="msg.pending && !msg.content" class="thinking-state">
                  <span class="thinking-dot" />
                  <span class="thinking-dot" />
                  <span class="thinking-dot" />
                  <span class="thinking-label">正在生成回答</span>
                </div>
                <div v-else class="message-content markdown-body" v-html="renderMessage(msg.content)" />
                <div v-if="msg.pending && msg.content" class="streaming-hint">生成中...</div>
              </template>
              <div v-else class="message-content">{{ msg.content }}</div>
              <div v-if="msg.extra_metadata?.citations?.length" class="citations">
                <button class="citations-toggle" type="button" @click="msg.citationsCollapsed = !msg.citationsCollapsed">
                  <span>引用来源 {{ msg.extra_metadata.citations.length }}</span>
                  <span>{{ msg.citationsCollapsed ? '展开' : '收起' }}</span>
                </button>
                <div v-if="!msg.citationsCollapsed" class="citation-list">
                  <button
                    v-for="(cite, index) in msg.extra_metadata.citations"
                    :key="cite.chunk_uri || cite.chunk_id || index"
                    class="citation-link"
                    type="button"
                    @click="openCitation(cite)"
                  >
                    {{ citationLabel(cite, index) }}
                    <span class="citation-file">{{ cite.filename || '-' }}</span>
                  </button>
                </div>
              </div>
              <div v-if="msg.role === 'assistant' && !msg.pending" class="message-actions">
                <NButton size="small" secondary round @click="copyMessage(msg)">复制</NButton>
                <NButton size="small" secondary round type="primary" @click="continueAsk(msg)">继续追问</NButton>
                <NButton size="small" secondary round @click="retryFromMessage(msg)">重新回答</NButton>
              </div>
              <NSpace v-if="msg.role === 'assistant' && !msg.pending && !msg.rated" class="rating-row">
                <NButton size="tiny" secondary type="success" @click="rateMessage(msg, 5, true)">有帮助</NButton>
                <NButton size="tiny" secondary type="error" @click="rateMessage(msg, 1, false)">无帮助</NButton>
              </NSpace>
              <NTag v-if="msg.rated" size="small" type="success" class="rated-tag">已评分</NTag>
            </div>
          </div>
        </div>

        <div class="input-bar">
          <NInput
            v-model:value="input"
            class="chat-input"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 5 }"
            placeholder="继续追问或输入新的产品技术支持/数据安全问题，Enter 发送，Shift+Enter 换行"
            @keydown="handleInputKeydown"
          />
          <NButton class="send-button" type="primary" size="large" :loading="sending" :disabled="!input.trim()" @click="send">发送</NButton>
        </div>
      </section>
    </div>
  </CommonPage>
</template>

<style scoped>
.chat-page { display: grid; grid-template-columns: 1fr; gap: 16px; height: calc(100vh - 96px); min-height: 560px; transition: grid-template-columns .22s ease; }
.chat-page.expanded { grid-template-columns: 300px 1fr; }
.conversation-sidebar, .chat-main { border-radius: 24px; background: linear-gradient(180deg, rgba(255,255,255,.86), rgba(248,250,252,.92)); border: 1px solid rgba(148,163,184,.18); box-shadow: 0 16px 50px rgba(15,23,42,.08); backdrop-filter: blur(12px); }
.conversation-sidebar { padding: 14px; overflow: hidden; display: flex; flex-direction: column; }
.conversation-sidebar { min-width: 300px; }
.conversation-list { margin-top: 12px; overflow: auto; }
.conversation-item { position: relative; padding: 14px; border-radius: 16px; cursor: pointer; border: 1px solid transparent; margin-bottom: 10px; background: rgba(148,163,184,.08); }
.conversation-item:hover, .conversation-item.active { background: rgba(32,128,240,.10); border-color: rgba(32,128,240,.24); }
.conversation-title { font-weight: 700; padding-right: 44px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-preview { color: #64748b; font-size: 12px; margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-time { color: #7b8494; font-size: 12px; margin-top: 6px; }
.conversation-item .n-button { position: absolute; right: 8px; top: 8px; }
.chat-main { min-width: 0; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.chat-header { padding: 8px 14px; border-bottom: 1px solid rgba(148,163,184,.10); }
.header-bar { width: 100%; }
.header-bar-compact { display: flex; justify-content: flex-end; }
.progress-strip { display: flex; gap: 12px; padding: 10px 18px; border-bottom: 1px solid rgba(148,163,184,.12); background: rgba(255,255,255,.72); }
.stream-debug-bar { display: flex; gap: 8px; padding: 8px 18px; border-bottom: 1px dashed rgba(148,163,184,.18); background: rgba(239,246,255,.68); }
.progress-tools { display: inline-flex; align-items: center; gap: 8px; margin-right: 8px; padding-right: 12px; border-right: 1px solid rgba(148,163,184,.18); }
.debug-switch-label { font-size: 12px; color: #64748b; }
.progress-step { display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: #94a3b8; }
.progress-step .step-dot { width: 8px; height: 8px; border-radius: 999px; background: currentColor; }
.progress-step.active { color: #2563eb; }
.progress-step.done { color: #16a34a; }
.message-scroll { position: relative; flex: 1 1 0; min-height: 0; overflow-y: auto; overflow-x: hidden; padding: 18px 24px 28px; overscroll-behavior: contain; background: radial-gradient(circle at top, rgba(219,234,254,.35), transparent 30%), linear-gradient(180deg, rgba(248,250,252,.65), rgba(241,245,249,.40)); }
.message-loading { position: sticky; top: 8px; left: 50%; z-index: 2; display: flex; justify-content: center; pointer-events: none; }
.message-row { display: flex; margin-bottom: 16px; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: stretch; }
.message-bubble { max-width: min(820px, 78%); padding: 16px 18px; border-radius: 20px; line-height: 1.65; white-space: normal; word-break: break-word; box-shadow: 0 8px 24px rgba(15,23,42,.06); }
.message-row.user .message-bubble { background: linear-gradient(180deg, #2563eb, #1d4ed8); color: white; border-top-right-radius: 8px; }
.message-row.assistant .message-bubble { width: 100%; max-width: none; background: rgba(255,255,255,.96); color: #172033; border: 1px solid rgba(148,163,184,.18); border-top-left-radius: 8px; }
.message-role { font-size: 12px; opacity: .72; margin-bottom: 6px; }
.markdown-body :deep(p) { margin: 4px 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; margin: 4px 0; }
.markdown-body :deep(li) { margin: 2px 0; }
.markdown-body :deep(pre) { padding: 12px; border-radius: 10px; background: rgba(15, 23, 42, .06); overflow: auto; }
.markdown-body :deep(code) { padding: 2px 5px; border-radius: 4px; background: rgba(15, 23, 42, .06); }
.markdown-body :deep(table) { width: 100%; border-collapse: collapse; margin: 10px 0; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid rgba(148,163,184,.25); padding: 8px; text-align: left; }
.thinking-state { display: inline-flex; align-items: center; gap: 8px; color: #64748b; }
.thinking-dot { width: 8px; height: 8px; border-radius: 999px; background: #60a5fa; animation: pulse 1.2s infinite ease-in-out; }
.thinking-dot:nth-child(2) { animation-delay: .15s; }
.thinking-dot:nth-child(3) { animation-delay: .3s; }
.thinking-label { margin-left: 4px; font-size: 13px; }
.streaming-hint { margin-top: 8px; font-size: 12px; color: #64748b; }
.citations { margin-top: 12px; padding-top: 10px; border-top: 1px dashed rgba(148,163,184,.38); color: #64748b; font-size: 12px; }
.citations-toggle { width: 100%; display: flex; justify-content: space-between; align-items: center; border: 0; border-radius: 12px; padding: 8px 10px; cursor: pointer; color: #334155; background: rgba(241,245,249,.9); font-weight: 700; }
.citation-list { display: grid; gap: 8px; margin-top: 8px; }
.citation-link { display: flex; justify-content: space-between; gap: 12px; width: 100%; border: 1px solid rgba(37,99,235,.16); border-radius: 12px; padding: 9px 10px; color: #1d4ed8; background: rgba(239,246,255,.78); cursor: pointer; text-align: left; }
.citation-link:hover { border-color: rgba(37,99,235,.34); background: rgba(219,234,254,.86); }
.citation-file { flex: none; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #64748b; }
.message-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.rating-row, .rated-tag { margin-top: 10px; }
.input-bar { flex: none; display: grid; grid-template-columns: minmax(0, 1fr) 104px; gap: 10px; padding: 12px 14px; border-top: 1px solid rgba(148,163,184,.18); background: rgba(255,255,255,.96); align-items: end; }
.input-bar :deep(.n-input-wrapper) { min-height: 46px; border-radius: 16px; align-items: flex-start; padding-top: 8px; padding-bottom: 8px; }
.input-bar :deep(textarea) { line-height: 1.55; }
.send-button { height: 46px; border-radius: 16px; font-weight: 800; box-shadow: 0 10px 22px rgba(37,99,235,.22); }
@keyframes pulse {
  0%, 80%, 100% { opacity: .35; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-2px); }
}
@media (max-width: 900px) {
  .chat-page { grid-template-columns: 1fr; height: calc(100vh - 84px); min-height: 520px; }
  .conversation-sidebar { max-height: 260px; }
  .input-bar { grid-template-columns: 1fr; }
  .message-bubble { max-width: 92%; }
}
</style>
