<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import AppPage from '@/components/page/AppPage.vue'
import api from '@/api'
import { getToken, sanitizeHtml } from '@/utils'

defineOptions({ name: '智能对话' })

const input = ref('')
const loading = ref(false)
const sending = ref(false)
const conversations = ref([])
const messages = ref([])
const conversationId = ref(null)
const currentConversation = ref(null)
const scroller = ref(null)
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const apiBase = (import.meta.env.VITE_BASE_API || '/api/v1').replace(/\/$/, '')
const sidebarCollapsed = ref(false)
const stickToBottom = ref(true)
const quickPrompts = [
  '如何排查终端无法连接平台的问题？',
  '数据安全网关常见部署注意事项有哪些？',
  '帮我整理一个客户现场故障排查清单',
  '产品授权异常时应该收集哪些信息？',
]
const router = useRouter()
const secureAssetUrls = ref({})
const secureAssetObjectUrls = new Set()
const secureAssetQueue = []
const secureAssetQueued = new Set()
let secureAssetActiveCount = 0
let secureAssetObserver = null
const maxSecureAssetConcurrency = 3

onMounted(async () => {
  await loadConversations()
  if (conversations.value.length) await openConversation(conversations.value[0])
})
onUnmounted(() => {
  revokeSecureAssetUrls()
  secureAssetObserver?.disconnect()
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
    messages.value = normalizeMessages(res.data.messages || [])
    stickToBottom.value = true
    await scrollToBottom(true)
  } finally {
    loading.value = false
  }
}

function newConversation() {
  conversationId.value = null
  currentConversation.value = null
  messages.value = []
  input.value = ''
  stickToBottom.value = true
}

async function send() {
  const text = input.value.trim()
  return await sendMessage(text)
}

async function sendMessage(text) {
  if (!text || sending.value) return
  input.value = ''
  const localUser = { id: `local-user-${Date.now()}`, role: 'user', content: text }
  const localAssistantLocalId = `local-assistant-${Date.now()}`
  const localAssistant = { id: localAssistantLocalId, role: 'assistant', content: '', pending: true, revealing: true, citationsCollapsed: true, streaming: true }
  messages.value.push(localUser, localAssistant)
  stickToBottom.value = true
  await scrollToBottom(true)
  sending.value = true
  let rawAnswer = ''
  const patchAssistant = (patch) => {
    Object.assign(localAssistant, patch)
    messages.value = messages.value.map((msg) => ([localAssistant.id, localAssistantLocalId].includes(msg.id) ? { ...localAssistant } : msg))
  }
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
        if (item.type === 'assistant.delta') {
          rawAnswer += item.payload?.content || ''
          patchAssistant({ content: compactAssistantContent(rawAnswer), pending: true, revealing: false, streaming: true })
          await scrollToBottom()
        } else if (item.type === 'final') {
          const data = item.payload || {}
          conversationId.value = data.conversation_id || conversationId.value
          rawAnswer = data.content || rawAnswer || '未返回内容'
          patchAssistant({
            id: data.message_id || localAssistant.id,
            content: compactAssistantContent(rawAnswer),
            pending: false,
            revealing: false,
            streaming: false,
            extra_metadata: { citations: data.citations || [] },
            citationsCollapsed: true,
          })
        } else if (item.type === 'error') {
          rawAnswer = item.payload?.message || '对话失败，请稍后重试'
          patchAssistant({ content: item.payload?.message || '对话失败，请稍后重试', revealing: false, streaming: false })
        }
      }
    }
    await loadConversations()
    const current = conversations.value.find((item) => item.id === conversationId.value)
    if (current) currentConversation.value = current
  } catch (error) {
    patchAssistant({ content: error.message || '对话失败，请稍后重试', pending: false, revealing: false, streaming: false })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

function normalizeMessages(rows) {
  return rows
    .filter((msg) => ['user', 'assistant'].includes(msg.role))
    .map((msg) => ({ ...msg, citationsCollapsed: true, streaming: false, revealing: false, pending: false }))
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
  nextTick(() => {
    document.querySelector('.composer-shell')?.scrollIntoView({ block: 'end' })
    document.querySelector('.chat-composer textarea')?.focus()
  })
}

async function sendSuggestion(text) {
  await sendMessage(text)
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

function conversationTitle(item) {
  return item?.title || `会话 ${item?.id || ''}`
}

function renderMessage(content) {
  const html = md.render(sanitizeAssistantContent(content || ''))
  const normalized = prepareSecureDocumentAssetUrls(html)
  return sanitizeHtml(normalized)
}

function normalizeDocumentAssetPath(src) {
  const value = String(src || '').trim().replace(/^\/api\/v1/i, '')
  const match = value.match(/^\/skill-know\/documents\/assets\/\d+\/[^?#]+/i)
  return match ? match[0] : ''
}

function prepareSecureDocumentAssetUrls(html) {
  return String(html || '').replace(/(<img\b[^>]*?\bsrc=["'])(\/(?:api\/v1\/)?skill-know\/documents\/assets\/[^"']+)(["'][^>]*>)/gi, (_, prefix, src, suffix) => {
    const assetPath = normalizeDocumentAssetPath(src)
    if (!assetPath) return `${prefix}${src}${suffix}`
    const quote = suffix[0] || '"'
    const rest = suffix.slice(1)
    const lazyAttrs = rest.includes('loading=') ? '' : ' loading="lazy" decoding="async"'
    return `${prefix}${secureAssetUrls.value[assetPath] || ''}${quote} data-secure-asset="${assetPath}"${lazyAttrs}${rest}`
  })
}

function initSecureAssetObserver() {
  if (secureAssetObserver) return secureAssetObserver
  secureAssetObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return
      const path = entry.target?.dataset?.secureAsset
      if (path) queueSecureAsset(path)
      secureAssetObserver.unobserve(entry.target)
    })
  }, { rootMargin: '360px 0px' })
  return secureAssetObserver
}

async function hydrateSecureAssetImages() {
  await nextTick()
  const observer = initSecureAssetObserver()
  document.querySelectorAll('img[data-secure-asset]').forEach((img) => {
    const path = img.dataset.secureAsset
    if (!path || secureAssetUrls.value[path] || secureAssetQueued.has(path)) return
    observer.observe(img)
  })
}

watch(secureAssetUrls, hydrateSecureAssetImages, { flush: 'post' })
watch(messages, hydrateSecureAssetImages, { flush: 'post', deep: true })

function queueSecureAsset(path) {
  if (!path || secureAssetUrls.value[path] || secureAssetQueued.has(path)) return
  secureAssetQueued.add(path)
  secureAssetQueue.push(path)
  drainSecureAssetQueue()
}

function drainSecureAssetQueue() {
  while (secureAssetActiveCount < maxSecureAssetConcurrency && secureAssetQueue.length) {
    const path = secureAssetQueue.shift()
    secureAssetActiveCount += 1
    fetchSecureDocumentAsset(path).finally(() => {
      secureAssetActiveCount -= 1
      drainSecureAssetQueue()
    })
  }
}

async function fetchSecureDocumentAsset(path) {
  try {
    const resp = await fetch(`${apiBase}${path}`, {
      headers: { token: getToken() || '' },
    })
    if (!resp.ok) return
    const blobUrl = URL.createObjectURL(await resp.blob())
    secureAssetObjectUrls.add(blobUrl)
    secureAssetUrls.value = { ...secureAssetUrls.value, [path]: blobUrl }
  } catch {
    // 引用图片预览失败不阻断回答正文展示。
  }
}

function revokeSecureAssetUrls() {
  secureAssetObjectUrls.forEach((url) => URL.revokeObjectURL(url))
  secureAssetObjectUrls.clear()
  secureAssetQueue.length = 0
  secureAssetQueued.clear()
  secureAssetActiveCount = 0
  secureAssetUrls.value = {}
}

function handleInputKeydown(event) {
  if (event.key !== 'Enter') return
  if (event.shiftKey) return
  event.preventDefault()
  send()
}
</script>

<template>
  <AppPage :show-footer="false" class="chat-app-page">
    <div class="chat-page-shell">
      <div class="chatgpt-page" :class="{ collapsed: sidebarCollapsed }">
      <aside class="conversation-sidebar">
        <div class="sidebar-top">
          <button class="sidebar-icon-button" type="button" @click="sidebarCollapsed = !sidebarCollapsed">
            {{ sidebarCollapsed ? '展开' : '收起' }}
          </button>
          <NButton class="new-chat-button" type="primary" secondary @click="newConversation">新建对话</NButton>
        </div>
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
            <div class="conversation-meta">
              <span>{{ item.updated_at || item.created_at }}</span>
              <NButton size="tiny" quaternary type="error" @click.stop="deleteConversation(item)">删除</NButton>
            </div>
          </div>
          <NEmpty v-if="!conversations.length" description="暂无历史会话" />
        </div>
      </aside>

      <section class="chat-main">
        <button v-if="sidebarCollapsed" class="sidebar-toggle-floating" type="button" @click="sidebarCollapsed = false">会话</button>
        <div ref="scroller" class="message-scroll" :class="{ loading, empty: !messages.length }" @scroll="handleMessageScroll">
          <NSpin v-if="loading" class="message-loading" size="small" />
          <section v-if="!messages.length" class="welcome-panel">
            <div class="welcome-mark">AI</div>
            <h2>今天想了解什么？</h2>
            <p>可以咨询产品技术支持、数据安全方案、故障排查和知识库中的文档内容。</p>
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
                <div v-else class="message-content markdown-body" v-html="renderMessage(msg.content)" />
                <div v-if="msg.pending && msg.content" class="streaming-hint">生成中...</div>
              </template>
              <div v-else class="message-content user-content">{{ msg.content }}</div>
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
              <div v-if="msg.role === 'assistant' && !msg.pending && !msg.streaming && !msg.revealing" class="message-actions">
                <NButton size="small" secondary round @click="copyMessage(msg)">复制</NButton>
                <NButton size="small" secondary round type="primary" @click="continueAsk(msg)">继续追问</NButton>
                <NButton size="small" secondary round @click="retryFromMessage(msg)">重新回答</NButton>
              </div>
              <NSpace v-if="msg.role === 'assistant' && !msg.pending && !msg.streaming && !msg.revealing && !msg.rated" class="rating-row">
                <NButton size="tiny" secondary type="success" @click="rateMessage(msg, 5, true)">有帮助</NButton>
                <NButton size="tiny" secondary type="error" @click="rateMessage(msg, 1, false)">无帮助</NButton>
              </NSpace>
              <NTag v-if="msg.rated" size="small" type="success" class="rated-tag">已评分</NTag>
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
              placeholder="给 Skill-Know 发送消息"
              @keydown="handleInputKeydown"
            />
            <NButton class="send-button" type="primary" circle :loading="sending" :disabled="!input.trim()" @click="send">↑</NButton>
          </div>
          <div class="composer-hint">Enter 发送，Shift + Enter 换行。回答可能来自知识库检索结果，请结合引用来源核验。</div>
        </footer>
      </section>
      </div>
    </div>
  </AppPage>
</template>

<style scoped>
.chat-page-shell { flex: 1; min-height: 0; height: 100%; display: flex; overflow: hidden; }
.chat-app-page { box-sizing: border-box; min-height: 0; overflow: hidden; }
.chatgpt-page { --chat-bg: #f7f7f4; --sidebar-bg: #f1f0ea; --line: rgba(17,24,39,.10); --muted: #6b7280; --text: #111827; flex: 1; min-height: 0; display: grid; grid-template-columns: 280px minmax(0, 1fr); height: 100%; overflow: hidden; border-radius: 20px; background: var(--chat-bg); border: 1px solid var(--line); box-shadow: 0 18px 50px rgba(15,23,42,.08); transition: grid-template-columns .2s ease; }
.chatgpt-page.collapsed { grid-template-columns: 0 minmax(0, 1fr); }
.conversation-sidebar { min-width: 0; overflow: hidden; display: flex; flex-direction: column; background: var(--sidebar-bg); border-right: 1px solid var(--line); }
.sidebar-top { display: grid; grid-template-columns: 64px 1fr; gap: 8px; padding: 12px; }
.sidebar-icon-button, .sidebar-toggle-floating { border: 1px solid rgba(17,24,39,.12); background: rgba(255,255,255,.72); color: #374151; border-radius: 12px; cursor: pointer; font-size: 12px; font-weight: 700; }
.sidebar-icon-button, .new-chat-button, .sidebar-toggle-floating { height: 34px; }
.sidebar-toggle-floating { position: absolute; top: 14px; left: 18px; z-index: 3; padding: 0 12px; }
.new-chat-button { border-radius: 12px; font-weight: 800; }
.conversation-list { min-height: 0; padding: 4px 10px 14px; overflow: auto; }
.conversation-item { padding: 11px 12px; border-radius: 14px; cursor: pointer; border: 1px solid transparent; margin-bottom: 6px; color: #202123; transition: background .16s ease, border-color .16s ease, transform .16s ease; }
.conversation-item:hover { background: rgba(255,255,255,.72); transform: translateY(-1px); }
.conversation-item.active { background: #fff; border-color: rgba(37,99,235,.20); box-shadow: 0 8px 24px rgba(15,23,42,.06); }
.conversation-title { font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-preview { color: var(--muted); font-size: 12px; margin-top: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; color: #8a8f98; font-size: 11px; margin-top: 6px; }
.chat-main { position: relative; min-width: 0; min-height: 0; height: 100%; overflow: hidden; display: grid; grid-template-rows: minmax(0, 1fr) auto; background: #fff; }
.message-scroll { position: relative; min-height: 0; overflow-y: auto; overflow-x: hidden; padding: 24px max(28px, calc((100% - 860px) / 2)) 32px; overscroll-behavior: contain; background: linear-gradient(180deg, #fff 0%, #fbfbf8 100%); }
.message-scroll.empty { display: grid; place-items: center; }
.message-loading { position: sticky; top: 8px; left: 50%; z-index: 2; display: flex; justify-content: center; pointer-events: none; }
.welcome-panel { width: min(760px, 100%); margin: auto; text-align: center; transform: translateY(-4vh); }
.welcome-mark { width: 54px; height: 54px; margin: 0 auto 18px; display: grid; place-items: center; border-radius: 18px; color: #fff; font-weight: 900; background: linear-gradient(135deg, #111827, #334155); box-shadow: 0 18px 44px rgba(15,23,42,.16); }
.welcome-panel h2 { margin: 0; color: var(--text); font-size: 30px; letter-spacing: -.04em; }
.welcome-panel p { margin: 12px auto 24px; max-width: 560px; color: var(--muted); font-size: 14px; line-height: 1.7; }
.prompt-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.prompt-card { min-height: 58px; padding: 13px 15px; border-radius: 16px; border: 1px solid rgba(17,24,39,.10); background: #fff; color: #374151; text-align: left; cursor: pointer; line-height: 1.45; box-shadow: 0 12px 28px rgba(15,23,42,.05); transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease; }
.prompt-card:hover { transform: translateY(-2px); border-color: rgba(37,99,235,.26); box-shadow: 0 18px 36px rgba(15,23,42,.08); }
.message-row { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 13px; margin-bottom: 24px; }
.message-row.user { grid-template-columns: minmax(0, 1fr); }
.message-row.user .message-bubble { grid-column: 1; grid-row: 1; justify-self: end; max-width: min(620px, 82%); background: #f4f4f4; border: 1px solid rgba(17,24,39,.08); border-radius: 22px; padding: 12px 16px; }
.message-avatar { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 999px; background: #111827; color: #fff; font-size: 12px; font-weight: 900; }
.message-bubble { min-width: 0; color: var(--text); line-height: 1.72; word-break: break-word; }
.user-content, .streaming-content { white-space: pre-wrap; overflow-wrap: anywhere; }
.markdown-body :deep(p) { margin: 4px 0 10px; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 22px; margin: 6px 0 12px; }
.markdown-body :deep(li) { margin: 3px 0; }
.markdown-body :deep(pre) { padding: 14px; border-radius: 12px; background: #f4f4f5; overflow: auto; border: 1px solid rgba(17,24,39,.08); }
.markdown-body :deep(code) { padding: 2px 5px; border-radius: 5px; background: #f4f4f5; }
.markdown-body :deep(table) { width: 100%; border-collapse: collapse; margin: 12px 0; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid rgba(148,163,184,.28); padding: 8px; text-align: left; }
.markdown-body :deep(img) {
  display: block;
  max-width: 100%;
  height: auto;
  max-height: 56vh;
  margin: 10px auto;
  border: 1px solid rgba(17, 24, 39, .08);
  border-radius: 10px;
  background: #f6f7f8;
  object-fit: contain;
}
.markdown-body :deep(img[data-secure-asset][src=""]) {
  width: min(100%, 420px);
  min-height: 160px;
}
.typing-cursor { display: inline-block; width: 7px; height: 1.1em; margin-left: 2px; vertical-align: -2px; background: #111827; animation: cursor-blink .9s steps(2, start) infinite; }
.thinking-state { display: inline-flex; align-items: center; gap: 8px; color: var(--muted); }
.thinking-dot { width: 8px; height: 8px; border-radius: 999px; background: #111827; animation: pulse 1.2s infinite ease-in-out; }
.thinking-dot:nth-child(2) { animation-delay: .15s; }
.thinking-dot:nth-child(3) { animation-delay: .3s; }
.thinking-label { margin-left: 4px; font-size: 13px; }
.streaming-hint { margin-top: 8px; font-size: 12px; color: var(--muted); }
.citations { margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(17,24,39,.08); color: var(--muted); font-size: 12px; }
.citations-toggle { width: 100%; display: flex; justify-content: space-between; align-items: center; border: 1px solid rgba(37,99,235,.14); border-radius: 13px; padding: 8px 11px; cursor: pointer; color: #1f2937; background: #f8fafc; font-weight: 800; }
.citation-list { display: grid; gap: 8px; margin-top: 8px; }
.citation-link { display: flex; justify-content: space-between; gap: 12px; width: 100%; border: 1px solid rgba(37,99,235,.14); border-radius: 13px; padding: 10px 11px; color: #1d4ed8; background: #fff; cursor: pointer; text-align: left; }
.citation-link:hover { border-color: rgba(37,99,235,.32); background: #eff6ff; }
.citation-file { flex: none; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); }
.message-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 13px; }
.rating-row, .rated-tag { margin-top: 10px; }
.composer-shell { min-height: 0; padding: 12px max(28px, calc((100% - 860px) / 2)) 16px; border-top: 1px solid var(--line); background: linear-gradient(180deg, rgba(255,255,255,.82), #fff); }
.chat-composer { display: grid; grid-template-columns: minmax(0, 1fr) 38px; gap: 8px; align-items: end; padding: 9px 10px 9px 16px; border: 1px solid rgba(17,24,39,.13); border-radius: 24px; background: #fff; box-shadow: 0 14px 42px rgba(15,23,42,.10); }
.chat-composer :deep(.n-input) { --n-border: none !important; --n-border-hover: none !important; --n-border-focus: none !important; --n-box-shadow-focus: none !important; --n-color: transparent !important; }
.chat-composer :deep(.n-input-wrapper) { min-height: 34px; padding: 0; background: transparent; }
.chat-composer :deep(textarea) { line-height: 1.55; padding-top: 5px; }
.send-button { width: 38px; height: 38px; min-height: 38px; font-size: 18px; font-weight: 900; }
.composer-hint { margin-top: 8px; text-align: center; color: #9ca3af; font-size: 12px; }
@keyframes pulse { 0%, 80%, 100% { opacity: .35; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-2px); } }
@keyframes cursor-blink { 0%, 45% { opacity: 1; } 46%, 100% { opacity: 0; } }
@media (max-width: 900px) {
  .chatgpt-page, .chatgpt-page.collapsed { grid-template-columns: 1fr; height: 100%; min-height: 0; }
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
