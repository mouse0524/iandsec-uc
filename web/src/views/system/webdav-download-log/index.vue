<script setup>
import { h, nextTick, onMounted, ref } from 'vue'
import { NInput, NSelect, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import api from '@/api'

defineOptions({ name: '下载日志' })

const logTable = ref(null)
const queryItems = ref({})
const typeOptions = [
  { label: '直接下载', value: 'direct' },
  { label: '分享下载', value: 'share' },
]

onMounted(async () => {
  await nextTick()
  logTable.value?.handleSearch()
})

async function getLogTableData(params = {}) {
  const res = await api.webdavDownloadLogList(params)
  return {
    data: res?.data || [],
    total: Number(res?.total || 0),
  }
}

const columns = [
  { title: '文件名', key: 'file_name', minWidth: 180, ellipsis: { tooltip: true } },
  { title: '文件路径', key: 'file_path', minWidth: 240, ellipsis: { tooltip: true } },
  {
    title: '下载类型',
    key: 'download_type',
    width: 110,
    align: 'center',
    render(row) {
      const isShare = row.download_type === 'share'
      return h(NTag, { type: isShare ? 'warning' : 'info', bordered: false }, { default: () => (isShare ? '分享下载' : '直接下载') })
    },
  },
  { title: '下载者', key: 'downloader_name', width: 130, align: 'center', render: (row) => row.downloader_name || '公开访问' },
  { title: '来源IP', key: 'source_ip', width: 140, align: 'center', render: (row) => row.source_ip || '-' },
  { title: '分享码', key: 'share_code', width: 110, align: 'center', render: (row) => row.share_code || '-' },
  { title: '下载时间', key: 'created_at', width: 170, align: 'center', render: (row) => row.created_at || '-' },
  { title: '浏览器', key: 'user_agent', minWidth: 220, ellipsis: { tooltip: true }, render: (row) => row.user_agent || '-' },
]
</script>

<template>
  <CommonPage title="下载日志" :show-header="false" show-footer>
    <CrudTable
      ref="logTable"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="getLogTableData"
      :scroll-x="1320"
    >
      <template #queryBar>
        <QueryBarItem label="文件名" :label-width="54">
          <NInput v-model:value="queryItems.file_name" clearable placeholder="输入文件名" style="width: 220px" @keypress.enter="logTable?.handleSearch()" />
        </QueryBarItem>
        <QueryBarItem label="类型" :label-width="40">
          <NSelect v-model:value="queryItems.download_type" :options="typeOptions" clearable style="width: 150px" />
        </QueryBarItem>
      </template>
    </CrudTable>
  </CommonPage>
</template>
