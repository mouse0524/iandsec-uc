<script setup>
import { h, onMounted, ref } from 'vue'
import { NAlert, NButton, NDataTable, NInput, NPopconfirm, NSpace, NTag, NUpload } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '知识来源' })

const loading = ref(false)
const uploadLoading = ref(false)
const keyword = ref('')
const rows = ref([])
const total = ref(0)
const health = ref(null)
const page = ref(1)
const pageSize = ref(10)
const statusLabels = {
  completed: '已完成',
  failed: '失败',
  pending: '待处理',
  building: '生成中',
}

const columns = [
  { title: '标题', key: 'title', minWidth: 160 },
  { title: '原始文件', key: 'file_path', minWidth: 240, ellipsis: { tooltip: true } },
  { title: 'Markdown', key: 'markdown_path', minWidth: 240, ellipsis: { tooltip: true } },
  { title: '类型', key: 'file_type', width: 90 },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render(row) {
      const type = row.status === 'completed' ? 'success' : row.status === 'failed' ? 'error' : 'warning'
      return h(NTag, { type }, { default: () => statusLabels[row.status] || row.status })
    },
  },
  { title: '错误信息', key: 'error_message', minWidth: 180 },
  {
    title: '操作',
    key: 'actions',
    width: 170,
    render(row) {
      return h(
        NSpace,
        { size: 8 },
        {
          default: () => [
            h(
              NButton,
              { size: 'small', disabled: row.status !== 'failed', onClick: () => retry(row.id) },
              { default: () => '重试' }
            ),
            h(
              NPopconfirm,
              { onPositiveClick: () => remove(row.id) },
              {
                trigger: () => h(NButton, { size: 'small', type: 'error', ghost: true }, { default: () => '删除' }),
                default: () => '确定删除该知识来源及其生成内容？',
              }
            ),
          ],
        }
      )
    },
  },
]

async function load() {
  loading.value = true
  try {
    const res = await api.wikiSourceList({ page: page.value, page_size: pageSize.value, keyword: keyword.value || undefined })
    const healthRes = await api.wikiHealth()
    rows.value = res?.data || []
    total.value = res?.total || 0
    health.value = healthRes?.data || null
  } finally {
    loading.value = false
  }
}

async function upload({ file }) {
  uploadLoading.value = true
  try {
    const rawFile = file.file
    const init = await api.wikiInitChunkUpload({
      filename: rawFile.name,
      file_size: rawFile.size,
      total_chunks: Math.ceil(rawFile.size / (2 * 1024 * 1024)) || 1,
    })
    const uploadId = init?.data?.upload_id
    const chunkSize = init?.data?.chunk_size || 2 * 1024 * 1024
    const totalChunks = Math.ceil(rawFile.size / chunkSize) || 1
    for (let index = 0; index < totalChunks; index += 1) {
      const chunk = rawFile.slice(index * chunkSize, Math.min(rawFile.size, (index + 1) * chunkSize))
      await api.wikiUploadChunk({ upload_id: uploadId, chunk_index: index }, chunk)
    }
    await api.wikiCompleteChunkUpload({ upload_id: uploadId, filename: rawFile.name, total_chunks: totalChunks })
    window.$message?.success('上传完成，后台正在整理 Wiki')
    load().catch(() => {})
  } catch (error) {
    window.$message?.error(error?.message || '上传失败')
  } finally {
    uploadLoading.value = false
  }
}

async function retry(id) {
  await api.wikiRetrySource({ source_id: id })
  await load()
}

async function remove(id) {
  await api.wikiDeleteSource({ source_id: id })
  await load()
}

onMounted(load)
</script>

<template>
  <CommonPage>
    <template #action>
      <NSpace>
        <NInput v-model:value="keyword" placeholder="关键词" clearable @keyup.enter="load" />
        <NButton type="primary" @click="load">搜索</NButton>
        <NUpload :show-file-list="false" accept=".md,.txt,.csv,.html,.htm,.docx,.xlsx,.pdf" :custom-request="upload">
          <NButton :loading="uploadLoading">上传</NButton>
        </NUpload>
      </NSpace>
    </template>
    <NAlert type="info" class="mb-12">
      已上传 {{ health?.source_count || 0 }} 个原始文件；LLM Wiki 当前生成/维护 {{ health?.page_count || 0 }} 个 Markdown 页面。
      一个文件可能会生成来源页、摘要、术语或实践等多个 Wiki 页面。
    </NAlert>
    <NAlert v-if="health && !health.ok" type="warning" class="mb-12">
      Wiki 结构不完整：缺失 {{ [...(health.missing || []), ...(health.missing_page_files || [])].join('，') }}
    </NAlert>
    <NDataTable
      remote
      :loading="loading"
      :columns="columns"
      :data="rows"
      :pagination="{ page, pageSize, itemCount: total, onUpdatePage: (v) => { page = v; load() } }"
    />
  </CommonPage>
</template>
