<template>
  <AppPage :show-footer="false">
    <div flex-1>
      <n-card rounded-10>
        <div flex items-center justify-between>
          <div flex items-center>
            <div>
              <p text-20 font-semibold>
                {{ $t('views.workbench.text_hello', { username: userStore.name }) }}
              </p>
              <p mt-5 text-14 op-60>{{ $t('views.workbench.text_welcome') }}</p>
            </div>
          </div>
          <n-space :size="12" :wrap="false">
            <n-statistic v-for="item in headerStats" :key="item.id" v-bind="item">
              <template #suffix>
                <n-button text type="primary" size="small" @click="goByMetric(item.metric)">查看</n-button>
              </template>
            </n-statistic>
          </n-space>
        </div>
      </n-card>

      <n-card title="全局统计看板" size="small" :segmented="true" mt-15 rounded-10>
        <template #header-extra>
          <n-button text type="primary" :loading="statsLoading" @click="loadStats">刷新</n-button>
        </template>
        <div class="stats-grid">
          <n-card v-for="item in panelStats" :key="item.id" size="small" class="stat-item" :bordered="true" @click="goByMetric(item.metric)">
            <n-statistic :label="item.label" :value="item.value" />
            <div class="stat-tip">点击查看详情</div>
          </n-card>
        </div>
      </n-card>
    </div>
  </AppPage>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store'
import api from '@/api'

const userStore = useUserStore()
const router = useRouter()
const statsLoading = ref(false)
const stats = ref({
  ticket_total: 0,
  ticket_pending_review: 0,
  ticket_tech_processing: 0,
  ticket_today_created: 0,
  ticket_today_done: 0,
  register_pending: 0,
  user_total: 0,
  auditlog_today: 0,
})

const headerStats = computed(() => [
  { id: 0, label: '工单总量', value: stats.value.ticket_total, metric: 'ticket_total' },
  { id: 1, label: '待审核工单', value: stats.value.ticket_pending_review, metric: 'ticket_pending_review' },
  { id: 2, label: '待审核注册', value: stats.value.register_pending, metric: 'register_pending' },
])

const panelStats = computed(() => [
  { id: 0, label: '工单总量', value: stats.value.ticket_total, metric: 'ticket_total' },
  { id: 1, label: '待审核工单', value: stats.value.ticket_pending_review, metric: 'ticket_pending_review' },
  { id: 2, label: '技术处理中', value: stats.value.ticket_tech_processing, metric: 'ticket_tech_processing' },
  { id: 3, label: '今日新增工单', value: stats.value.ticket_today_created, metric: 'ticket_today_created' },
  { id: 4, label: '今日完成工单', value: stats.value.ticket_today_done, metric: 'ticket_today_done' },
  { id: 5, label: '待审核注册', value: stats.value.register_pending, metric: 'register_pending' },
  { id: 6, label: '用户总数', value: stats.value.user_total, metric: 'user_total' },
  { id: 7, label: '今日操作日志', value: stats.value.auditlog_today, metric: 'auditlog_today' },
])

onMounted(() => {
  loadStats()
})

async function loadStats() {
  try {
    statsLoading.value = true
    const res = await api.getWorkbenchStats()
    stats.value = { ...stats.value, ...(res.data || {}) }
  } catch (error) {
    // ignore stats load errors
  } finally {
    statsLoading.value = false
  }
}

function goByMetric(metric) {
  if (metric === 'register_pending') {
    router.push({ path: '/partner/review', query: { status: 'pending' } })
    return
  }
  if (metric === 'auditlog_today') {
    router.push({ path: '/system/auditlog' })
    return
  }

  const statusMap = {
    ticket_pending_review: 'pending_review',
    ticket_tech_processing: 'tech_processing',
    ticket_today_done: 'done',
  }

  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const end = new Date(start)
  end.setDate(end.getDate() + 1)

  const toIso = (d) => d.toISOString()

  const query = {}
  if (statusMap[metric]) {
    query.status = statusMap[metric]
  }
  if (metric === 'ticket_today_created') {
    query.created_start = toIso(start)
    query.created_end = toIso(end)
  }
  if (metric === 'ticket_today_done') {
    query.finished_start = toIso(start)
    query.finished_end = toIso(end)
  }
  router.push({ path: '/ticket/my', query })
}
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-item {
  border-radius: 10px;
  cursor: pointer;
}

.stat-tip {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.6;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 700px) {
  .stats-grid {
    grid-template-columns: repeat(1, minmax(0, 1fr));
  }
}
</style>
