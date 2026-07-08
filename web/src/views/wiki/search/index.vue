<script setup>
import { nextTick, onMounted, ref } from 'vue'
import AppPage from '@/components/page/AppPage.vue'
import { NButton, NInput, NTag } from 'naive-ui'
import { getToken } from '@/utils'
import api from '@/api'

defineOptions({ name: '知识检索' })

const input = ref('')
const sending = ref(false)
const loadingConversations = ref(false)
const historyHidden = ref(localStorage.getItem('wiki_history_hidden') === '1')
const conversations = ref([])
const conversationId = ref(null)
const messages = ref([])
const scroller = ref(null)
const stickToBottom = ref(true)
const apiBase = (import.meta.env.VITE_BASE_API || '/api/v1').replace(/\/$/, '')
const quickPrompts = [
  'Monsafe 授权到期怎么处理？',
  '终端无法连接平台如何排查？',
  '部署前需要收集哪些客户环境信息？',
  '把常见问题整理成处理步骤',
]

onMounted(loadConversations)

function setHistoryHidden(value) {
  historyHidden.value = value
  localStorage.setItem('wiki_history_hidden', value ? '1' : '0')
}

async function loadConversations() {
  loadingConversations.value = true
  try {
    const res = await api.wikiConversations({ page: 1, page_size: 50 })
    conversations.value = res?.data || []
  } finally {
    loadingConversations.value = false
  }
}

async function openConversation(item) {
  if (!item?.id || sending.value) return
  const res = await api.wikiConversationGet({ conversation_id: item.id })
  conversationId.value = res?.data?.id || item.id
  let lastQuestion = ''
  messages.value = (res?.data?.messages || []).map((message) => {
    if (message.role === 'user') lastQuestion = message.content
    return {
      id: message.id,
      role: message.role,
      question: message.role === 'assistant' ? lastQuestion : message.content,
      content: message.content,
      pending: false,
      streaming: false,
      citations: message.citations || [],
      archivePath: message.archive_path || '',
      citationsCollapsed: true,
      statusLabel: '',
    }
  })
  await scrollToBottom(true)
}

function newConversation() {
  if (sending.value) return
  conversationId.value = null
  messages.value = []
  input.value = ''
}

function conversationTime(item) {
  const value = String(item?.updated_at || item?.created_at || '')
  return value.length >= 16 ? value.slice(11, 16) : ''
}

async function sendSuggestion(text) {
  input.value = text
  await send()
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return
  input.value = ''
  const assistantId = `assistant-${Date.now()}`
  messages.value.push(
    { id: `user-${Date.now()}`, role: 'user', content: text },
    {
      id: assistantId,
      role: 'assistant',
      question: text,
      content: '',
      pending: true,
      streaming: true,
      citations: [],
      archivePath: '',
      citationsCollapsed: true,
      statusLabel: '准备提问',
    }
  )
  await scrollToBottom(true)
  sending.value = true
  let rawAnswer = ''
  const patchAssistant = (patch) => {
    messages.value = messages.value.map((item) => (item.id === assistantId ? { ...item, ...patch } : item))
  }
  try {
    const resp = await fetch(`${apiBase}/wiki/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', token: getToken() || '' },
      body: JSON.stringify({ question: text, conversation_id: conversationId.value }),
    })
    if (!resp.ok || !resp.body) throw new Error(`Wiki 请求失败：${resp.status}`)
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const line = part.split('\n').find((item) => item.startsWith('data:'))
        if (!line) continue
        const item = JSON.parse(line.replace(/^data:\s*/, ''))
        if (item.type === 'status') {
          patchAssistant({ statusLabel: item.payload?.label || '' })
        } else if (item.type === 'assistant.delta') {
          rawAnswer += item.payload?.content || ''
          patchAssistant({ content: rawAnswer, pending: true, streaming: true })
          await scrollToBottom()
        } else if (item.type === 'final') {
          const data = item.payload || {}
          rawAnswer = data.content || rawAnswer || '没有得到有效回答。'
          conversationId.value = data.conversation_id || conversationId.value
          patchAssistant({
            id: data.message_id || assistantId,
            content: rawAnswer,
            pending: false,
            streaming: false,
            citations: data.citations || [],
            archivePath: data.archive_path || '',
            statusLabel: '',
          })
          await loadConversations()
        } else if (item.type === 'error') {
          patchAssistant({ content: item.payload?.message || 'Wiki 问答失败', pending: false, streaming: false })
        }
      }
    }
  } catch (error) {
    patchAssistant({ content: error?.message || 'Wiki 问答失败，请检查大模型配置。', pending: false, streaming: false })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

async function markUnhelpful(msg) {
  if (!msg?.question || !msg?.content) return
  await api.wikiMarkUnhelpful({
    question: msg.question,
    answer: msg.content,
    evidence_page_ids: msg.citations.map((item) => item.id).filter(Boolean),
  })
  window.$message?.success('已记录反馈')
}

async function copyMessage(msg) {
  await navigator.clipboard.writeText(msg.content || '')
  window.$message?.success('已复制')
}

function isNearBottom() {
  const el = scroller.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 96
}

async function scrollToBottom(force = false) {
  await nextTick()
  if (!scroller.value) return
  if (force || stickToBottom.value || isNearBottom()) scroller.value.scrollTop = scroller.value.scrollHeight
}

function handleMessageScroll() {
  stickToBottom.value = isNearBottom()
}

function handleInputKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  send()
}
</script>

<template>
  <AppPage :show-footer="false" class="chat-app-page">
    <div class="chat-page-shell">
      <div class="wiki-chat-shell" :class="{ historyHidden }">
        <aside v-if="!historyHidden" class="conversation-sidebar">
          <div class="sidebar-header">
            <div>
              <div class="sidebar-title">对话记录</div>
              <div class="sidebar-subtitle">仅显示当前用户</div>
            </div>
            <div class="sidebar-actions">
              <NButton size="small" secondary @click="setHistoryHidden(true)">隐藏</NButton>
              <NButton size="small" type="primary" secondary @click="newConversation">新建</NButton>
            </div>
          </div>
          <div class="conversation-list" :class="{ loading: loadingConversations }">
            <button
              v-for="item in conversations"
              :key="item.id"
              class="conversation-item"
              :class="{ active: item.id === conversationId }"
              type="button"
              @click="openConversation(item)"
            >
              <span class="conversation-title">{{ item.title }}</span>
              <span class="conversation-preview">{{ item.last_message_preview || '暂无消息' }}</span>
              <span class="conversation-time">{{ conversationTime(item) }}</span>
            </button>
            <div v-if="!conversations.length" class="empty-history">暂无历史对话</div>
          </div>
        </aside>

        <section class="chat-main">
        <button v-if="historyHidden" class="history-toggle" type="button" @click="setHistoryHidden(false)">记录</button>
        <div ref="scroller" class="message-scroll" :class="{ empty: !messages.length }" @scroll="handleMessageScroll">
          <section v-if="!messages.length" class="welcome-panel">
            <div class="welcome-mark">WIKI</div>
            <h2>今天想了解什么？</h2>
            <p>我会基于企业 Wiki 生成回答，流式输出。</p>
            <div class="prompt-grid">
              <button v-for="item in quickPrompts" :key="item" class="prompt-card" type="button" @click="sendSuggestion(item)">
                {{ item }}
              </button>
            </div>
          </section>

          <div v-for="msg in messages" :key="msg.id" class="message-row" :class="msg.role">
            <div v-if="msg.role === 'assistant'" class="message-avatar">AI</div>
            <article class="message-bubble">
              <template v-if="msg.role === 'assistant'">
                <div v-if="msg.pending && !msg.content" class="thinking-state">
                  <span class="thinking-dot" />
                  <span class="thinking-dot" />
                  <span class="thinking-dot" />
                  <span class="thinking-label">正在生成回答</span>
                </div>
                <div v-else-if="msg.streaming" class="message-content streaming-content">{{ msg.content }}<span class="typing-cursor" /></div>
                <div v-else class="message-content assistant-content">{{ msg.content }}</div>
                <div v-if="msg.pending && msg.statusLabel" class="query-status">
                  {{ msg.statusLabel }}
                </div>
                <div v-if="msg.pending && msg.content" class="streaming-hint">生成中...</div>
              </template>
              <div v-else class="message-content user-content">{{ msg.content }}</div>

              <div v-if="msg.archivePath || msg.citations?.length" class="citations">
                <button class="citations-toggle" type="button" @click="msg.citationsCollapsed = !msg.citationsCollapsed">
                  <span>引用</span>
                  <span>{{ msg.citationsCollapsed ? '展开' : '收起' }}</span>
                </button>
                <div v-if="!msg.citationsCollapsed" class="citation-list">
                  <NTag v-if="msg.archivePath" size="small" type="success" class="archive-path">{{ msg.archivePath }}</NTag>
                  <NTag v-for="cite in msg.citations" :key="cite.id || cite.path" size="small">{{ cite.title || cite.path }}</NTag>
                </div>
              </div>

              <div v-if="msg.role === 'assistant' && !msg.pending && !msg.streaming" class="message-actions">
                <NButton size="small" secondary round @click="copyMessage(msg)">复制</NButton>
                <NButton size="small" secondary round type="warning" @click="markUnhelpful(msg)">无用</NButton>
              </div>
            </article>
          </div>
        </div>

        <footer class="composer-shell">
          <div class="chat-composer">
            <NInput
              v-model:value="input"
              class="chat-input"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 5 }"
              placeholder="向企业 Wiki 提问"
              @keydown="handleInputKeydown"
            />
            <NButton class="send-button" type="primary" circle :loading="sending" :disabled="!input.trim()" @click="send">↑</NButton>
          </div>
          <div class="composer-hint">Enter 发送，Shift + Enter 换行。回答来自 Wiki 编译结果，请结合引用核验。</div>
        </footer>
      </section>
      </div>
    </div>
  </AppPage>
</template>

<style scoped>
.chat-page-shell { flex: 1; min-height: 0; height: 100%; display: flex; overflow: hidden; background: #eef2f7; padding: 10px; }
.chat-app-page { box-sizing: border-box; min-height: 0; overflow: hidden; }
.wiki-chat-shell { flex: 1; min-width: 0; min-height: 0; display: grid; grid-template-columns: 286px minmax(0, 1fr); gap: 10px; }
.wiki-chat-shell.historyHidden { grid-template-columns: minmax(0, 1fr); }
.conversation-sidebar { min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); border: 1px solid rgba(15,23,42,.08); border-radius: 14px; background: #f8fafc; box-shadow: 0 16px 36px rgba(15,23,42,.07); overflow: hidden; }
.sidebar-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 14px; border-bottom: 1px solid rgba(15,23,42,.08); background: #fff; }
.sidebar-actions { display: flex; gap: 6px; }
.sidebar-title { font-size: 15px; font-weight: 900; color: #0f172a; }
.sidebar-subtitle { margin-top: 2px; font-size: 12px; color: #64748b; }
.conversation-list { min-height: 0; overflow: auto; padding: 10px; }
.conversation-item { position: relative; width: 100%; display: grid; gap: 4px; padding: 11px 12px; margin-bottom: 8px; text-align: left; border: 1px solid transparent; border-radius: 10px; background: transparent; color: #0f172a; cursor: pointer; transition: background .16s ease, border-color .16s ease, transform .16s ease; }
.conversation-item:hover { background: #fff; transform: translateY(-1px); }
.conversation-item.active { background: #fff; border-color: rgba(37,99,235,.28); box-shadow: 0 10px 24px rgba(37,99,235,.08); }
.conversation-item.active::before { content: ""; position: absolute; left: 0; top: 12px; bottom: 12px; width: 3px; border-radius: 999px; background: #2563eb; }
.conversation-title { font-weight: 800; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-preview { color: #64748b; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-time { color: #94a3b8; font-size: 11px; }
.empty-history { padding: 18px 8px; color: #94a3b8; text-align: center; font-size: 13px; }
.chat-main { position: relative; min-width: 0; min-height: 0; height: 100%; overflow: hidden; display: grid; grid-template-rows: minmax(0, 1fr) auto; border: 1px solid rgba(17,24,39,.10); border-radius: 14px; background: #fff; box-shadow: 0 18px 50px rgba(15,23,42,.08); }
.history-toggle { position: absolute; top: 14px; left: 16px; z-index: 2; height: 30px; padding: 0 10px; border: 1px solid rgba(15,23,42,.12); border-radius: 8px; color: #334155; background: rgba(255,255,255,.86); cursor: pointer; font-size: 12px; font-weight: 800; box-shadow: 0 8px 20px rgba(15,23,42,.08); }
.history-toggle:hover { color: #1d4ed8; border-color: rgba(37,99,235,.28); }
.message-scroll { min-height: 0; overflow-y: auto; overflow-x: hidden; padding: 28px max(32px, calc((100% - 880px) / 2)) 34px; background: radial-gradient(circle at 18% 0%, rgba(37,99,235,.06), transparent 28%), linear-gradient(180deg, #fff 0%, #fbfbf8 100%); }
.message-scroll.empty { display: grid; place-items: center; }
.welcome-panel { width: min(760px, 100%); margin: auto; text-align: center; transform: translateY(-4vh); }
.welcome-mark { width: 58px; height: 58px; margin: 0 auto 18px; display: grid; place-items: center; border-radius: 14px; color: #fff; font-size: 13px; font-weight: 900; background: linear-gradient(135deg, #0f172a, #2563eb); box-shadow: 0 18px 44px rgba(15,23,42,.16); }
.welcome-panel h2 { margin: 0; color: #111827; font-size: 30px; letter-spacing: 0; }
.welcome-panel p { margin: 12px auto 24px; max-width: 560px; color: #6b7280; font-size: 14px; line-height: 1.7; }
.prompt-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.prompt-card { min-height: 58px; padding: 13px 15px; border-radius: 10px; border: 1px solid rgba(17,24,39,.10); background: #fff; color: #374151; text-align: left; cursor: pointer; line-height: 1.45; box-shadow: 0 12px 28px rgba(15,23,42,.05); transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease; }
.prompt-card:hover { transform: translateY(-2px); border-color: rgba(37,99,235,.26); box-shadow: 0 18px 36px rgba(15,23,42,.08); }
.message-row { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 13px; margin-bottom: 24px; }
.message-row.user { grid-template-columns: minmax(0, 1fr); }
.message-row.user .message-bubble { grid-column: 1; justify-self: end; max-width: min(620px, 82%); background: #eff6ff; border: 1px solid rgba(37,99,235,.16); border-radius: 10px; padding: 12px 16px; }
.message-avatar { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 999px; background: #0f172a; color: #fff; font-size: 12px; font-weight: 900; box-shadow: 0 8px 18px rgba(15,23,42,.16); }
.message-bubble { min-width: 0; color: #111827; line-height: 1.72; word-break: break-word; }
.user-content, .streaming-content { white-space: pre-wrap; overflow-wrap: anywhere; }
.assistant-content { white-space: pre-wrap; overflow-wrap: anywhere; }
.typing-cursor { display: inline-block; width: 7px; height: 1.1em; margin-left: 2px; vertical-align: -2px; background: #111827; animation: cursor-blink .9s steps(2, start) infinite; }
.thinking-state { display: inline-flex; align-items: center; gap: 8px; color: #6b7280; }
.thinking-dot { width: 8px; height: 8px; border-radius: 999px; background: #111827; animation: pulse 1.2s infinite ease-in-out; }
.thinking-dot:nth-child(2) { animation-delay: .15s; }
.thinking-dot:nth-child(3) { animation-delay: .3s; }
.thinking-label { margin-left: 4px; font-size: 13px; }
.streaming-hint { margin-top: 8px; font-size: 12px; color: #6b7280; }
.query-status { display: inline-flex; margin-top: 10px; padding: 4px 8px; border-radius: 999px; color: #1d4ed8; background: #eff6ff; font-size: 12px; }
.citations { margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(17,24,39,.08); color: #6b7280; font-size: 12px; }
.citations-toggle { width: 100%; display: flex; justify-content: space-between; align-items: center; border: 1px solid rgba(37,99,235,.14); border-radius: 8px; padding: 8px 11px; cursor: pointer; color: #1f2937; background: #f8fafc; font-weight: 800; }
.citation-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.archive-path { max-width: min(520px, 58vw); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.message-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 13px; }
.composer-shell { min-height: 0; padding: 12px max(28px, calc((100% - 860px) / 2)) 16px; border-top: 1px solid rgba(17,24,39,.10); background: linear-gradient(180deg, rgba(255,255,255,.86), #fff); }
.chat-composer { display: grid; grid-template-columns: minmax(0, 1fr) 38px; gap: 8px; align-items: end; padding: 9px 10px 9px 16px; border: 1px solid rgba(17,24,39,.13); border-radius: 24px; background: #fff; box-shadow: 0 14px 42px rgba(15,23,42,.10); }
.chat-composer :deep(.n-input) { --n-border: none !important; --n-border-hover: none !important; --n-border-focus: none !important; --n-box-shadow-focus: none !important; --n-color: transparent !important; }
.chat-composer :deep(.n-input-wrapper) { min-height: 34px; padding: 0; background: transparent; }
.chat-composer :deep(textarea) { line-height: 1.55; padding-top: 5px; }
.send-button { width: 38px; height: 38px; min-height: 38px; font-size: 18px; font-weight: 900; }
.composer-hint { margin-top: 8px; text-align: center; color: #9ca3af; font-size: 12px; }
@keyframes pulse { 0%, 80%, 100% { opacity: .35; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-2px); } }
@keyframes cursor-blink { 0%, 45% { opacity: 1; } 46%, 100% { opacity: 0; } }
@media (max-width: 900px) {
  .chat-page-shell { padding: 0; }
  .wiki-chat-shell { grid-template-columns: 1fr; }
  .conversation-sidebar { display: none; }
  .message-scroll { padding: 20px 14px 28px; }
  .composer-shell { padding: 10px 14px 14px; }
  .prompt-grid { grid-template-columns: 1fr; }
  .message-row { grid-template-columns: 30px minmax(0, 1fr); gap: 10px; }
  .message-row.user { grid-template-columns: minmax(0, 1fr); }
  .message-row.user .message-bubble { grid-column: 1; max-width: 100%; justify-self: stretch; }
  .message-avatar { width: 30px; height: 30px; }
}
</style>
