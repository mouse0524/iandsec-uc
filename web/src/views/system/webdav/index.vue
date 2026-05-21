<script setup>
import { computed, h, nextTick, onMounted, ref } from 'vue'
import { NButton, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import api from '@/api'

defineOptions({ name: '外发网盘' })

const currentPath = ref('/')
const fileList = ref([])
const loading = ref(false)
const fileTable = ref(null)
const creatingSharePath = ref('')
const downloadingPath = ref('')
const isCreatingShare = computed(() => !!creatingSharePath.value)

const breadcrumbItems = computed(() => {
  const clean = (currentPath.value || '/').replace(/^\/+|\/+$/g, '')
  const items = [{ label: '首页', path: '/' }]
  if (!clean) return items
  const parts = clean.split('/')
  for (let idx = 0; idx < parts.length; idx += 1) {
    items.push({
      label: parts[idx],
      path: '/' + parts.slice(0, idx + 1).join('/'),
    })
  }
  return items
})

async function getFileTableData() {
  return {
    data: fileList.value,
    total: fileList.value.length,
  }
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let idx = 0
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx += 1
  }
  return `${size.toFixed(size >= 100 || idx === 0 ? 0 : 1)} ${units[idx]}`
}

const fileColumns = [
  {
    title: '名称',
    key: 'name',
    align: 'left',
    render(row) {
      if (row.is_dir) {
        return h(
          'button',
          { class: 'file-name-button folder', type: 'button', onClick: () => openDir(row.path) },
          [h('span', { class: 'file-icon' }, '📁'), h('span', { class: 'file-title' }, row.name)]
        )
      }
      return h('div', { class: 'file-name-static' }, [h('span', { class: 'file-icon' }, '📄'), h('span', { class: 'file-title' }, row.name)])
    },
  },
  {
    title: '类型',
    key: 'type',
    width: 120,
    align: 'center',
    render(row) {
      return h(NTag, { size: 'small', round: true, type: row.is_dir ? 'success' : 'info' }, { default: () => (row.is_dir ? '目录' : '文件') })
    },
  },
  {
    title: '大小',
    key: 'size',
    width: 120,
    align: 'center',
    render(row) {
      if (row.is_dir) return '-'
      return formatSize(row.size || 0)
    },
  },
  { title: '修改时间', key: 'mod_time', width: 180, align: 'center' },
  {
    title: '操作',
    key: 'actions',
    width: 230,
    align: 'center',
    render(row) {
      if (row.is_dir) return h('span', { class: 'muted-action' }, '进入目录')
      return h(
        'div',
        { class: 'file-actions' },
        [
          h(
            NButton,
            {
              size: 'small',
              type: 'primary',
              secondary: true,
              loading: creatingSharePath.value === row.path,
              disabled: isCreatingShare.value || !!downloadingPath.value,
              onClick: () => createShare(row),
            },
            { default: () => '创建分享' }
          ),
          h(
            NButton,
            {
              size: 'small',
              type: 'info',
              secondary: true,
              loading: downloadingPath.value === row.path,
              disabled: !!downloadingPath.value || isCreatingShare.value,
              onClick: () => downloadFile(row),
            },
            { default: () => '直接下载' }
          ),
        ]
      )
    },
  },
]

onMounted(() => {
  loadFiles()
})

async function loadFiles() {
  try {
    loading.value = true
    const res = await api.webdavList({ path: currentPath.value })
    fileList.value = res.data || []
    await nextTick()
    fileTable.value?.handleSearch()
  } finally {
    loading.value = false
  }
}

async function openDir(path) {
  const previousPath = currentPath.value
  currentPath.value = path
  try {
    await loadFiles()
  } catch (error) {
    currentPath.value = previousPath
    const message = error?.message || error?.msg || '目录读取失败，请确认目标路径是否存在'
    $message.error(message)
  }
}

async function goParent() {
  if (currentPath.value === '/') return
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  currentPath.value = parts.length ? '/' + parts.join('/') : '/'
  await loadFiles()
}

async function createShare(row) {
  if (isCreatingShare.value) return
  try {
    creatingSharePath.value = row.path
    const res = await api.webdavCreateShare({
      file_path: row.path,
      file_name: row.name,
      expire_hours: null,
    })
    if (res?.data?.reused) {
      $message.info('该文件已有有效分享，已返回原链接（可在“分享记录”查看）')
    } else {
      $message.success('分享创建成功，可在“分享记录”菜单查看')
    }
  } finally {
    creatingSharePath.value = ''
  }
}

function openDownloadUrl(url) {
  const link = document.createElement('a')
  link.href = url
  link.target = '_blank'
  link.rel = 'noopener noreferrer'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

async function downloadFile(row) {
  if (!row?.path || downloadingPath.value) return
  try {
    downloadingPath.value = row.path
    const res = await api.webdavDownload({ path: row.path })
    const apiUrl = res?.data?.download_url || ''
    if (!apiUrl) {
      $message.error('下载链接生成失败，请稍后重试')
      return
    }
    const path = apiUrl.startsWith('/') ? apiUrl : `/${apiUrl}`
    openDownloadUrl(`${window.location.origin}${path}`)
  } finally {
    downloadingPath.value = ''
  }
}
</script>

<template>
  <CommonPage title="外发网盘" :show-header="false" show-footer>
    <div class="webdav-workspace">
      <section class="browser-panel">
        <div class="browser-toolbar">
          <div class="path-block">
            <div class="path-label">当前位置</div>
            <div class="path-nav">
              <template v-for="(item, idx) in breadcrumbItems" :key="item.path">
                <button
                  v-if="idx < breadcrumbItems.length - 1"
                  class="path-button"
                  type="button"
                  @click="openDir(item.path)"
                >
                  {{ item.label }}
                </button>
                <span v-else class="path-current">{{ item.label }}</span>
                <span v-if="idx < breadcrumbItems.length - 1" class="path-sep">/</span>
              </template>
            </div>
          </div>
          <div class="toolbar-actions">
            <NButton tertiary round type="primary" :disabled="currentPath === '/'" @click="goParent">返回上级</NButton>
            <NButton secondary round :loading="loading" @click="loadFiles">刷新目录</NButton>
          </div>
        </div>

        <div class="table-shell">
          <CrudTable
            ref="fileTable"
            :columns="fileColumns"
            :is-pagination="false"
            :remote="false"
            :get-data="getFileTableData"
          />
        </div>
      </section>
    </div>
  </CommonPage>
</template>

<style scoped>
.webdav-workspace {
  --wd-card: rgba(255, 255, 255, .92);
  --wd-line: rgba(15, 23, 42, .10);
  --wd-text: #101827;
  --wd-muted: #64748b;
}
.browser-panel {
  margin-top: 16px;
  overflow: hidden;
  border: 1px solid var(--wd-line);
  border-radius: 22px;
  background: var(--wd-card);
  box-shadow: 0 16px 42px rgba(15, 23, 42, .07);
}
.browser-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid var(--wd-line);
  background: rgba(248, 250, 252, .88);
}
.path-label {
  margin-bottom: 8px;
  color: var(--wd-muted);
  font-size: 12px;
  font-weight: 800;
}
.path-nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.path-button {
  padding: 4px 10px;
  border: 1px solid rgba(2, 132, 199, .18);
  border-radius: 999px;
  color: #0369a1;
  background: rgba(240, 249, 255, .86);
  cursor: pointer;
  transition: .18s ease;
}
.path-button:hover {
  border-color: rgba(2, 132, 199, .38);
  background: #e0f2fe;
}
.path-sep {
  color: #94a3b8;
  user-select: none;
}
.path-current {
  padding: 4px 10px;
  border-radius: 999px;
  color: var(--wd-text);
  background: #fff;
  font-weight: 800;
}
.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}
.table-shell {
  padding: 14px;
}
.table-shell :deep(.n-card) {
  border: 0;
  background: transparent;
  box-shadow: none;
}
.table-shell :deep(.n-data-table-th) {
  font-weight: 900;
  background: #f8fafc;
}
.table-shell :deep(.n-data-table-td) {
  vertical-align: middle;
}
:deep(.file-name-button), :deep(.file-name-static) {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  max-width: 100%;
  color: var(--wd-text);
}
:deep(.file-name-button) {
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}
:deep(.file-name-button.folder) {
  color: #0369a1;
  font-weight: 800;
}
:deep(.file-icon) {
  width: 30px;
  height: 30px;
  display: inline-grid;
  place-items: center;
  border-radius: 10px;
  background: #f1f5f9;
}
:deep(.file-title) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
:deep(.muted-action) {
  color: #94a3b8;
  font-size: 12px;
}
:deep(.file-actions) {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}
@media (max-width: 1100px) {
  .browser-toolbar { flex-direction: column; align-items: stretch; }
}
@media (max-width: 640px) {
  .toolbar-actions { justify-content: flex-start; }
}
</style>
