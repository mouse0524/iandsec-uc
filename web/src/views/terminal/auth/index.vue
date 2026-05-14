<script setup>
import { h, ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import api from '@/api'

defineOptions({ name: '授权校验' })

const tableRef = ref(null)
const query = ref({ company_name: '' })

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

async function getTableData(params) {
  const res = await api.terminalAuthReports({ ...params, ...query.value })
  return res
}

function handleSearch() {
  tableRef.value?.handleSearch()
}
</script>

<template>
  <CommonPage title="授权校验" :show-header="false" show-footer>
    <div class="terminal-page">
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
  min-height: calc(100vh - 128px);
  padding: 22px;
  background: #f7f8fa;
}
.table-panel {
  border: 1px solid var(--terminal-line);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 10px 26px rgba(15, 23, 42, .06);
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
@media (max-width: 640px) {
  .terminal-page {
    padding: 14px;
  }
}
</style>
