<script setup>
import { h, nextTick, onMounted, ref } from 'vue'
import { NButton, NInput, NPopconfirm, NSwitch, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import api from '@/api'

defineOptions({ name: '分享记录' })

const shareTable = ref(null)
const shareQuery = ref({ include_history: false })

onMounted(async () => {
  await nextTick()
  shareTable.value?.handleSearch()
})

async function getShareTableData(params = {}) {
  const res = await api.webdavShareList(params)
  return {
    data: res?.data || [],
    total: Number(res?.total || 0),
  }
}

function buildDownloadUrl(apiUrl) {
  if (!apiUrl) return ''
  const publicShareApiPath = '/api/v1/public/webdav/share/download'
  let parsedUrl = null
  try {
    parsedUrl = new URL(apiUrl, window.location.origin)
  } catch {
    parsedUrl = null
  }
  if (parsedUrl?.pathname === publicShareApiPath) {
    return `${window.location.origin}/public/webdav/share/download${parsedUrl.search}`
  }
  if (/^https?:\/\//i.test(apiUrl)) return apiUrl
  const path = apiUrl.startsWith('/') ? apiUrl : `/${apiUrl}`
  return `${window.location.origin}${path}`
}

async function copyText(text) {
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  const success = document.execCommand('copy')
  textarea.remove()
  if (!success) throw new Error('copy failed')
}

const shareColumns = [
  { title: '分享码', key: 'code', width: 120, align: 'center' },
  { title: '创建者', key: 'creator_name', width: 120, align: 'center' },
  { title: '文件名', key: 'file_name', align: 'left' },
  { title: '文件路径', key: 'file_path', align: 'left' },
  { title: '过期时间', key: 'expire_time', width: 180, align: 'center' },
  {
    title: '状态',
    key: 'is_active',
    width: 90,
    align: 'center',
    render(row) {
      const expired = row.is_expired || row.status === 'expired'
      const active = row.is_active && !expired
      const type = active ? 'success' : (expired ? 'warning' : 'default')
      const text = active ? '生效' : (expired ? '过期' : '失效')
      return h(NTag, { type, bordered: false }, { default: () => text })
    },
  },
  {
    title: '下载链接',
    key: 'link',
    width: 280,
    align: 'left',
    render(row) {
      const url = buildDownloadUrl(row.download_url || '')
      const disabled = !row.is_active || row.is_expired || row.status === 'expired'
      return h(
        NButton,
        {
          type: 'primary',
          text: true,
          disabled,
          onClick: async () => {
            if (disabled) return
            if (!url) {
              $message.error('当前记录缺少下载链接，请刷新后重试')
              return
            }
            try {
              await copyText(url)
              $message.success('下载链接已复制')
            } catch (error) {
              $message.error('复制失败，请手动选中链接复制')
            }
          },
        },
        { default: () => (disabled ? '已失效' : (url || '链接生成中')) }
      )
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    align: 'center',
    render(row) {
      return h(
        NPopconfirm,
        { onPositiveClick: () => deleteShare(row.id) },
        {
          trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
          default: () => '确认删除该分享记录？',
        }
      )
    },
  },
]

async function deleteShare(id) {
  await api.webdavShareDelete({ id })
  $message.success('分享记录已删除')
  shareTable.value?.handleSearch()
}
</script>

<template>
  <CommonPage title="分享记录" show-footer>
    <CrudTable
      ref="shareTable"
      v-model:query-items="shareQuery"
      :columns="shareColumns"
      :get-data="getShareTableData"
    >
      <template #queryBar>
        <div class="share-query-item">
          <QueryBarItem label="文件名" :label-width="60">
            <NInput class="share-query-input" v-model:value="shareQuery.file_name" clearable placeholder="输入文件名" @keypress.enter="shareTable?.handleSearch()" />
          </QueryBarItem>
        </div>
        <div class="share-query-item">
          <QueryBarItem label="显示历史" :label-width="70">
            <NSwitch v-model:value="shareQuery.include_history" />
          </QueryBarItem>
        </div>
      </template>
    </CrudTable>
  </CommonPage>
</template>

<style scoped>
.share-query-item {
  display: flex;
  align-items: center;
  min-height: 34px;
}

.share-query-input {
  width: 220px;
}
</style>
