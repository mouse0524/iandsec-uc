<script setup>
import { computed, onMounted, ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '系统监控' })

const loading = ref(false)
const clearing = ref(false)
const monitor = ref({})

const system = computed(() => monitor.value.system || {})
const mysql = computed(() => monitor.value.mysql || {})
const redis = computed(() => monitor.value.redis || {})
const skillKnowIndex = computed(() => monitor.value.skill_know_index || {})

onMounted(loadOverview)

function formatBytes(value) {
  const size = Number(value || 0)
  if (!size) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let current = size
  let index = 0
  while (current >= 1024 && index < units.length - 1) {
    current /= 1024
    index += 1
  }
  return `${current.toFixed(current >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}

function formatSeconds(value) {
  const seconds = Number(value || 0)
  if (!seconds) return '-'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days) return `${days}天 ${hours}小时`
  if (hours) return `${hours}小时 ${minutes}分钟`
  return `${minutes || 1}分钟`
}

function statusType(status) {
  return status === 'ok' ? 'success' : ['missing', 'degraded', 'needs_reindex'].includes(status) ? 'warning' : 'error'
}

async function loadOverview() {
  loading.value = true
  try {
    const res = await api.monitorOverview()
    monitor.value = res.data || {}
  } finally {
    loading.value = false
  }
}

async function clearRedis() {
  window.$dialog.warning({
    title: '清空 Redis 缓存',
    content: `将清理当前 Redis DB${redis.value.db ?? ''} 的业务缓存键，不会清理验证码、登录失败锁定等安全状态。确认继续？`,
    positiveText: '清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      clearing.value = true
      try {
        const res = await api.monitorClearRedis({ confirm: true })
        $message.success(`已清理 ${res.data?.cleared || 0} 个缓存键`)
        await loadOverview()
      } finally {
        clearing.value = false
      }
    },
  })
}
</script>

<template>
  <CommonPage title="系统监控" :show-header="false" show-footer>
    <NSpin :show="loading">
      <div class="monitor-page">
        <header class="monitor-head">
          <div>
            <div class="eyebrow">Operations</div>
            <h1>系统监控</h1>
            <p>集中查看系统资源、MySQL、Redis 与本地 WH 索引状态。</p>
          </div>
          <NSpace>
            <NButton secondary :loading="loading" @click="loadOverview">刷新</NButton>
            <NButton type="error" secondary :loading="clearing" :disabled="redis.status !== 'ok'" @click="clearRedis">清理 Redis 缓存</NButton>
          </NSpace>
        </header>

        <section class="metric-grid">
          <div class="metric-card">
            <span>CPU</span>
            <b>{{ system.cpu?.percent ?? '-' }}%</b>
            <NProgress type="line" :percentage="Number(system.cpu?.percent || 0)" :show-indicator="false" />
          </div>
          <div class="metric-card">
            <span>内存</span>
            <b>{{ system.memory?.percent ?? '-' }}%</b>
            <NProgress type="line" :percentage="Number(system.memory?.percent || 0)" :show-indicator="false" />
          </div>
          <div class="metric-card">
            <span>磁盘</span>
            <b>{{ system.disk?.percent ?? '-' }}%</b>
            <NProgress type="line" :percentage="Number(system.disk?.percent || 0)" :show-indicator="false" />
          </div>
          <div class="metric-card">
            <span>Redis 键数量</span>
            <b>{{ redis.db_size ?? '-' }}</b>
            <p>{{ redis.used_memory_human || formatBytes(redis.used_memory) }}</p>
          </div>
        </section>

        <section class="monitor-grid">
          <div class="monitor-panel">
            <div class="panel-head">
              <div>
                <h3>系统资源</h3>
                <p>{{ system.hostname || '-' }} · {{ system.platform || '-' }}</p>
              </div>
              <NTag :type="system.psutil_available ? 'success' : 'warning'" round>{{ system.psutil_available ? '完整采集' : '基础采集' }}</NTag>
            </div>
            <div class="info-list">
              <div><span>Python</span><b>{{ system.python || '-' }}</b></div>
              <div><span>进程 PID</span><b>{{ system.process?.pid || '-' }}</b></div>
              <div><span>进程内存</span><b>{{ formatBytes(system.process?.memory_rss) }}</b></div>
              <div><span>线程数</span><b>{{ system.process?.threads || '-' }}</b></div>
              <div><span>磁盘可用</span><b>{{ formatBytes(system.disk?.free) }} / {{ formatBytes(system.disk?.total) }}</b></div>
            </div>
          </div>

          <div class="monitor-panel">
            <div class="panel-head">
              <div>
                <h3>MySQL</h3>
                <p>{{ mysql.host }}:{{ mysql.port }} / {{ mysql.database }}</p>
              </div>
              <NTag :type="statusType(mysql.status)" round>{{ mysql.status || 'unknown' }}</NTag>
            </div>
            <div class="info-list">
              <div><span>版本</span><b>{{ mysql.version || '-' }}</b></div>
              <div><span>库大小</span><b>{{ formatBytes(mysql.database_size) }}</b></div>
              <div><span>连接数</span><b>{{ mysql.metrics?.Threads_connected ?? '-' }}</b></div>
              <div><span>运行线程</span><b>{{ mysql.metrics?.Threads_running ?? '-' }}</b></div>
              <div><span>慢查询</span><b>{{ mysql.metrics?.Slow_queries ?? '-' }}</b></div>
              <div v-if="mysql.error"><span>错误</span><b>{{ mysql.error }}</b></div>
            </div>
          </div>

          <div class="monitor-panel">
            <div class="panel-head">
              <div>
                <h3>Redis 缓存</h3>
                <p>{{ redis.host }}:{{ redis.port }} / DB {{ redis.db }}</p>
              </div>
              <NTag :type="statusType(redis.status)" round>{{ redis.status || 'unknown' }}</NTag>
            </div>
            <div class="info-list">
              <div><span>版本</span><b>{{ redis.version || '-' }}</b></div>
              <div><span>运行时间</span><b>{{ formatSeconds(redis.uptime_seconds) }}</b></div>
              <div><span>内存占用</span><b>{{ redis.used_memory_human || formatBytes(redis.used_memory) }}</b></div>
              <div><span>连接客户端</span><b>{{ redis.connected_clients ?? '-' }}</b></div>
              <div><span>命中率</span><b>{{ redis.hit_rate ?? 0 }}%</b></div>
              <div v-if="redis.error"><span>错误</span><b>{{ redis.error }}</b></div>
            </div>
          </div>

          <div class="monitor-panel">
            <div class="panel-head">
              <div>
                <h3>本地 WH 索引</h3>
                <p>{{ skillKnowIndex.index_dir || '-' }}</p>
              </div>
              <NTag :type="statusType(skillKnowIndex.status)" round>{{ skillKnowIndex.status || 'unknown' }}</NTag>
            </div>
            <div class="info-list">
              <div><span>后端</span><b>{{ skillKnowIndex.backend || 'whoosh' }}</b></div>
              <div><span>可用</span><b>{{ skillKnowIndex.available ? '是' : '否' }}</b></div>
              <div><span>索引存在</span><b>{{ skillKnowIndex.exists ? '是' : '否' }}</b></div>
              <div><span>文档数</span><b>{{ skillKnowIndex.document_count ?? '-' }}</b></div>
              <div><span>分段数</span><b>{{ skillKnowIndex.section_count ?? '-' }}</b></div>
              <div><span>索引条目</span><b>{{ skillKnowIndex.doc_count ?? 0 }} / {{ skillKnowIndex.doc_count_all ?? 0 }}</b></div>
              <div><span>领域词版本</span><b>{{ skillKnowIndex.domain_terms_version || '-' }}</b></div>
              <div v-if="skillKnowIndex.error"><span>错误</span><b>{{ skillKnowIndex.error }}</b></div>
            </div>
          </div>
        </section>
      </div>
    </NSpin>
  </CommonPage>
</template>

<style scoped>
.monitor-page {
  --monitor-line: rgba(17, 24, 39, .10);
  --monitor-muted: #6b7280;
  --monitor-text: #111827;
  display: grid;
  gap: 16px;
  min-height: calc(100vh - 128px);
  padding: 22px;
  border: 1px solid var(--monitor-line);
  border-radius: 16px;
  background: #f7f8fa;
}
.monitor-head, .panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.eyebrow {
  color: var(--primary-color, #f4511e);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}
h1, h3, p { margin: 0; }
h1, h3 { color: var(--monitor-text); font-weight: 800; }
.monitor-head p, .panel-head p {
  margin-top: 6px;
  color: var(--monitor-muted);
  font-size: 13px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.metric-card, .monitor-panel {
  border: 1px solid var(--monitor-line);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 10px 26px rgba(15, 23, 42, .06);
}
.metric-card {
  display: grid;
  gap: 8px;
  padding: 16px;
}
.metric-card span, .info-list span {
  color: var(--monitor-muted);
  font-size: 12px;
}
.metric-card b {
  color: var(--monitor-text);
  font-size: 24px;
  line-height: 1;
}
.metric-card p {
  color: var(--monitor-muted);
  font-size: 12px;
}
.monitor-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.monitor-panel {
  min-width: 0;
  overflow: hidden;
}
.panel-head {
  padding: 16px;
  border-bottom: 1px solid var(--monitor-line);
  background: #fbfcfd;
}
.info-list {
  display: grid;
  gap: 0;
  padding: 6px 16px 14px;
}
.info-list div {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 14px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(17, 24, 39, .06);
}
.info-list div:last-child { border-bottom: 0; }
.info-list b {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--monitor-text);
  font-weight: 700;
}
@media (max-width: 1100px) {
  .metric-grid, .monitor-grid { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .monitor-page { padding: 14px; }
  .monitor-head, .panel-head { flex-direction: column; }
  .info-list div { grid-template-columns: 1fr; gap: 4px; }
}
</style>
