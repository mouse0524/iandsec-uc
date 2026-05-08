<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
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
  const localAssistant = { id: `local-assistant-${Date.now()}`, role: 'assistant', content: '', pending: true }
  messages.value.push(localUser, localAssistant)
  await scrollToBottom()
  sending.value = true
  try {
    const resp = await fetch(`${import.meta.env.VITE_BASE_API}/skill-know/chat/agent/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', token: getToken() || '' },
      body: JSON.stringify({ message: text, conversation_id: conversationId.value }),
    })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let paintCounter = 0
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
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
          localAssistant.content += sanitizeAssistantContent(item.payload?.content || '')
          paintCounter += 1
          if (paintCounter % 12 === 0) {
            await nextTick()
            await new Promise((resolve) => requestAnimationFrame(resolve))
          }
        }
        else if (item.type === 'final') {
          const data = item.payload || {}
          progressSteps.value = [
            { key: 'retrieve', label: '检索知识库', status: 'done' },
            { key: 'reason', label: '整理上下文', status: 'done' },
            { key: 'answer', label: '生成回答', status: 'done' },
          ]
          conversationId.value = data.conversation_id || conversationId.value
          Object.assign(localAssistant, {
            id: data.message_id || localAssistant.id,
            content: sanitizeAssistantContent(data.content || localAssistant.content || '未返回内容'),
            pending: false,
            extra_metadata: { citations: data.citations || [] },
          })
        }
        else if (item.type === 'error') {
          localAssistant.content = item.payload?.message || '对话失败，请稍后重试'
          localAssistant.pending = false
          progressSteps.value = []
        }
      }
    }

    await loadConversations()
    const current = conversations.value.find((item) => item.id === conversationId.value)
    if (current) currentConversation.value = current
  } catch (error) {
    localAssistant.content = error.message || '对话失败，请稍后重试'
    localAssistant.pending = false
    progressSteps.value = []
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

function sanitizeAssistantContent(content) {
  return String(content || '').replace(/<system-reminder>[\s\S]*?<\/system-reminder>/gi, '').trim()
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
  input.value = `${sanitizeAssistantContent(msg.content || '')}\n\n请继续说明：`
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
      <aside class="conversation-sidebar" :class="{ collapsed: sidebarCollapsed }">
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

        <NSpin :show="loading">
          <div ref="scroller" class="message-scroll">
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
                  <b>引用来源</b>
                  <p v-for="cite in msg.extra_metadata.citations" :key="cite.chunk_uri || cite.chunk_id">
                    {{ cite.title }} · {{ cite.heading || '无章节' }} · {{ cite.filename || '-' }}
                  </p>
                </div>
                <NSpace v-if="msg.role === 'assistant' && !msg.pending" class="message-actions" size="small">
                  <NButton size="tiny" quaternary @click="copyMessage(msg)">复制</NButton>
                  <NButton size="tiny" quaternary @click="continueAsk(msg)">继续追问</NButton>
                  <NButton size="tiny" quaternary @click="retryFromMessage(msg)">重新回答</NButton>
                </NSpace>
                <NSpace v-if="msg.role === 'assistant' && !msg.pending && !msg.rated" class="rating-row">
                  <NButton size="tiny" secondary type="success" @click="rateMessage(msg, 5, true)">有帮助</NButton>
                  <NButton size="tiny" secondary type="error" @click="rateMessage(msg, 1, false)">无帮助</NButton>
                </NSpace>
                <NTag v-if="msg.rated" size="small" type="success" class="rated-tag">已评分</NTag>
              </div>
            </div>
          </div>
        </NSpin>

        <div class="input-bar">
          <NInput
            v-model:value="input"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 5 }"
            placeholder="继续追问或输入新的产品技术支持/数据安全问题，Enter 发送，Shift+Enter 换行"
            @keydown="handleInputKeydown"
          />
          <NButton type="primary" size="large" :loading="sending" :disabled="!input.trim()" @click="send">发送</NButton>
        </div>
      </section>
    </div>
  </CommonPage>
</template>

<style scoped>
.chat-page { display: grid; grid-template-columns: 92px 1fr; gap: 16px; height: calc(100vh - 38px); transition: grid-template-columns .22s ease; }
.chat-page.expanded { grid-template-columns: 300px 1fr; }
.conversation-sidebar, .chat-main { border-radius: 24px; background: linear-gradient(180deg, rgba(255,255,255,.86), rgba(248,250,252,.92)); border: 1px solid rgba(148,163,184,.18); box-shadow: 0 16px 50px rgba(15,23,42,.08); backdrop-filter: blur(12px); }
.conversation-sidebar { padding: 14px; overflow: hidden; display: flex; flex-direction: column; }
.conversation-sidebar.collapsed .conversation-list { display: none; }
.conversation-sidebar.collapsed { padding-bottom: 14px; }
.conversation-sidebar:not(.collapsed) { min-width: 300px; }
.conversation-list { margin-top: 12px; overflow: auto; }
.conversation-item { position: relative; padding: 14px; border-radius: 16px; cursor: pointer; border: 1px solid transparent; margin-bottom: 10px; background: rgba(148,163,184,.08); }
.conversation-item:hover, .conversation-item.active { background: rgba(32,128,240,.10); border-color: rgba(32,128,240,.24); }
.conversation-title { font-weight: 700; padding-right: 44px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-preview { color: #64748b; font-size: 12px; margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-time { color: #7b8494; font-size: 12px; margin-top: 6px; }
.conversation-item .n-button { position: absolute; right: 8px; top: 8px; }
.chat-main { min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
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
.message-scroll { height: calc(100vh - 220px); overflow: auto; padding: 22px 24px; background: radial-gradient(circle at top, rgba(219,234,254,.35), transparent 30%), linear-gradient(180deg, rgba(248,250,252,.65), rgba(241,245,249,.40)); }
.message-row { display: flex; margin-bottom: 16px; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: stretch; }
.message-bubble { max-width: min(820px, 78%); padding: 16px 18px; border-radius: 20px; line-height: 1.8; white-space: pre-wrap; word-break: break-word; box-shadow: 0 8px 24px rgba(15,23,42,.06); }
.message-row.user .message-bubble { background: linear-gradient(180deg, #2563eb, #1d4ed8); color: white; border-top-right-radius: 8px; }
.message-row.assistant .message-bubble { width: 100%; max-width: none; background: rgba(255,255,255,.96); color: #172033; border: 1px solid rgba(148,163,184,.18); border-top-left-radius: 8px; }
.message-role { font-size: 12px; opacity: .72; margin-bottom: 6px; }
.markdown-body :deep(p) { margin: 8px 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; margin: 8px 0; }
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
.citations p { margin: 4px 0; }
.message-actions { margin-top: 10px; }
.rating-row, .rated-tag { margin-top: 10px; }
.input-bar { display: grid; grid-template-columns: 1fr 120px; gap: 12px; padding: 16px; border-top: 1px solid rgba(148,163,184,.18); background: rgba(255,255,255,.92); align-items: stretch; }
.input-bar :deep(.n-input) { height: 100%; }
.input-bar :deep(.n-input-wrapper) { min-height: 52px; border-radius: 16px; align-items: flex-start; padding-top: 10px; padding-bottom: 10px; }
.input-bar :deep(textarea) { line-height: 1.7; }
.input-bar :deep(.n-button) { height: 52px; border-radius: 16px; font-weight: 700; }
@keyframes pulse {
  0%, 80%, 100% { opacity: .35; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-2px); }
}
@media (max-width: 900px) {
  .chat-page { grid-template-columns: 1fr; height: auto; }
  .conversation-sidebar { max-height: 260px; }
  .message-scroll { height: 72vh; }
  .message-bubble { max-width: 92%; }
}
</style>
