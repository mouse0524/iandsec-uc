<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { NButton } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '对话管理（评分）' })

const loading = ref(false)
const conversations = ref([])
const feedbacks = ref([])
const candidates = ref([])
const selected = ref(null)

const conversationColumns = computed(() => ([
  {
    title: '会话标题',
    key: 'title',
    ellipsis: { tooltip: true },
    render: (row) => row.title || `会话 ${row.id}`,
  },
  {
    title: '最后消息',
    key: 'last_message_preview',
    ellipsis: { tooltip: true },
    render: (row) => row.last_message_preview || '-',
  },
  {
    title: '评分',
    key: 'rating',
    width: 120,
    render: (row) => conversationRating(row.id),
  },
  {
    title: '反馈数',
    key: 'feedback_count',
    width: 100,
    render: (row) => conversationFeedbackCount(row.id),
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 180,
    render: (row) => row.updated_at || row.created_at || '-',
  },
  {
    title: '操作',
    key: 'actions',
    width: 110,
    render: (row) => h(
      NButton,
      { size: 'small', type: 'primary', secondary: true, onClick: () => openConversation(row) },
      { default: () => '查看详情' },
    ),
  },
]))

onMounted(loadAll)

async function fetchAllPages(requestFn) {
  const pageSize = 100
  let page = 1
  let total = 0
  const rows = []
  do {
    const res = await requestFn({ page, page_size: pageSize })
    total = Number(res.total || 0)
    rows.push(...(res.data || []))
    page += 1
  } while (rows.length < total)
  return rows
}

async function loadAll() {
  loading.value = true
  try {
    const [convRows, fbRows, candidateRows] = await Promise.all([
      fetchAllPages(api.skillKnowConversations),
      fetchAllPages(api.skillKnowFeedbackList),
      fetchAllPages(api.skillKnowLearningCandidates),
    ])
    conversations.value = convRows
    feedbacks.value = fbRows
    candidates.value = candidateRows
  } finally {
    loading.value = false
  }
}

async function openConversation(item) {
  const res = await api.skillKnowGetConversation({ conversation_id: item.id })
  selected.value = res.data
}

function conversationRating(conversationId) {
  const rows = (feedbacks.value || []).filter((item) => Number(item.conversation_id) === Number(conversationId))
  if (!rows.length) return '-'
  const valid = rows.map((item) => Number(item.rating)).filter((n) => Number.isFinite(n) && n > 0)
  if (!valid.length) return '已反馈'
  const avg = valid.reduce((sum, n) => sum + n, 0) / valid.length
  return `${avg.toFixed(1)} / 5`
}

function conversationFeedbackCount(conversationId) {
  return (feedbacks.value || []).filter((item) => Number(item.conversation_id) === Number(conversationId)).length
}

async function approveCandidate(item) {
  await api.skillKnowApproveLearningCandidate({ candidate_id: item.id, candidate_markdown: item.candidate_markdown })
  $message.success('已通过学习候选')
  await loadAll()
}

async function rejectCandidate(item) {
  await api.skillKnowRejectLearningCandidate({ candidate_id: item.id })
  $message.success('已拒绝学习候选')
  await loadAll()
}
</script>

<template>
  <CommonPage title="对话管理（评分）" :show-header="false" show-footer>
    <div class="audit-workspace">
      <aside class="audit-sidebar">
        <div class="sidebar-head">
          <div>
            <div class="eyebrow">Conversation Audit</div>
            <h2>对话审计</h2>
            <p>集中查看历史对话、用户评分和可沉淀为知识的低分反馈。</p>
          </div>
          <NButton size="small" secondary :loading="loading" @click="loadAll">刷新</NButton>
        </div>

        <div class="metric-stack">
          <div class="metric-card">
            <span>会话</span>
            <b>{{ conversations.length }}</b>
          </div>
          <div class="metric-card">
            <span>评分</span>
            <b>{{ feedbacks.length }}</b>
          </div>
          <div class="metric-card">
            <span>候选</span>
            <b>{{ candidates.length }}</b>
          </div>
        </div>

        <NSpin :show="loading">
          <div class="conversation-list">
            <button
              v-for="item in conversations"
              :key="item.id"
              class="conversation-card"
              :class="{ active: selected?.id === item.id }"
              type="button"
              @click="openConversation(item)"
            >
              <span class="conversation-title">{{ item.title || `会话 ${item.id}` }}</span>
              <span class="conversation-preview">{{ item.last_message_preview || '暂无消息预览' }}</span>
              <span class="conversation-meta">
                <span>{{ conversationRating(item.id) }}</span>
                <span>{{ item.updated_at || item.created_at || '-' }}</span>
              </span>
            </button>
            <NEmpty v-if="!conversations.length" description="暂无对话" />
          </div>
        </NSpin>
      </aside>

      <section class="audit-main">
        <header class="main-header">
          <div>
            <div class="eyebrow">Feedback Loop</div>
            <h1>评分与学习候选</h1>
            <p>像审阅一段对话一样检查反馈，并把有价值的内容审核入库。</p>
          </div>
        </header>

        <div class="review-grid">
          <section class="panel feedback-panel">
            <div class="panel-head">
              <div>
                <h3>评分记录</h3>
                <p>{{ feedbacks.length }} 条用户反馈</p>
              </div>
            </div>
            <div class="feedback-list">
              <div v-for="item in feedbacks" :key="item.id" class="feedback-item">
                <div class="feedback-top">
                  <b>消息 {{ item.message_id }}</b>
                  <NTag size="small" round>{{ item.rating || '-' }} 分</NTag>
                </div>
                <p>{{ item.reason || (item.is_helpful ? '有帮助' : '无帮助') }}</p>
              </div>
              <NEmpty v-if="!feedbacks.length" description="暂无评分" />
            </div>
          </section>

          <section class="panel candidate-panel">
            <div class="panel-head">
              <div>
                <h3>学习候选</h3>
                <p>审核后可补充到知识库。</p>
              </div>
            </div>
            <div class="candidate-list">
              <article v-for="item in candidates" :key="item.id" class="candidate-item">
                <div class="candidate-title">
                  <b>{{ item.question }}</b>
                  <NTag size="small" round>{{ item.status }}</NTag>
                </div>
                <NInput v-model:value="item.candidate_markdown" type="textarea" :autosize="{ minRows: 5, maxRows: 12 }" />
                <NSpace class="actions">
                  <NButton size="small" type="primary" :disabled="item.status !== 'pending'" @click="approveCandidate(item)">通过</NButton>
                  <NButton size="small" secondary type="error" :disabled="item.status !== 'pending'" @click="rejectCandidate(item)">拒绝</NButton>
                </NSpace>
              </article>
              <NEmpty v-if="!candidates.length" description="暂无学习候选" />
            </div>
          </section>
        </div>

        <section class="panel detail-panel">
          <div class="panel-head">
            <div>
              <h3>会话详情</h3>
              <p>{{ selected ? (selected.title || `会话 ${selected.id}`) : '请选择左侧会话查看完整消息流' }}</p>
            </div>
          </div>

          <template v-if="selected">
            <div class="message-flow">
              <article v-for="msg in selected.messages" :key="msg.id" class="message-row" :class="msg.role">
                <div class="avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
                <div class="message-bubble">
                  <div class="message-role">{{ msg.role }}</div>
                  <pre>{{ msg.content }}</pre>
                  <div v-if="msg.extra_metadata?.citations?.length" class="citations">
                    <b>引用来源</b>
                    <p v-for="cite in msg.extra_metadata.citations" :key="cite.chunk_uri || cite.chunk_id">{{ cite.title }} · {{ cite.heading || '无章节' }}</p>
                  </div>
                </div>
              </article>
            </div>
          </template>
          <NEmpty v-else description="请选择对话" />
        </section>
      </section>
    </div>
  </CommonPage>
</template>

<style scoped>
.audit-workspace {
  --ai-bg: #f7f7f4;
  --ai-sidebar: #f1f0ea;
  --ai-line: rgba(17, 24, 39, .10);
  --ai-text: #111827;
  --ai-muted: #6b7280;
  display: grid;
  grid-template-columns: 330px minmax(0, 1fr);
  height: calc(100vh - 96px);
  min-height: 560px;
  overflow: hidden;
  border: 1px solid var(--ai-line);
  border-radius: 20px;
  background: var(--ai-bg);
  box-shadow: 0 18px 50px rgba(15, 23, 42, .08);
}
.audit-sidebar {
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 14px;
  padding: 18px;
  border-right: 1px solid var(--ai-line);
  background: var(--ai-sidebar);
}
.sidebar-head, .main-header, .panel-head, .candidate-title, .feedback-top, .conversation-meta {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.eyebrow {
  color: #10a37f;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}
h1, h2, h3, p { margin: 0; }
h1, h2, h3 { color: var(--ai-text); font-weight: 800; }
.sidebar-head h2, .main-header h1 { margin-top: 6px; }
.sidebar-head p, .main-header p, .panel-head p, .conversation-preview, .feedback-item p, .citations p {
  margin-top: 7px;
  color: var(--ai-muted);
  font-size: 13px;
  line-height: 1.6;
}
.metric-stack {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.metric-card {
  padding: 12px;
  border: 1px solid var(--ai-line);
  border-radius: 14px;
  background: rgba(255, 255, 255, .68);
}
.metric-card span {
  display: block;
  color: var(--ai-muted);
  font-size: 12px;
}
.metric-card b {
  display: block;
  margin-top: 4px;
  color: var(--ai-text);
  font-size: 22px;
}
.conversation-list {
  display: grid;
  gap: 8px;
  min-height: 0;
  overflow: auto;
  padding-right: 4px;
}
.conversation-card {
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
.conversation-card:hover, .conversation-card.active {
  border-color: rgba(17, 24, 39, .12);
  background: rgba(255, 255, 255, .76);
  box-shadow: 0 10px 24px rgba(15, 23, 42, .07);
}
.conversation-title {
  color: var(--ai-text);
  font-weight: 800;
}
.conversation-preview {
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.conversation-meta {
  color: var(--ai-muted);
  font-size: 12px;
}
.audit-main {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: 24px max(26px, calc((100% - 1040px) / 2));
  background: linear-gradient(180deg, #fff 0%, #fbfbf8 100%);
}
.main-header {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--ai-line);
}
.review-grid {
  display: grid;
  grid-template-columns: minmax(260px, .82fr) minmax(360px, 1.18fr);
  gap: 16px;
  margin-top: 16px;
}
.panel {
  border: 1px solid var(--ai-line);
  border-radius: 18px;
  background: rgba(255, 255, 255, .86);
  box-shadow: 0 12px 34px rgba(15, 23, 42, .06);
  overflow: hidden;
}
.panel-head {
  padding: 16px;
  border-bottom: 1px solid var(--ai-line);
  background: #fbfbf8;
}
.feedback-list, .candidate-list {
  display: grid;
  gap: 10px;
  max-height: 360px;
  overflow: auto;
  padding: 14px;
}
.feedback-item, .candidate-item {
  padding: 13px;
  border: 1px solid rgba(17, 24, 39, .08);
  border-radius: 14px;
  background: #fff;
}
.candidate-item {
  display: grid;
  gap: 12px;
}
.actions { margin-top: 2px; }
.detail-panel {
  margin-top: 16px;
}
.message-flow {
  display: grid;
  gap: 20px;
  padding: 20px max(18px, calc((100% - 860px) / 2));
}
.message-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 12px;
}
.avatar {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: #111827;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}
.message-row.assistant .avatar {
  background: #10a37f;
}
.message-bubble {
  padding: 14px 16px;
  border: 1px solid rgba(17, 24, 39, .08);
  border-radius: 16px;
  background: #fff;
}
.message-role {
  margin-bottom: 8px;
  color: var(--ai-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}
pre {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.75;
  color: var(--ai-text);
}
.citations {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--ai-line);
}
@media (max-width: 1100px) {
  .audit-workspace { grid-template-columns: 1fr; height: auto; min-height: calc(100vh - 96px); }
  .audit-sidebar { border-right: 0; border-bottom: 1px solid var(--ai-line); }
  .review-grid { grid-template-columns: 1fr; }
}
</style>
