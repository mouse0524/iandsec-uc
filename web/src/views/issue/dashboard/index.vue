<script setup>
import { computed, onMounted, ref } from 'vue'
import { NButton } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

defineOptions({ name: '工单数据展板' })

const loading = ref(false)
const dashboard = ref({
  total: 0,
  status_counts: [],
  role_counts: [],
  top_projects: [],
  created_trend: { daily: [], weekly: [] },
  closed_trend: { daily: [], weekly: [] },
  stale_issues: [],
})

const dashboardTotal = computed(() => Number(dashboard.value.total || 0))
const dailyCreated = computed(() => dashboard.value.created_trend?.daily || [])
const weeklyCreated = computed(() => dashboard.value.created_trend?.weekly || [])
const dailyClosed = computed(() => dashboard.value.closed_trend?.daily || [])
const weeklyClosed = computed(() => dashboard.value.closed_trend?.weekly || [])
const maxStatusCount = computed(() =>
  Math.max(1, ...(dashboard.value.status_counts || []).map((item) => Number(item.count || 0))),
)
const maxProjectCount = computed(() =>
  Math.max(1, ...(dashboard.value.top_projects || []).map((item) => Number(item.count || 0))),
)
const maxRoleCount = computed(() =>
  Math.max(1, ...(dashboard.value.role_counts || []).map((item) => Number(item.count || 0))),
)
const maxDailyCreated = computed(() => maxTrendCount(dailyCreated.value))
const maxWeeklyCreated = computed(() => maxTrendCount(weeklyCreated.value))
const maxDailyClosed = computed(() => maxTrendCount(dailyClosed.value))
const maxWeeklyClosed = computed(() => maxTrendCount(weeklyClosed.value))

function maxTrendCount(items) {
  return Math.max(1, ...(items || []).map((item) => Number(item.count || 0)))
}

function trendPoint(item, index, items, maxCount) {
  const count = Number(item.count || 0)
  const x = items.length > 1 ? (index / (items.length - 1)) * 100 : 50
  const y = 92 - (count / maxCount) * 76
  return { x, y, count }
}

function trendPoints(items, maxCount) {
  return (items || []).map((item, index) => trendPoint(item, index, items, maxCount))
}

function trendPath(items, maxCount) {
  return trendPoints(items, maxCount)
    .map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`)
    .join(' ')
}

function trendLabel(item) {
  return item.date?.slice(5) || item.week || ''
}

async function loadDashboard() {
  loading.value = true
  try {
    const res = await api.getIssueDashboard()
    dashboard.value = res?.data || dashboard.value
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<template>
  <CommonPage title="数据展板" :show-header="false" show-footer>
    <div class="issue-dashboard-page">
      <section class="dashboard-shell">
        <div class="dashboard-head">
          <div>
            <span class="dashboard-kicker">工单中心</span>
            <strong>当前可见工单 {{ dashboardTotal }} 个</strong>
          </div>
          <NButton secondary :loading="loading" @click="loadDashboard">
            <template #icon>
              <TheIcon icon="mdi-content-save-cog-outline" :size="16" />
            </template>
            刷新
          </NButton>
        </div>
        <div class="dashboard-grid">
          <div class="dashboard-panel">
            <div class="panel-title">问题状态</div>
            <div v-if="dashboard.status_counts?.length" class="metric-list">
              <div
                v-for="item in dashboard.status_counts"
                :key="item.status_id || item.name"
                class="metric-row"
              >
                <div class="metric-line">
                  <span>{{ item.name }}</span>
                  <strong>{{ item.count }}</strong>
                </div>
                <div class="metric-bar">
                  <i :style="{ width: `${(Number(item.count || 0) / maxStatusCount) * 100}%` }" />
                </div>
              </div>
            </div>
            <div v-else class="dashboard-empty">暂无状态数据</div>
          </div>
          <div class="dashboard-panel">
            <div class="panel-title">项目问题 Top10</div>
            <div v-if="dashboard.top_projects?.length" class="metric-list">
              <div
                v-for="(item, index) in dashboard.top_projects"
                :key="item.project_name"
                class="metric-row"
              >
                <div class="metric-line">
                  <span :title="item.project_name">{{ index + 1 }}. {{ item.project_name }}</span>
                  <strong>{{ item.count }}</strong>
                </div>
                <div class="metric-bar project">
                  <i :style="{ width: `${(Number(item.count || 0) / maxProjectCount) * 100}%` }" />
                </div>
              </div>
            </div>
            <div v-else class="dashboard-empty">暂无项目数据</div>
          </div>
          <div class="dashboard-panel">
            <div class="panel-title">打开问题按角色</div>
            <div v-if="dashboard.role_counts?.length" class="metric-list">
              <div v-for="item in dashboard.role_counts" :key="item.role_name" class="metric-row">
                <div class="metric-line">
                  <span>{{ item.role_name }}</span>
                  <strong>{{ item.count }}</strong>
                </div>
                <div class="metric-bar role">
                  <i :style="{ width: `${(Number(item.count || 0) / maxRoleCount) * 100}%` }" />
                </div>
              </div>
            </div>
            <div v-else class="dashboard-empty">暂无打开问题角色数据</div>
          </div>
          <div class="dashboard-panel">
            <div class="panel-title">新增趋势</div>
            <div class="trend-grid">
              <div class="trend-chart">
                <div class="trend-title">每日</div>
                <svg viewBox="0 0 100 112" preserveAspectRatio="none">
                  <polyline class="chart-grid" points="0,92 100,92" />
                  <path class="chart-line" :d="trendPath(dailyCreated, maxDailyCreated)" />
                  <circle
                    v-for="point in trendPoints(dailyCreated, maxDailyCreated)"
                    :key="`created-day-${point.x}`"
                    class="chart-point"
                    :cx="point.x"
                    :cy="point.y"
                    r="1.8"
                  />
                </svg>
                <div class="chart-labels">
                  <span v-for="item in dailyCreated" :key="item.date">{{ trendLabel(item) }}</span>
                </div>
                <div class="chart-values">
                  <span v-for="item in dailyCreated" :key="`v-${item.date}`">{{ item.count }}</span>
                </div>
              </div>
              <div class="trend-chart">
                <div class="trend-title">每周</div>
                <svg viewBox="0 0 100 112" preserveAspectRatio="none">
                  <polyline class="chart-grid" points="0,92 100,92" />
                  <path class="chart-line" :d="trendPath(weeklyCreated, maxWeeklyCreated)" />
                  <circle
                    v-for="point in trendPoints(weeklyCreated, maxWeeklyCreated)"
                    :key="`created-week-${point.x}`"
                    class="chart-point"
                    :cx="point.x"
                    :cy="point.y"
                    r="1.8"
                  />
                </svg>
                <div class="chart-labels">
                  <span v-for="item in weeklyCreated" :key="item.week">{{ trendLabel(item) }}</span>
                </div>
                <div class="chart-values">
                  <span v-for="item in weeklyCreated" :key="`v-${item.week}`">{{ item.count }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="dashboard-panel">
            <div class="panel-title">关闭趋势</div>
            <div class="trend-grid">
              <div class="trend-chart is-closed">
                <div class="trend-title">每日</div>
                <svg viewBox="0 0 100 112" preserveAspectRatio="none">
                  <polyline class="chart-grid" points="0,92 100,92" />
                  <path class="chart-line" :d="trendPath(dailyClosed, maxDailyClosed)" />
                  <circle
                    v-for="point in trendPoints(dailyClosed, maxDailyClosed)"
                    :key="`closed-day-${point.x}`"
                    class="chart-point"
                    :cx="point.x"
                    :cy="point.y"
                    r="1.8"
                  />
                </svg>
                <div class="chart-labels">
                  <span v-for="item in dailyClosed" :key="item.date">{{ trendLabel(item) }}</span>
                </div>
                <div class="chart-values">
                  <span v-for="item in dailyClosed" :key="`v-${item.date}`">{{ item.count }}</span>
                </div>
              </div>
              <div class="trend-chart is-closed">
                <div class="trend-title">每周</div>
                <svg viewBox="0 0 100 112" preserveAspectRatio="none">
                  <polyline class="chart-grid" points="0,92 100,92" />
                  <path class="chart-line" :d="trendPath(weeklyClosed, maxWeeklyClosed)" />
                  <circle
                    v-for="point in trendPoints(weeklyClosed, maxWeeklyClosed)"
                    :key="`closed-week-${point.x}`"
                    class="chart-point"
                    :cx="point.x"
                    :cy="point.y"
                    r="1.8"
                  />
                </svg>
                <div class="chart-labels">
                  <span v-for="item in weeklyClosed" :key="item.week">{{ trendLabel(item) }}</span>
                </div>
                <div class="chart-values">
                  <span v-for="item in weeklyClosed" :key="`v-${item.week}`">{{ item.count }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="dashboard-panel wide">
            <div class="panel-title">长期未更新问题</div>
            <div v-if="dashboard.stale_issues?.length" class="stale-list">
              <div v-for="item in dashboard.stale_issues" :key="item.id" class="stale-row">
                <div>
                  <strong>#{{ item.id }} {{ item.title }}</strong>
                  <span>{{ item.project_name }} · 更新于 {{ item.updated_at }}</span>
                </div>
                <em>{{ item.days }} 天</em>
              </div>
            </div>
            <div v-else class="dashboard-empty">暂无 7 天未更新的未关闭问题</div>
          </div>
        </div>
      </section>
    </div>
  </CommonPage>
</template>

<style scoped>
.issue-dashboard-page {
  --issue-accent: #0f766e;
  --issue-border: #e5e7eb;
  --issue-muted: #64748b;
  --issue-ink: #111827;
}

.dashboard-shell {
  padding: 16px;
  border: 1px solid var(--issue-border);
  border-radius: 8px;
  background: linear-gradient(180deg, #f8fafc 0%, #fff 96px);
}

.dashboard-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.dashboard-head strong {
  display: block;
  color: var(--issue-ink);
  font-size: 18px;
}

.dashboard-kicker {
  display: block;
  margin-bottom: 3px;
  color: var(--issue-muted);
  font-size: 12px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
  gap: 14px;
}

.dashboard-panel {
  min-width: 0;
  padding: 14px;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: #fff;
}

.panel-title {
  margin-bottom: 12px;
  color: var(--issue-ink);
  font-size: 14px;
  font-weight: 700;
}

.metric-list {
  display: grid;
  gap: 10px;
}

.metric-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #334155;
  font-size: 13px;
}

.metric-line span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-line strong {
  color: var(--issue-ink);
  font-size: 13px;
}

.metric-bar {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.metric-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #0f766e;
}

.metric-bar.project i {
  background: #2563eb;
}

.metric-bar.role i {
  background: #d97706;
}

.dashboard-panel.wide {
  grid-column: 1 / -1;
}

.trend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.trend-title {
  margin-bottom: 8px;
  color: var(--issue-muted);
  font-size: 12px;
  font-weight: 700;
}

.trend-chart {
  min-width: 0;
}

.trend-chart svg {
  display: block;
  width: 100%;
  height: 150px;
  overflow: visible;
}

.chart-grid {
  fill: none;
  stroke: #e2e8f0;
  stroke-width: 0.8;
}

.chart-line {
  fill: none;
  stroke: #0f766e;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.4;
  vector-effect: non-scaling-stroke;
}

.chart-point {
  fill: #fff;
  stroke: #0f766e;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}

.trend-chart.is-closed .chart-line {
  stroke: #16a34a;
}

.trend-chart.is-closed .chart-point {
  stroke: #16a34a;
}

.chart-labels,
.chart-values {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
  color: var(--issue-muted);
  font-size: 11px;
  text-align: center;
}

.chart-values {
  margin-top: 4px;
  color: var(--issue-ink);
  font-weight: 700;
}

.chart-labels span,
.chart-values span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stale-list {
  display: grid;
  gap: 10px;
}

.stale-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 10px 12px;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: #f8fafc;
}

.stale-row div {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.stale-row strong,
.stale-row span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stale-row strong {
  color: var(--issue-ink);
  font-size: 13px;
}

.stale-row span {
  color: var(--issue-muted);
  font-size: 12px;
}

.stale-row em {
  flex: 0 0 auto;
  color: #dc2626;
  font-size: 13px;
  font-style: normal;
  font-weight: 700;
}

.dashboard-empty {
  padding: 28px 0;
  color: var(--issue-muted);
  font-size: 13px;
  text-align: center;
}

@media (max-width: 900px) {
  .dashboard-grid,
  .trend-grid {
    grid-template-columns: 1fr;
  }
}
</style>
