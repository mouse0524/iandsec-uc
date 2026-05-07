<script setup>
import { nextTick, ref } from 'vue'
import { getToken } from '@/utils'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '智能对话' })

const input = ref('')
const streaming = ref(false)
const timeline = ref([])
const answer = ref('')
const citations = ref([])
const lastMessageId = ref(null)
const conversationId = ref(null)
const scroller = ref(null)

function pushEvent(item) {
  timeline.value.push(item)
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}

async function send() {
  if (!input.value.trim() || streaming.value) return
  const message = input.value.trim()
  input.value = ''
  answer.value = ''
  citations.value = []
  lastMessageId.value = null
  streaming.value = true
  try {
    const resp = await fetch(`${import.meta.env.VITE_BASE_API}/skill-know/chat/agent/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', token: getToken() || '' },
      body: JSON.stringify({ message, conversation_id: conversationId.value }),
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
      for (const part of parts) {
        const line = part.split('\n').find((i) => i.startsWith('data:'))
        if (!line) continue
        const item = JSON.parse(line.replace(/^data:\s*/, ''))
        if (item.type === 'assistant.delta') answer.value += item.payload?.content || ''
        else if (item.type === 'final') {
          conversationId.value = item.payload?.conversation_id || conversationId.value
          lastMessageId.value = item.payload?.message_id || null
          citations.value = item.payload?.citations || []
        } else pushEvent(item)
      }
    }
  } catch (error) {
    pushEvent({ type: 'error', payload: { message: error.message || '对话失败' } })
  } finally {
    streaming.value = false
    if (answer.value) pushEvent({ type: 'assistant.message', payload: { content: answer.value, citations: citations.value, message_id: lastMessageId.value } })
  }
}

async function rateAnswer(rating, isHelpful) {
  if (!lastMessageId.value) return
  await api.skillKnowFeedbackMessage({ message_id: lastMessageId.value, rating, is_helpful: isHelpful })
  $message.success('评分已提交')
}

function resetChat() {
  timeline.value = []
  answer.value = ''
  citations.value = []
  lastMessageId.value = null
  conversationId.value = null
}

function eventTitle(type) {
  return {
    'user.message': '用户消息',
    'phase.changed': '阶段切换',
    'search.results': '检索结果',
    'llm.call.started': '模型调用',
    'llm.call.completed': '模型完成',
    'assistant.message': 'AI 回复',
    error: '错误',
  }[type] || type
}
</script>

<template>
  <CommonPage title="智能对话" show-footer>
    <div class="sk-theme-page">
      <div class="sk-hero">
        <h2 class="sk-hero-title">知识库智能对话</h2>
        <p class="sk-hero-sub">基于 Markdown 文档片段回答问题，面向产品技术支持与数据安全场景，并保留引用来源。</p>
      </div>
      <NCard class="chat-card" :bordered="false">
        <template #header>
          <NSpace justify="space-between"><span>对话</span><NButton secondary size="small" @click="resetChat">新对话</NButton></NSpace>
        </template>
        <div ref="scroller" class="timeline-scroll">
          <NEmpty v-if="!timeline.length" description="开始一次基于知识库的对话" />
          <div v-for="(item, idx) in timeline" :key="idx" class="event-card" :class="item.type.replaceAll('.', '-')">
            <NSpace justify="space-between" align="center"><b>{{ eventTitle(item.type) }}</b><NTag size="small">{{ item.type }}</NTag></NSpace>
            <div v-if="item.type === 'search.results'" class="event-body">
              <div v-for="hit in item.payload.items" :key="hit.chunk_uri || hit.chunk_id" class="citation-hit">
                <b>{{ hit.title }}</b><span>{{ hit.heading || '无章节' }} · score {{ hit.score || 0 }}</span>
                <p>{{ hit.abstract }}</p>
              </div>
            </div>
            <div v-else-if="item.type === 'assistant.message'" class="answer-body">
              {{ item.payload.content }}
              <div v-if="item.payload.citations?.length" class="citations">
                <b>引用来源</b>
                <div v-for="cite in item.payload.citations" :key="cite.chunk_uri || cite.chunk_id" class="citation-hit">
                  {{ cite.title }} · {{ cite.heading || '无章节' }} · {{ cite.filename || '-' }}
                </div>
              </div>
              <NSpace v-if="item.payload.message_id" class="rating-row">
                <NButton size="small" secondary type="success" @click="rateAnswer(5, true)">有帮助</NButton>
                <NButton size="small" secondary type="error" @click="rateAnswer(1, false)">无帮助</NButton>
              </NSpace>
            </div>
            <pre v-else>{{ JSON.stringify(item.payload, null, 2) }}</pre>
          </div>
          <div v-if="streaming && answer" class="event-card assistant-message"><b>AI 回复中</b><div class="answer-body">{{ answer }}</div></div>
        </div>
        <div class="input-bar">
          <NInput v-model:value="input" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="输入产品技术支持或数据安全问题，Ctrl+Enter 发送" @keydown.ctrl.enter="send" />
          <NButton type="primary" size="large" :loading="streaming" :disabled="!input.trim()" @click="send">发送</NButton>
        </div>
      </NCard>
    </div>
  </CommonPage>
</template>

<style scoped>
.chat-card { border-radius: 20px; min-height: calc(100vh - 170px); }
.timeline-scroll { height: calc(100vh - 330px); overflow: auto; padding-right: 8px; }
.event-card { padding: 14px; border-radius: 14px; margin-bottom: 12px; background: rgba(148, 163, 184, .10); border: 1px solid rgba(148, 163, 184, .18); }
.search-results { background: rgba(32, 128, 240, .10); }
.phase-changed { background: rgba(245, 158, 11, .10); }
.llm-call-started, .llm-call-completed { background: rgba(30, 64, 175, .10); }
.assistant-message { background: rgba(24, 160, 88, .10); }
.error { background: rgba(208, 48, 80, .12); }
pre { margin: 8px 0 0; white-space: pre-wrap; font-size: 12px; }
.answer-body { white-space: pre-wrap; line-height: 1.7; margin-top: 8px; }
.citation-hit { padding: 8px 0; border-bottom: 1px dashed rgba(148, 163, 184, .3); }
.citation-hit span, .citation-hit p { color: #64748b; margin: 4px 0; }
.citations, .rating-row { margin-top: 12px; }
.input-bar { display: grid; grid-template-columns: 1fr 110px; gap: 12px; margin-top: 16px; }
</style>
