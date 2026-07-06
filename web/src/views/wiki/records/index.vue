<script setup>
import { h, onMounted, ref } from 'vue'
import { NButton, NDataTable, NInput, NModal, NSpace, NTabPane, NTabs, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '问答反馈' })

const tab = ref('records')
const loading = ref(false)
const feedbackLoading = ref(false)
const keyword = ref('')
const records = ref([])
const feedback = ref([])
const recordTotal = ref(0)
const feedbackTotal = ref(0)
const recordPage = ref(1)
const feedbackPage = ref(1)
const pageSize = 10
const editing = ref(null)
const learningContent = ref('')

const reasonLabels = {
  no_match: '未命中',
  empty_answer: '空回答',
  unhelpful_feedback: '用户反馈',
}

const recordColumns = [
  { title: '用户', key: 'owner_name', width: 120 },
  { title: '问题', key: 'question', minWidth: 220, ellipsis: { tooltip: true } },
  { title: '回答', key: 'content', minWidth: 280, ellipsis: { tooltip: true } },
  { title: '归档', key: 'archive_path', minWidth: 180, ellipsis: { tooltip: true } },
]

const feedbackColumns = [
  {
    title: '类型',
    key: 'reason',
    width: 110,
    render(row) {
      return h(NTag, { type: row.reason === 'unhelpful_feedback' ? 'warning' : 'info' }, { default: () => reasonLabels[row.reason] || row.reason })
    },
  },
  { title: '问题', key: 'question', minWidth: 220, ellipsis: { tooltip: true } },
  { title: '原回答', key: 'answer', minWidth: 260, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render(row) {
      return h(NSpace, { size: 8 }, {
        default: () => [
          h(NButton, { size: 'small', type: 'primary', secondary: true, onClick: () => openLearning(row) }, { default: () => '调整学习' }),
          h(NButton, { size: 'small', secondary: true, onClick: () => reject(row) }, { default: () => '驳回' }),
        ],
      })
    },
  },
]

async function loadRecords() {
  loading.value = true
  try {
    const res = await api.wikiAdminMessages({ page: recordPage.value, page_size: pageSize, keyword: keyword.value || undefined })
    records.value = res?.data || []
    recordTotal.value = res?.total || 0
  } finally {
    loading.value = false
  }
}

async function loadFeedback() {
  feedbackLoading.value = true
  try {
    const res = await api.wikiLearningList({ page: feedbackPage.value, page_size: pageSize, status: 'pending' })
    feedback.value = res?.data || []
    feedbackTotal.value = res?.total || 0
  } finally {
    feedbackLoading.value = false
  }
}

function openLearning(row) {
  editing.value = row
  learningContent.value = row.proposed_content || `# ${row.question}\n\n`
}

async function approve() {
  if (!editing.value) return
  await api.wikiLearningApprove({ candidate_id: editing.value.id, content: learningContent.value })
  window.$message?.success('已学习到 Wiki')
  editing.value = null
  await loadFeedback()
}

async function reject(row) {
  await api.wikiLearningReject({ candidate_id: row.id })
  window.$message?.success('已驳回')
  await loadFeedback()
}

onMounted(() => {
  loadRecords()
  loadFeedback()
})
</script>

<template>
  <CommonPage>
    <template #action>
      <NSpace>
        <NInput v-model:value="keyword" placeholder="搜索问答记录" clearable @keyup.enter="loadRecords" />
        <NButton type="primary" @click="loadRecords">搜索</NButton>
      </NSpace>
    </template>

    <NTabs v-model:value="tab" type="line" animated>
      <NTabPane name="records" tab="问答记录">
        <NDataTable
          remote
          :loading="loading"
          :columns="recordColumns"
          :data="records"
          :pagination="{ page: recordPage, pageSize, itemCount: recordTotal, onUpdatePage: (v) => { recordPage = v; loadRecords() } }"
        />
      </NTabPane>
      <NTabPane name="feedback" tab="问题反馈">
        <NDataTable
          remote
          :loading="feedbackLoading"
          :columns="feedbackColumns"
          :data="feedback"
          :pagination="{ page: feedbackPage, pageSize, itemCount: feedbackTotal, onUpdatePage: (v) => { feedbackPage = v; loadFeedback() } }"
        />
      </NTabPane>
    </NTabs>

    <NModal :show="!!editing" preset="card" title="调整学习内容" style="width: min(760px, 92vw)" @update:show="(v) => { if (!v) editing = null }">
      <NInput v-model:value="learningContent" type="textarea" :autosize="{ minRows: 12, maxRows: 20 }" />
      <template #footer>
        <NSpace justify="end">
          <NButton @click="editing = null">取消</NButton>
          <NButton type="primary" @click="approve">学习入库</NButton>
        </NSpace>
      </template>
    </NModal>
  </CommonPage>
</template>
