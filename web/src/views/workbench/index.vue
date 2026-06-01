<template>
  <AppPage :show-footer="false">
    <div class="security-workbench">
      <section class="hero-panel">
        <div>
          <div class="eyebrow">AI驱动数据安全 · 运营视图</div>
          <h1>{{ $t('views.workbench.text_hello', { username: userStore.name }) }}</h1>
          <p>{{ $t('views.workbench.text_welcome') }}</p>
        </div>
        <div class="hero-actions">
          <div class="refresh-meta">最近上报：{{ latestReportText }}</div>
          <NButton type="primary" :loading="statsLoading" @click="loadStats">刷新数据</NButton>
        </div>
      </section>

      <section class="metric-grid">
        <button
          v-for="item in keyMetrics"
          :key="item.key"
          class="metric-card"
          type="button"
          @click="goByMetric(item.metric)"
        >
          <span class="metric-label">{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.hint }}</small>
        </button>
      </section>

      <section class="dashboard-grid">
        <div class="panel panel-wide">
          <div class="panel-head">
            <div>
              <h2>工单处理态势</h2>
              <p>从审核、处理中到完成闭环的当前分布</p>
            </div>
            <NButton text type="primary" @click="goByMetric('ticket_total')">查看工单</NButton>
          </div>
          <div class="status-bars">
            <div v-for="item in ticketBars" :key="item.key" class="status-row">
              <div class="status-title">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${item.percent}%`, background: item.color }"></div>
              </div>
            </div>
          </div>
          <div class="mini-grid">
            <div>
              <span>今日新增</span>
              <strong>{{ stats.ticket_today_created }}</strong>
            </div>
            <div>
              <span>今日完成</span>
              <strong>{{ stats.ticket_today_done }}</strong>
            </div>
            <div>
              <span>今日完成率</span>
              <strong>{{ stats.ticket_today_completion_rate }}%</strong>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head compact">
            <div>
              <h2>安全提醒</h2>
              <p>需要优先处理的异常与风险</p>
            </div>
          </div>
          <div class="alert-list">
            <button v-for="item in alertItems" :key="item.key" type="button" @click="goByMetric(item.metric)">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </button>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head compact">
            <div>
              <h2>AI知识库</h2>
              <p>文档解析、阅读索引与对话使用情况</p>
            </div>
          </div>
          <div class="knowledge-score">
            <div>
              <span>文档健康度</span>
              <strong>{{ stats.document_health_rate }}%</strong>
            </div>
            <div class="ring" :style="{ '--value': stats.document_health_rate }"></div>
          </div>
          <div class="info-list">
            <button v-for="item in knowledgeItems" :key="item.key" type="button" @click="goByMetric(item.metric)">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </button>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head compact">
            <div>
              <h2>终端授权</h2>
              <p>客户上报、授权与维保覆盖</p>
            </div>
          </div>
          <div class="terminal-total">
            <span>终端总数</span>
            <strong>{{ stats.terminal_total }}</strong>
          </div>
          <div class="info-list">
            <button v-for="item in terminalItems" :key="item.key" type="button" @click="goByMetric(item.metric)">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </button>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head compact">
            <div>
              <h2>运营风险</h2>
              <p>待审核、临期与失败事项汇总</p>
            </div>
          </div>
          <div class="risk-summary">
            <span>待处理风险</span>
            <strong>{{ riskTotal }}</strong>
          </div>
          <div class="risk-list">
            <button v-for="item in riskItems" :key="item.key" type="button" @click="goByMetric(item.metric)">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </button>
          </div>
        </div>

        <div class="panel panel-full">
          <div class="panel-head">
            <div>
              <h2>审计与共享</h2>
              <p>系统行为留痕、归档与外发共享状态</p>
            </div>
            <NButton text type="primary" @click="goByMetric('auditlog_today')">查看审计</NButton>
          </div>
          <div class="audit-grid">
            <button v-for="item in auditItems" :key="item.key" type="button" @click="goByMetric(item.metric)">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <small>{{ item.hint }}</small>
            </button>
          </div>
        </div>
      </section>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton } from 'naive-ui'
import { useUserStore } from '@/store'
import api from '@/api'

const userStore = useUserStore()
const router = useRouter()
const statsLoading = ref(false)
const stats = ref({
  ticket_total: 0,
  ticket_active: 0,
  ticket_pending_review: 0,
  ticket_tech_processing: 0,
  ticket_done: 0,
  ticket_rejected: 0,
  ticket_today_created: 0,
  ticket_today_done: 0,
  ticket_today_completion_rate: 0,
  register_pending: 0,
  register_approved: 0,
  register_rejected: 0,
  user_total: 0,
  auditlog_today: 0,
  auditlog_failed_today: 0,
  auditlog_archived: 0,
  document_total: 0,
  document_completed: 0,
  document_processing: 0,
  document_failed: 0,
  document_today: 0,
  document_health_rate: 100,
  chunk_total: 0,
  conversation_today: 0,
  message_today: 0,
  share_active: 0,
  share_expired: 0,
  terminal_company_count: 0,
  terminal_total: 0,
  terminal_auth_expiring: 0,
  terminal_maintain_expiring: 0,
  terminal_latest_reported_at: null,
})

const latestReportText = computed(() => {
  if (!stats.value.terminal_latest_reported_at) return '暂无终端上报'
  return stats.value.terminal_latest_reported_at.replace('T', ' ').slice(0, 19)
})

const keyMetrics = computed(() => [
  { key: 'active', label: '待处理工单', value: stats.value.ticket_active, hint: '审核与技术处理中', metric: 'ticket_active' },
  { key: 'documents', label: '知识库文档', value: stats.value.document_total, hint: `${stats.value.document_failed} 个失败`, metric: 'document_total' },
  { key: 'terminal', label: '受管终端', value: stats.value.terminal_total, hint: `${stats.value.terminal_company_count} 家公司`, metric: 'terminal_total' },
  { key: 'audit', label: '今日审计', value: stats.value.auditlog_today, hint: `${stats.value.auditlog_failed_today} 个失败请求`, metric: 'auditlog_today' },
])

const ticketBars = computed(() => {
  const total = Math.max(1, stats.value.ticket_total)
  return [
    { key: 'pending', label: '待客服审核', value: stats.value.ticket_pending_review, color: '#eab308' },
    { key: 'processing', label: '技术处理中', value: stats.value.ticket_tech_processing, color: '#2563eb' },
    { key: 'done', label: '已完成', value: stats.value.ticket_done, color: '#16a34a' },
    { key: 'rejected', label: '已驳回', value: stats.value.ticket_rejected, color: '#ef4444' },
  ].map((item) => ({ ...item, percent: Math.min(100, Math.round((item.value * 100) / total)) }))
})

const alertItems = computed(() => [
  { key: 'register', label: '注册待审核', value: stats.value.register_pending, metric: 'register_pending' },
  { key: 'document', label: '文档处理失败', value: stats.value.document_failed, metric: 'document_failed' },
  { key: 'auth', label: '授权30天内到期', value: stats.value.terminal_auth_expiring, metric: 'terminal_total' },
  { key: 'maintain', label: '维保30天内到期', value: stats.value.terminal_maintain_expiring, metric: 'terminal_total' },
  { key: 'audit', label: '今日失败请求', value: stats.value.auditlog_failed_today, metric: 'auditlog_today' },
])

const knowledgeItems = computed(() => [
  { key: 'processing', label: '处理中', value: stats.value.document_processing, metric: 'document_total' },
  { key: 'chunks', label: '文档分片', value: stats.value.chunk_total, metric: 'document_total' },
  { key: 'conversation', label: '今日会话', value: stats.value.conversation_today, metric: 'conversation_today' },
])

const terminalItems = computed(() => [
  { key: 'company', label: '上报公司', value: stats.value.terminal_company_count, metric: 'terminal_total' },
  { key: 'auth', label: '授权临期', value: stats.value.terminal_auth_expiring, metric: 'terminal_total' },
  { key: 'maintain', label: '维保临期', value: stats.value.terminal_maintain_expiring, metric: 'terminal_total' },
])

const riskItems = computed(() => [
  { key: 'register', label: '注册待审', value: stats.value.register_pending, metric: 'register_pending' },
  { key: 'documents', label: '文档失败', value: stats.value.document_failed, metric: 'document_failed' },
  { key: 'terminal', label: '授权/维保临期', value: stats.value.terminal_auth_expiring + stats.value.terminal_maintain_expiring, metric: 'terminal_total' },
  { key: 'audit', label: '失败请求', value: stats.value.auditlog_failed_today, metric: 'auditlog_today' },
])

const riskTotal = computed(() => riskItems.value.reduce((total, item) => total + Number(item.value || 0), 0))

const auditItems = computed(() => [
  { key: 'today', label: '今日请求', value: stats.value.auditlog_today, hint: '审计日志', metric: 'auditlog_today' },
  { key: 'failed', label: '失败请求', value: stats.value.auditlog_failed_today, hint: 'HTTP 4xx/5xx', metric: 'auditlog_today' },
  { key: 'archive', label: '已归档日志', value: stats.value.auditlog_archived, hint: '历史留存', metric: 'auditlog_today' },
  { key: 'share_active', label: '有效分享', value: stats.value.share_active, hint: 'WebDAV外发', metric: 'share_active' },
  { key: 'share_expired', label: '失效分享', value: stats.value.share_expired, hint: '过期或停用', metric: 'share_active' },
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

function todayRangeQuery(prefix) {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const end = new Date(start)
  end.setDate(end.getDate() + 1)
  return {
    [`${prefix}_start`]: start.toISOString(),
    [`${prefix}_end`]: end.toISOString(),
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
  if (metric === 'document_total' || metric === 'document_failed') {
    router.push({ path: '/skill-know/documents', query: metric === 'document_failed' ? { status: 'failed' } : {} })
    return
  }
  if (metric === 'conversation_today') {
    router.push({ path: '/skill-know/chat' })
    return
  }
  if (metric === 'terminal_total') {
    router.push({ path: '/terminal/auth' })
    return
  }
  if (metric === 'share_active') {
    router.push({ path: '/system/webdav-share' })
    return
  }

  const statusMap = {
    ticket_active: '',
    ticket_pending_review: 'pending_review',
    ticket_tech_processing: 'tech_processing',
    ticket_done: 'done',
    ticket_today_done: 'done',
  }
  const query = {}
  if (statusMap[metric]) query.status = statusMap[metric]
  if (metric === 'ticket_today_created') Object.assign(query, todayRangeQuery('created'))
  if (metric === 'ticket_today_done') Object.assign(query, todayRangeQuery('finished'))
  router.push({ path: '/ticket/my', query })
}
</script>

<style scoped>
.security-workbench {
  min-height: 100%;
  padding: 2px;
  color: #172033;
}

.hero-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 26px;
  border: 1px solid #dbe7f3;
  border-radius: 8px;
  background: linear-gradient(135deg, #f7fbff 0%, #eef7f4 100%);
}

.eyebrow {
  margin-bottom: 8px;
  color: #0f766e;
  font-size: 13px;
  font-weight: 700;
}

.hero-panel h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.hero-panel p {
  margin: 8px 0 0;
  color: #627085;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.refresh-meta {
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.metric-grid,
.dashboard-grid,
.mini-grid,
.audit-grid,
.risk-list {
  display: grid;
  gap: 14px;
}

.metric-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 14px;
}

.metric-card,
.audit-grid button,
.alert-list button,
.info-list button,
.risk-list button {
  border: 1px solid #e3ebf4;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.metric-card {
  min-height: 112px;
  padding: 18px;
  border-radius: 8px;
}

.metric-card span,
.metric-card small,
.terminal-total span,
.risk-summary span,
.mini-grid span,
.audit-grid small,
.alert-list span,
.info-list span,
.risk-list span,
.knowledge-score span {
  color: #64748b;
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin: 10px 0 8px;
  color: #0f172a;
  font-size: 30px;
  line-height: 1;
}

.dashboard-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 14px;
}

.panel {
  padding: 18px;
  border: 1px solid #e3ebf4;
  border-radius: 8px;
  background: #fff;
}

.panel-wide {
  grid-column: span 2;
}

.panel-full {
  grid-column: 1 / -1;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-head h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
}

.panel-head p {
  margin: 5px 0 0;
  color: #64748b;
  font-size: 13px;
}

.panel-head.compact {
  margin-bottom: 14px;
}

.status-bars {
  display: grid;
  gap: 13px;
}

.status-title {
  display: flex;
  justify-content: space-between;
  margin-bottom: 7px;
  font-size: 13px;
}

.bar-track {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #edf2f7;
}

.bar-fill {
  height: 100%;
  border-radius: inherit;
}

.mini-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 18px;
}

.mini-grid div,
.terminal-total,
.risk-summary {
  padding: 14px;
  border-radius: 8px;
  background: #f8fafc;
}

.mini-grid strong,
.terminal-total strong,
.risk-summary strong,
.knowledge-score strong {
  display: block;
  margin-top: 6px;
  font-size: 22px;
}

.alert-list,
.info-list,
.risk-list {
  display: grid;
  gap: 10px;
}

.alert-list button,
.info-list button,
.risk-list button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 42px;
  padding: 10px 12px;
  border-radius: 8px;
}

.alert-list strong,
.info-list strong,
.risk-list strong {
  font-size: 18px;
}

.knowledge-score {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  padding: 14px;
  border-radius: 8px;
  background: #f8fafc;
}

.ring {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: conic-gradient(#0f766e calc(var(--value) * 1%), #dce8ef 0);
  box-shadow: inset 0 0 0 10px #fff;
}

.terminal-total {
  margin-bottom: 14px;
}

.risk-summary {
  margin-bottom: 14px;
  border-left: 3px solid #ef4444;
}

.terminal-total strong {
  font-size: 34px;
}

.risk-summary strong {
  color: #b91c1c;
  font-size: 34px;
}

.audit-grid {
  grid-template-columns: repeat(5, minmax(132px, 1fr));
}

.audit-grid button {
  min-height: 94px;
  padding: 14px;
  border-radius: 8px;
}

.audit-grid strong {
  display: block;
  margin: 8px 0 6px;
  font-size: 24px;
}

@media (max-width: 1280px) {
  .metric-grid,
  .dashboard-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .panel-wide {
    grid-column: span 2;
  }

  .audit-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .hero-panel,
  .hero-actions {
    flex-direction: column;
    align-items: flex-start;
  }

  .metric-grid,
  .dashboard-grid,
  .mini-grid,
  .audit-grid,
  .risk-list {
    grid-template-columns: 1fr;
  }

  .panel-wide,
  .panel-full {
    grid-column: span 1;
  }
}
</style>
