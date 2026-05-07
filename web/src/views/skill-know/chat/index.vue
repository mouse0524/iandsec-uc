<script setup>
import { nextTick, onMounted, ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '智能对话' })

const input = ref('')
const loading = ref(false)
const sending = ref(false)
const conversations = ref([])
const messages = ref([])
const conversationId = ref(null)
const currentConversation = ref(null)
const scroller = ref(null)

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
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return
  input.value = ''
  const localUser = { id: `local-user-${Date.now()}`, role: 'user', content: text }
  const localAssistant = { id: `local-assistant-${Date.now()}`, role: 'assistant', content: '正在思考...', pending: true }
  messages.value.push(localUser, localAssistant)
  await scrollToBottom()
  sending.value = true
  try {
    const res = await api.skillKnowChat({ message: text, conversation_id: conversationId.value })
    const data = res.data || {}
    conversationId.value = data.conversation_id || conversationId.value
    Object.assign(localAssistant, {
      id: data.message_id || localAssistant.id,
      content: data.content || '未返回内容',
      pending: false,
      extra_metadata: { citations: data.citations || [] },
    })
    await loadConversations()
    const current = conversations.value.find((item) => item.id === conversationId.value)
    if (current) currentConversation.value = current
  } catch (error) {
    localAssistant.content = error.message || '对话失败，请稍后重试'
    localAssistant.pending = false
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

async function rateMessage(msg, rating, isHelpful) {
  if (!msg.id || String(msg.id).startsWith('local-')) return
  await api.skillKnowFeedbackMessage({ message_id: msg.id, rating, is_helpful: isHelpful })
  msg.rated = true
  $message.success('评分已提交')
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
</script>

<template>
  <CommonPage title="智能对话" show-footer>
    <div class="sk-theme-page chat-page">
      <aside class="conversation-sidebar">
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
            <div class="conversation-time">{{ item.updated_at || item.created_at }}</div>
            <NButton size="tiny" quaternary type="error" @click.stop="deleteConversation(item)">删除</NButton>
          </div>
          <NEmpty v-if="!conversations.length" description="暂无历史会话" />
        </div>
      </aside>

      <section class="chat-main">
        <div class="chat-header">
          <div>
            <h2>{{ currentConversation ? conversationTitle(currentConversation) : '新会话' }}</h2>
            <p>基于知识库 Markdown 文档回答，保留会话上下文。</p>
          </div>
        </div>

        <NSpin :show="loading">
          <div ref="scroller" class="message-scroll">
            <NEmpty v-if="!messages.length" description="输入问题开始对话，历史会话会自动保存" />
            <div v-for="msg in messages" :key="msg.id" class="message-row" :class="msg.role">
              <div class="message-bubble">
                <div class="message-role">{{ msg.role === 'user' ? '你' : 'AI 助手' }}</div>
                <div class="message-content">{{ msg.content }}</div>
                <div v-if="msg.extra_metadata?.citations?.length" class="citations">
                  <b>引用来源</b>
                  <p v-for="cite in msg.extra_metadata.citations" :key="cite.chunk_uri || cite.chunk_id">
                    {{ cite.title }} · {{ cite.heading || '无章节' }} · {{ cite.filename || '-' }}
                  </p>
                </div>
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
            placeholder="继续追问或输入新的产品技术支持/数据安全问题，Ctrl+Enter 发送"
            @keydown.ctrl.enter="send"
          />
          <NButton type="primary" size="large" :loading="sending" :disabled="!input.trim()" @click="send">发送</NButton>
        </div>
      </section>
    </div>
  </CommonPage>
</template>

<style scoped>
.chat-page { display: grid; grid-template-columns: 300px 1fr; gap: 16px; height: calc(100vh - 110px); }
.conversation-sidebar, .chat-main { border-radius: 20px; background: rgba(255,255,255,.76); border: 1px solid rgba(148,163,184,.18); box-shadow: 0 12px 36px rgba(15,23,42,.06); }
.conversation-sidebar { padding: 14px; overflow: hidden; display: flex; flex-direction: column; }
.conversation-list { margin-top: 12px; overflow: auto; }
.conversation-item { position: relative; padding: 12px; border-radius: 14px; cursor: pointer; border: 1px solid transparent; margin-bottom: 10px; background: rgba(148,163,184,.08); }
.conversation-item:hover, .conversation-item.active { background: rgba(32,128,240,.10); border-color: rgba(32,128,240,.24); }
.conversation-title { font-weight: 700; padding-right: 44px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-time { color: #7b8494; font-size: 12px; margin-top: 6px; }
.conversation-item .n-button { position: absolute; right: 8px; top: 8px; }
.chat-main { min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
.chat-header { padding: 18px 22px; border-bottom: 1px solid rgba(148,163,184,.18); }
.chat-header h2 { margin: 0; }
.chat-header p { margin: 6px 0 0; color: #64748b; }
.message-scroll { height: calc(100vh - 290px); overflow: auto; padding: 24px; background: linear-gradient(180deg, rgba(248,250,252,.55), rgba(241,245,249,.35)); }
.message-row { display: flex; margin-bottom: 16px; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }
.message-bubble { max-width: min(780px, 78%); padding: 14px 16px; border-radius: 18px; line-height: 1.75; white-space: pre-wrap; word-break: break-word; }
.message-row.user .message-bubble { background: #2563eb; color: white; border-top-right-radius: 6px; }
.message-row.assistant .message-bubble { background: white; color: #172033; border: 1px solid rgba(148,163,184,.22); border-top-left-radius: 6px; }
.message-role { font-size: 12px; opacity: .72; margin-bottom: 6px; }
.citations { margin-top: 12px; padding-top: 10px; border-top: 1px dashed rgba(148,163,184,.38); color: #64748b; font-size: 12px; }
.citations p { margin: 4px 0; }
.rating-row, .rated-tag { margin-top: 10px; }
.input-bar { display: grid; grid-template-columns: 1fr 110px; gap: 12px; padding: 16px; border-top: 1px solid rgba(148,163,184,.18); background: rgba(255,255,255,.86); }
@media (max-width: 900px) {
  .chat-page { grid-template-columns: 1fr; height: auto; }
  .conversation-sidebar { max-height: 260px; }
  .message-scroll { height: 58vh; }
  .message-bubble { max-width: 92%; }
}
</style>
