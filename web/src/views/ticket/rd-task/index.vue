<script setup>
import { h, ref } from 'vue'
import { NButton, NCard, NInput, NModal, NSelect, NSpace, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import api from '@/api'
import {
  rdTaskStatusOptions,
  rdTaskStatusTextMap,
  rdTaskStatusTypeMap,
  rdTaskTypeOptions,
  rdTaskTypeTextMap,
} from '@/views/ticket/components/ticket-meta'

defineOptions({ name: '产研任务' })

const $table = ref(null)
const queryItems = ref({})
const detailVisible = ref(false)
const detailLoading = ref(false)
const currentTask = ref({})
const transitionVisible = ref(false)
const pendingTask = ref(null)
const pendingAction = ref('')
const transitionComment = ref('')

const actionOptions = [
  { label: '产品确认', key: 'product_approve' },
  { label: '产品驳回', key: 'product_reject' },
  { label: '研发接单', key: 'dev_start' },
  { label: '提交测试', key: 'submit_test' },
  { label: '测试通过', key: 'test_pass' },
  { label: '测试退回', key: 'test_reject' },
  { label: '标记待发布', key: 'mark_pending_release' },
  { label: '标记已完成', key: 'complete' },
  { label: '标记已驳回', key: 'reject' },
]

function openTransition(row, action) {
  pendingTask.value = row
  pendingAction.value = action
  transitionComment.value = ''
  transitionVisible.value = true
}

async function submitTransition() {
  if (!pendingTask.value || !pendingAction.value) return
  const res = await api.transitionRdTask({
    task_id: pendingTask.value.id,
    action: pendingAction.value,
    comment: transitionComment.value,
  })
  const ticketIds = res?.data?.followup_ticket_ids || []
  $message.success(ticketIds.length ? `任务已流转，请跟进关联工单：${ticketIds.join('、')}` : '任务已流转')
  transitionVisible.value = false
  pendingTask.value = null
  pendingAction.value = ''
  $table.value?.handleSearch()
}

async function openDetail(row) {
  currentTask.value = row
  detailLoading.value = true
  detailVisible.value = true
  try {
    const res = await api.getRdTaskById({ task_id: row.id })
    currentTask.value = res?.data || row
  } finally {
    detailLoading.value = false
  }
}

const columns = [
  { title: '任务编号', key: 'task_no', align: 'center', width: 170 },
  {
    title: '标题',
    key: 'title',
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return h(
        'a',
        {
          class: 'task-title-link',
          href: 'javascript:void(0)',
          onClick: () => openDetail(row),
        },
        row.title || '-'
      )
    },
  },
  {
    title: '类型',
    key: 'task_type',
    align: 'center',
    render(row) {
      return rdTaskTypeTextMap[row.task_type] || row.task_type || '-'
    },
  },
  {
    title: '状态',
    key: 'status',
    align: 'center',
    render(row) {
      return h(
        NTag,
        { type: rdTaskStatusTypeMap[row.status] || 'default' },
        { default: () => rdTaskStatusTextMap[row.status] || row.status || '-' }
      )
    },
  },
  { title: '优先级', key: 'priority', align: 'center' },
  { title: '产品', key: 'product_owner_name', align: 'center', render: (row) => row.product_owner_name || '-' },
  { title: '研发', key: 'dev_owner_name', align: 'center', render: (row) => row.dev_owner_name || '-' },
  { title: '测试', key: 'test_owner_name', align: 'center', render: (row) => row.test_owner_name || '-' },
  { title: '版本', key: 'planned_version', align: 'center', render: (row) => row.planned_version || '-' },
  { title: '关联工单', key: 'ticket_count', align: 'center', render: (row) => row.ticket_count || 0 },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 180,
    render(row) {
      return h('div', { class: 'action-buttons' }, [
        h(NButton, { size: 'small', type: 'info', onClick: () => openDetail(row) }, { default: () => '详情' }),
        h(
          NSelect,
          {
            size: 'small',
            placeholder: '流转',
            options: actionOptions.map((item) => ({ label: item.label, value: item.key })),
            onUpdateValue: (value) => openTransition(row, value),
            style: 'width: 110px',
          },
        ),
      ])
    },
  },
]
</script>

<template>
  <CommonPage title="产研任务" show-footer>
    <div class="rd-task-page">
      <NCard size="small" class="table-shell">
        <CrudTable ref="$table" v-model:query-items="queryItems" :columns="columns" :get-data="api.getRdTaskList">
          <template #queryBar>
            <QueryBarItem label="关键词" :label-width="56">
              <NInput v-model:value="queryItems.keyword" clearable placeholder="任务编号/标题" @keypress.enter="$table?.handleSearch()" />
            </QueryBarItem>
            <QueryBarItem label="类型" :label-width="40">
              <NSelect v-model:value="queryItems.task_type" :options="rdTaskTypeOptions" clearable placeholder="选择类型" style="width: 180px" />
            </QueryBarItem>
            <QueryBarItem label="状态" :label-width="40">
              <NSelect v-model:value="queryItems.status" :options="rdTaskStatusOptions" clearable placeholder="选择状态" style="width: 180px" />
            </QueryBarItem>
          </template>
        </CrudTable>
      </NCard>

      <NModal v-model:show="detailVisible" preset="card" style="width: min(92vw, 860px)" title="产研任务详情">
        <div v-if="detailLoading" class="empty-text">加载中...</div>
        <div v-else class="task-detail">
          <div class="detail-header">
            <div>
              <span>{{ currentTask.task_no }}</span>
              <strong>{{ currentTask.title }}</strong>
            </div>
            <NTag :type="rdTaskStatusTypeMap[currentTask.status] || 'default'">
              {{ rdTaskStatusTextMap[currentTask.status] || currentTask.status || '-' }}
            </NTag>
          </div>
          <div class="detail-grid">
            <div><span>类型</span><strong>{{ rdTaskTypeTextMap[currentTask.task_type] || currentTask.task_type || '-' }}</strong></div>
            <div><span>优先级</span><strong>{{ currentTask.priority || '-' }}</strong></div>
            <div><span>计划版本</span><strong>{{ currentTask.planned_version || '-' }}</strong></div>
            <div><span>产品负责人</span><strong>{{ currentTask.product_owner_name || '-' }}</strong></div>
            <div><span>研发负责人</span><strong>{{ currentTask.dev_owner_name || '-' }}</strong></div>
            <div><span>测试负责人</span><strong>{{ currentTask.test_owner_name || '-' }}</strong></div>
          </div>
          <div class="detail-block">
            <span>描述</span>
            <p>{{ currentTask.description || '-' }}</p>
          </div>
          <div class="detail-block">
            <span>处理结论</span>
            <p>{{ currentTask.result_note || '-' }}</p>
          </div>
          <div class="detail-block">
            <span>关联工单</span>
            <NSpace v-if="currentTask.ticket_links?.length">
              <NTag v-for="item in currentTask.ticket_links" :key="item.ticket_id" type="info">#{{ item.ticket_id }}</NTag>
            </NSpace>
            <p v-else>-</p>
          </div>
          <div class="detail-block">
            <span>流转日志</span>
            <div v-if="currentTask.logs?.length" class="log-list">
              <div v-for="item in currentTask.logs" :key="item.id" class="log-item">
                <strong>{{ item.action }}</strong>
                <p>{{ rdTaskStatusTextMap[item.from_status] || item.from_status || '-' }} -> {{ rdTaskStatusTextMap[item.to_status] || item.to_status || '-' }}</p>
                <small>{{ item.comment || '-' }}</small>
              </div>
            </div>
            <p v-else>-</p>
          </div>
        </div>
      </NModal>

      <NModal v-model:show="transitionVisible" preset="card" style="width: 520px" title="流转产研任务">
        <NInput
          v-model:value="transitionComment"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 7 }"
          placeholder="请输入流转备注"
        />
        <div class="modal-actions">
          <NButton @click="transitionVisible = false">取消</NButton>
          <NButton type="primary" @click="submitTransition">确认流转</NButton>
        </div>
      </NModal>
    </div>
  </CommonPage>
</template>

<style scoped>
.rd-task-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.table-shell {
  border-radius: 8px;
}

.task-title-link {
  color: #2563eb;
  font-weight: 600;
  text-decoration: none;
}

.task-title-link:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.detail-header span,
.detail-block span,
.detail-grid span {
  display: block;
  color: #6b7280;
  font-size: 12px;
}

.detail-header strong {
  display: block;
  margin-top: 4px;
  color: #111827;
  font-size: 20px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.detail-grid > div,
.detail-block {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.detail-grid strong,
.detail-block p {
  margin: 6px 0 0;
  color: #111827;
}

.detail-block {
  margin-top: 12px;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.log-item {
  padding: 10px;
  border-radius: 8px;
  background: #f9fafb;
}

.log-item p,
.log-item small {
  display: block;
  margin: 4px 0 0;
  color: #6b7280;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

.empty-text {
  color: #6b7280;
}
</style>
