<script setup>
import { onMounted, ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '对话管理（评分）' })

const loading = ref(false)
const conversations = ref([])
const feedbacks = ref([])
const candidates = ref([])
const selected = ref(null)

onMounted(loadAll)

async function loadAll() {
  loading.value = true
  try {
    const [convRes, fbRes, candidateRes] = await Promise.all([
      api.skillKnowConversations({ page: 1, page_size: 50 }),
      api.skillKnowFeedbackList({ page: 1, page_size: 50 }),
      api.skillKnowLearningCandidates({ page: 1, page_size: 50 }),
    ])
    conversations.value = convRes.data || []
    feedbacks.value = fbRes.data || []
    candidates.value = candidateRes.data || []
  } finally {
    loading.value = false
  }
}

async function openConversation(item) {
  const res = await api.skillKnowGetConversation({ conversation_id: item.id })
  selected.value = res.data
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
  <CommonPage title="对话管理（评分）" show-footer>
    <div class="sk-theme-page">
      <div class="sk-hero">
        <h2 class="sk-hero-title">对话、评分与学习候选</h2>
        <p class="sk-hero-sub">查看历史对话、用户评分和由低分反馈生成的待审核知识补充建议。</p>
      </div>
      <NSpin :show="loading">
        <div class="manage-shell">
          <NCard title="对话记录" :bordered="false">
            <div v-for="item in conversations" :key="item.id" class="list-item" @click="openConversation(item)">
              <b>{{ item.title || `会话 ${item.id}` }}</b>
              <p>{{ item.updated_at || item.created_at }}</p>
            </div>
            <NEmpty v-if="!conversations.length" description="暂无对话" />
          </NCard>
          <NCard title="评分记录" :bordered="false">
            <div v-for="item in feedbacks" :key="item.id" class="list-item">
              <b>消息 {{ item.message_id }} · {{ item.rating || '-' }} 分</b>
              <p>{{ item.reason || (item.is_helpful ? '有帮助' : '无帮助') }}</p>
            </div>
            <NEmpty v-if="!feedbacks.length" description="暂无评分" />
          </NCard>
          <NCard title="学习候选" :bordered="false" class="candidate-card">
            <div v-for="item in candidates" :key="item.id" class="candidate-item">
              <NSpace justify="space-between" align="center"><b>{{ item.question }}</b><NTag>{{ item.status }}</NTag></NSpace>
              <NInput v-model:value="item.candidate_markdown" type="textarea" :autosize="{ minRows: 6, maxRows: 14 }" />
              <NSpace class="actions">
                <NButton size="small" type="primary" :disabled="item.status !== 'pending'" @click="approveCandidate(item)">通过</NButton>
                <NButton size="small" secondary type="error" :disabled="item.status !== 'pending'" @click="rejectCandidate(item)">拒绝</NButton>
              </NSpace>
            </div>
            <NEmpty v-if="!candidates.length" description="暂无学习候选" />
          </NCard>
          <NCard title="会话详情" :bordered="false" class="detail-card">
            <template v-if="selected">
              <div v-for="msg in selected.messages" :key="msg.id" class="message-item" :class="msg.role">
                <b>{{ msg.role }}</b>
                <pre>{{ msg.content }}</pre>
                <div v-if="msg.extra_metadata?.citations?.length" class="citations">
                  <b>引用</b>
                  <p v-for="cite in msg.extra_metadata.citations" :key="cite.chunk_uri || cite.chunk_id">{{ cite.title }} · {{ cite.heading || '无章节' }}</p>
                </div>
              </div>
            </template>
            <NEmpty v-else description="请选择对话" />
          </NCard>
        </div>
      </NSpin>
    </div>
  </CommonPage>
</template>

<style scoped>
.manage-shell { display: grid; grid-template-columns: 320px 320px 1fr; gap: 16px; }
.candidate-card, .detail-card { grid-column: span 3; }
.list-item, .candidate-item, .message-item { padding: 12px; border-radius: 12px; margin-bottom: 10px; background: rgba(148, 163, 184, .10); border: 1px solid rgba(148, 163, 184, .18); }
.list-item { cursor: pointer; }
.list-item p, .citations p { color: #64748b; margin: 6px 0 0; }
.actions { margin-top: 10px; }
pre { white-space: pre-wrap; word-break: break-word; margin: 8px 0 0; }
.assistant { background: rgba(24, 160, 88, .10); }
.user { background: rgba(32, 128, 240, .10); }
@media (max-width: 1100px) { .manage-shell { grid-template-columns: 1fr; } .candidate-card, .detail-card { grid-column: auto; } }
</style>
