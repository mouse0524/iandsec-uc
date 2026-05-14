<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import api from '@/api'

defineOptions({ name: '授权校验' })

const tableRef = ref(null)
const latest = ref(null)
const query = ref({ company_name: '' })

const latestStats = computed(() => latest.value || {})

const columns = [
  { title: '公司名称', key: 'company_name', minWidth: 150, fixed: 'left' },
  { title: '授权到期时间', key: 'auth_expire_at', width: 170, align: 'center' },
  { title: '维保到期时间', key: 'maintain_expire_at', width: 170, align: 'center' },
  {
    title: '已安装终端数量',
    key: 'terminal_stats_text',
    minWidth: 260,
    render(row) {
      return h('span', { class: 'wrap-cell' }, row.terminal_stats_text || '-')
    },
  },
  { title: '服务器版本号', key: 'server_version', width: 180, align: 'center' },
  {
    title: '客户端版本号',
    key: 'client_versions_text',
    minWidth: 260,
    render(row) {
      return h('span', { class: 'wrap-cell' }, row.client_versions_text || '-')
    },
  },
  { title: '上报时间', key: 'reported_at', width: 170, align: 'center' },
  { title: '来源IP', key: 'source_ip', width: 140, align: 'center' },
]

onMounted(loadLatest)

async function getTableData(params) {
  const res = await api.terminalAuthReports({ ...params, ...query.value })
  latest.value = res.data?.[0] || latest.value
  return res
}

async function loadLatest() {
  const res = await api.terminalLatestAuthReport()
  latest.value = res.data || null
}

function handleSearch() {
  tableRef.value?.handleSearch()
  loadLatest()
}
</script>

<template>
  <CommonPage title="授权校验" :show-header="false" show-footer>
    <div class="terminal-page">
      <header class="page-head">
        <div>
          <div class="eyebrow">Terminal License</div>
          <h1>授权校验</h1>
          <p>接收第三方上报的授权、维保、终端数量和版本分布信息。</p>
        </div>
        <NTag type="success" round>第三方上报</NTag>
      </header>

      <section class="summary-grid">
        <div class="summary-card">
          <span>最近上报公司</span>
          <b>{{ latestStats.company_name || '-' }}</b>
        </div>
        <div class="summary-card">
          <span>授权到期</span>
          <b>{{ latestStats.auth_expire_at || '-' }}</b>
        </div>
        <div class="summary-card">
          <span>维保到期</span>
          <b>{{ latestStats.maintain_expire_at || '-' }}</b>
        </div>
        <div class="summary-card">
          <span>服务器版本</span>
          <b>{{ latestStats.server_version || '-' }}</b>
        </div>
      </section>

      <section class="table-panel">
        <CrudTable
          ref="tableRef"
          row-key="id"
          :columns="columns"
          :get-data="getTableData"
          :scroll-x="1550"
        >
          <template #queryBar>
            <QueryBarItem label="公司名称" :label-width="80">
              <NInput
                v-model:value="query.company_name"
                clearable
                placeholder="按公司名称搜索"
                @keyup.enter="handleSearch"
              />
            </QueryBarItem>
            <QueryBarItem :label-width="0">
              <NButton type="primary" @click="handleSearch">查询</NButton>
            </QueryBarItem>
          </template>
        </CrudTable>
      </section>
    </div>
  </CommonPage>
</template>

<style scoped>
.terminal-page {
  --terminal-line: rgba(17, 24, 39, .10);
  --terminal-muted: #64748b;
  --terminal-text: #111827;
  display: grid;
  gap: 16px;
  min-height: calc(100vh - 128px);
  padding: 22px;
  border: 1px solid var(--terminal-line);
  border-radius: 16px;
  background: #f7f8fa;
}
.page-head {
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
h1, p {
  margin: 0;
}
h1 {
  margin-top: 4px;
  color: var(--terminal-text);
  font-weight: 800;
}
.page-head p {
  margin-top: 6px;
  color: var(--terminal-muted);
  font-size: 13px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.summary-card, .table-panel {
  border: 1px solid var(--terminal-line);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 10px 26px rgba(15, 23, 42, .06);
}
.summary-card {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 16px;
}
.summary-card span {
  color: var(--terminal-muted);
  font-size: 12px;
}
.summary-card b {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--terminal-text);
  font-size: 18px;
}
.table-panel {
  min-width: 0;
  padding: 14px;
}
.table-panel :deep(.n-card) {
  border: 0;
  background: transparent;
  box-shadow: none;
}
:deep(.wrap-cell) {
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.6;
}
@media (max-width: 1100px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .terminal-page {
    padding: 14px;
  }
  .page-head {
    flex-direction: column;
  }
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
