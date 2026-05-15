<script setup>
import { h, onMounted, ref } from 'vue'
import { NButton, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '对话历史' })

const loading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const conversations = ref([])
const selected = ref(null)

const columns = [
  {
    title: '会话标题',
    key: 'title',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => row.title || `会话 ${row.id}`,
  },
  {
    title: '提问人姓名',
    key: 'owner_name',
    width: 140,
    ellipsis: { tooltip: true },
    render: (row) => row.owner_name || '-',
  },
  {
    title: '最后消息',
    key: 'last_message_preview',
    minWidth: 360,
    ellipsis: { tooltip: true },
    render: (row) => row.last_message_preview || '-',
  },
  {
    title: '消息类型',
    key: 'last_message_role',
    width: 100,
    render: (row) => roleTag(row.last_message_role),
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
    fixed: 'right',
    render: (row) =>
      h(
        NButton,
        { size: 'small', type: 'primary', secondary: true, onClick: () => openConversation(row) },
        { default: () => '查看' },
      ),
  },
]

onMounted(loadConversations)

async function loadConversations() {
  loading.value = true
  try {
    const res = await api.skillKnowConversations({ page: 1, page_size: 100 })
    conversations.value = res.data || []
  } finally {
    loading.value = false
  }
}

async function openConversation(item) {
  detailLoading.value = true
  detailVisible.value = true
  try {
    const res = await api.skillKnowGetConversation({ conversation_id: item.id })
    selected.value = res.data
  } finally {
    detailLoading.value = false
  }
}

function roleTag(role) {
  const label = role === 'user' ? '用户' : role === 'assistant' ? 'AI' : role || '-'
  const type = role === 'assistant' ? 'success' : role === 'user' ? 'info' : 'default'
  return h(NTag, { size: 'small', type, bordered: false }, { default: () => label })
}

function roleText(role) {
  return role === 'user' ? '用户' : role === 'assistant' ? 'AI' : role || '-'
}

function citationText(cite) {
  const title = cite.title || cite.filename || '未命名文档'
  const heading = cite.heading ? ` / ${cite.heading}` : ''
  const lineRange = Array.isArray(cite.line_range)
    ? ` / 行 ${cite.line_range[0]}-${cite.line_range[1]}`
    : ''
  return `${title}${heading}${lineRange}`
}

function citationKey(cite, index) {
  return cite.evidence_id || cite.section_id || cite.chunk_id || `${cite.title || 'cite'}-${index}`
}
</script>

<template>
  <CommonPage title="对话历史" :show-header="false" show-footer>
    <div class="history-workspace">
      <header class="history-header">
        <div>
          <div class="eyebrow">Reader Agent</div>
          <h1>对话历史</h1>
          <p>查看历史问答、提问人和引用来源；点击“查看”打开完整对话详情。</p>
        </div>
        <NButton size="small" secondary :loading="loading" @click="loadConversations">刷新</NButton>
      </header>

      <NDataTable
        :columns="columns"
        :data="conversations"
        :loading="loading"
        size="small"
        :pagination="{ pageSize: 12 }"
        :scroll-x="1120"
      />
    </div>

    <NDrawer v-model:show="detailVisible" :width="900" placement="right">
      <NDrawerContent
        :title="selected?.title || (selected?.id ? `会话 ${selected.id}` : '会话详情')"
        closable
      >
        <NSpin :show="detailLoading">
          <template v-if="selected">
            <div class="detail-meta">
              <div>
                <span>提问人</span>
                <strong>{{ selected.owner_name || '-' }}</strong>
              </div>
              <div>
                <span>更新时间</span>
                <strong>{{ selected.updated_at || selected.created_at || '-' }}</strong>
              </div>
              <div>
                <span>会话 ID</span>
                <strong>{{ selected.id }}</strong>
              </div>
            </div>

            <div class="message-flow">
              <article
                v-for="msg in selected.messages"
                :key="msg.id"
                class="message-row"
                :class="msg.role"
              >
                <div class="avatar">{{ msg.role === 'user' ? '用户' : 'AI' }}</div>
                <div class="message-bubble">
                  <div class="message-role">{{ roleText(msg.role) }}</div>
                  <pre>{{ msg.content }}</pre>
                  <div v-if="msg.extra_metadata?.citations?.length" class="citations">
                    <b>引用来源</b>
                    <p
                      v-for="(cite, index) in msg.extra_metadata.citations"
                      :key="citationKey(cite, index)"
                    >
                      {{ citationText(cite) }}
                    </p>
                  </div>
                </div>
              </article>
            </div>
          </template>
          <NEmpty v-else description="暂无对话详情" />
        </NSpin>
      </NDrawerContent>
    </NDrawer>
  </CommonPage>
</template>

<style scoped>
.history-workspace {
  --line: rgba(17, 24, 39, 0.1);
  --text: #111827;
  --muted: #6b7280;
  min-height: calc(100vh - 128px);
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}

.history-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.eyebrow {
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

h1,
p {
  margin: 0;
}

h1 {
  margin-top: 4px;
  color: var(--text);
  font-size: 24px;
  font-weight: 700;
}

.history-header p {
  margin-top: 6px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
}

.detail-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(17, 24, 39, 0.1);
}

.detail-meta div {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid rgba(17, 24, 39, 0.08);
  border-radius: 8px;
  background: #fafafa;
}

.detail-meta span {
  display: block;
  color: #6b7280;
  font-size: 12px;
}

.detail-meta strong {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: #111827;
  font-size: 13px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-flow {
  display: grid;
  gap: 18px;
  padding-top: 18px;
}

.message-row {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
}

.avatar {
  width: 42px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #111827;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.message-row.assistant .avatar {
  background: #0f766e;
}

.message-bubble {
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid rgba(17, 24, 39, 0.08);
  border-radius: 8px;
  background: #fff;
}

.message-role {
  margin-bottom: 8px;
  color: #6b7280;
  font-size: 12px;
  font-weight: 700;
}

pre {
  margin: 0;
  color: #111827;
  font-family: inherit;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.citations {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(17, 24, 39, 0.1);
}

.citations p {
  margin: 7px 0 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 820px) {
  .history-header,
  .detail-meta {
    grid-template-columns: 1fr;
  }

  .history-header {
    display: grid;
  }
}
</style>
