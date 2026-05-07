<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NCard, NForm, NFormItem, NInput, NModal, NSelect, NTag, NUpload } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import RichTextEditor from '@/components/editor/RichTextEditor.vue'
import TicketDetailModal from '@/views/ticket/components/TicketDetailModal.vue'
import api from '@/api'
import { isImageName } from '@/utils'
import { ticketStatusOptions, ticketStatusTextMap, ticketStatusTypeMap } from '@/views/ticket/components/ticket-meta'

defineOptions({ name: '我的工单' })

const $table = ref(null)
const route = useRoute()
const queryItems = ref({
  status: route.query.status || undefined,
  created_start: route.query.created_start || undefined,
  created_end: route.query.created_end || undefined,
  finished_start: route.query.finished_start || undefined,
  finished_end: route.query.finished_end || undefined,
})
const detailVisible = ref(false)
const currentTicket = ref({})
const tableData = ref([])
const editVisible = ref(false)
const editingTicketId = ref(null)
const savingEdit = ref(false)
const editUploadLoading = ref(false)
const editCaptchaImage = ref('')
const editFileList = ref([])
const editForm = ref({
  company_name: '',
  contact_name: '',
  email: '',
  phone: '',
  project_phase: '',
  category: '',
  title: '',
  description: '',
  attachment_ids: [],
  captcha_id: '',
  captcha_code: '',
})
const rootCauseOptions = ref([])
const categoryOptions = ref([])
const projectPhaseOptions = ref([])
const fallbackProjectPhases = ['售前', '实施', '售后']
const fallbackCategories = ['登录问题', '权限问题', '系统异常', '其他']
const fallbackRootCauses = ['代码缺陷', '配置错误', '环境异常', '数据问题', '操作不当', '第三方依赖']

const summaryCards = computed(() => {
  const rows = tableData.value || []
  const countByStatus = rows.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1
    return acc
  }, {})
  return [
    { label: '当前总工单', value: rows.length, tone: 'neutral' },
    { label: '审核中', value: countByStatus.pending_review || 0, tone: 'warning' },
    { label: '技术处理中', value: countByStatus.tech_processing || 0, tone: 'info' },
    { label: '已完成', value: countByStatus.done || 0, tone: 'success' },
  ]
})

onMounted(() => {
  $table.value?.handleSearch()
  loadTicketMetaOptions()
})

function buildObjectUrl(rawFile) {
  if (!rawFile) return ''
  try {
    return URL.createObjectURL(rawFile)
  } catch {
    return ''
  }
}

async function uploadEditFile(rawFile, targetFile = null) {
  const res = await api.uploadTicketAttachment(rawFile)
  const attachmentId = Number(res?.data?.id || 0)
  if (!attachmentId) throw new Error('上传成功但未返回附件ID')
  if (targetFile) {
    targetFile.attachmentId = attachmentId
    if (isImageName(targetFile.name)) {
      targetFile.url = buildObjectUrl(rawFile)
    }
  }
  if (!editForm.value.attachment_ids.includes(attachmentId)) {
    editForm.value.attachment_ids.push(attachmentId)
  }
}

async function buildEditPreviewItem(item) {
  const base = {
    id: String(item.id),
    name: item.origin_name || `附件${item.id}`,
    status: 'finished',
    attachmentId: Number(item.id),
  }
  if (!isImageName(item.origin_name || item.file_path)) return base
  try {
    const res = await api.downloadTicketAttachment({ attachment_id: item.id })
    const blob = res instanceof Blob ? res : new Blob([res])
    return { ...base, url: URL.createObjectURL(blob) }
  } catch {
    return base
  }
}

async function fetchEditCaptcha() {
  const res = await api.getCaptcha()
  editForm.value.captcha_id = res.data.captcha_id
  editCaptchaImage.value = `data:image/png;base64,${res.data.image_base64}`
}

function handleTableDataChange(rows) {
  tableData.value = Array.isArray(rows) ? rows : []
}

async function loadTicketMetaOptions() {
  try {
    const res = await api.getPublicConfig()
    const config = res?.data || {}
    const projectPhases = config.ticket_project_phases?.length ? config.ticket_project_phases : fallbackProjectPhases
    const categories = config.ticket_categories?.length ? config.ticket_categories : fallbackCategories
    const rootCauses = config.ticket_root_causes?.length ? config.ticket_root_causes : fallbackRootCauses
    projectPhaseOptions.value = projectPhases.map((item) => ({ label: item, value: item }))
    categoryOptions.value = categories.map((item) => ({ label: item, value: item }))
    rootCauseOptions.value = rootCauses.map((item) => ({ label: item, value: item }))
  } catch (error) {
    rootCauseOptions.value = fallbackRootCauses.map((item) => ({ label: item, value: item }))
    categoryOptions.value = fallbackCategories.map((item) => ({ label: item, value: item }))
    projectPhaseOptions.value = fallbackProjectPhases.map((item) => ({ label: item, value: item }))
  }
}

async function openDetail(row) {
  const res = await api.getTicketById({ ticket_id: row.id })
  currentTicket.value = res.data
  detailVisible.value = true
}

async function openEdit(row) {
  const detail = await api.getTicketById({ ticket_id: row.id })
  const source = detail?.data || row
  const existingAttachments = Array.isArray(source.attachments) ? source.attachments : []
  const existingIds = existingAttachments.map((item) => Number(item.id)).filter((id) => id > 0)
  editingTicketId.value = row.id
  editForm.value = {
    company_name: source.company_name || '',
    contact_name: source.contact_name || '',
    email: source.email || '',
    phone: source.phone || '',
    project_phase: source.project_phase || '',
    category: source.category || '',
    title: source.title || '',
    description: source.description || '',
    attachment_ids: existingIds,
    captcha_id: '',
    captcha_code: '',
  }
  editFileList.value = await Promise.all(existingAttachments.map((item) => buildEditPreviewItem(item)))
  await fetchEditCaptcha()
  editVisible.value = true
}

async function customEditUpload({ file, onFinish, onError }) {
  try {
    editUploadLoading.value = true
    await uploadEditFile(file.file, file)
    onFinish()
  } catch (error) {
    onError()
  } finally {
    editUploadLoading.value = false
  }
}

async function handleEditPasteUpload(event) {
  const files = Array.from(event?.clipboardData?.files || [])
  const imageFiles = files.filter((item) => /^image\//.test(item.type || ''))
  if (!imageFiles.length) return
  event.preventDefault()
  for (const rawFile of imageFiles) {
    if (editFileList.value.length >= 5) break
    const uploadFile = {
      id: `${Date.now()}-${Math.random()}`,
      name: rawFile.name || `pasted-${Date.now()}.png`,
      status: 'uploading',
      file: rawFile,
      url: buildObjectUrl(rawFile),
    }
    editFileList.value = [...editFileList.value, uploadFile]
    try {
      editUploadLoading.value = true
      await uploadEditFile(rawFile, uploadFile)
      uploadFile.status = 'finished'
    } catch {
      uploadFile.status = 'error'
    } finally {
      editUploadLoading.value = false
    }
  }
}

function handleEditRemove({ file }) {
  const attachmentId = Number(file?.attachmentId || 0)
  if (attachmentId > 0) {
    editForm.value.attachment_ids = editForm.value.attachment_ids.filter((id) => id !== attachmentId)
  }
}

async function submitEdit() {
  if (!editingTicketId.value) return
  if (!editForm.value.captcha_code?.trim()) {
    $message.warning('请输入验证码')
    return
  }
  try {
    savingEdit.value = true
    const payload = {
      ticket_id: editingTicketId.value,
      ...editForm.value,
    }
    await api.updateTicket(payload)
    $message.success('工单已更新')
    closeEditModal()
    $table.value?.handleSearch()
  } finally {
    savingEdit.value = false
  }
}

function closeEditModal() {
  editVisible.value = false
  editingTicketId.value = null
  editFileList.value = []
  editCaptchaImage.value = ''
  editForm.value.captcha_id = ''
  editForm.value.captcha_code = ''
}

const columns = [
  { title: '工单编号', key: 'ticket_no', align: 'center' },
  { title: '项目阶段', key: 'project_phase', align: 'center' },
  { title: '问题分类', key: 'category', align: 'center' },
  { title: '标题', key: 'title', align: 'center', ellipsis: { tooltip: true } },
  { title: '问题根因', key: 'root_cause', align: 'center', ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    align: 'center',
    render(row) {
      return h(NTag, { type: ticketStatusTypeMap[row.status] || 'default' }, { default: () => ticketStatusTextMap[row.status] })
    },
  },
  { title: '创建时间', key: 'created_at', align: 'center' },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    render(row) {
      return [
        h(
          NButton,
          { size: 'small', type: 'primary', onClick: () => openDetail(row), style: 'margin-right: 8px' },
          { default: () => '详情' }
        ),
        h(
          NButton,
          {
            size: 'small',
            type: 'warning',
            disabled: !['cs_rejected', 'tech_rejected'].includes(row.status),
            onClick: () => openEdit(row),
          },
          { default: () => '编辑' }
        ),
      ]
    },
  },
]

</script>

<template>
  <CommonPage title="我的工单" show-footer>
    <div class="ticket-my-page">
      <div class="summary-grid">
        <div v-for="item in summaryCards" :key="item.label" class="summary-card" :data-tone="item.tone">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>

      <NCard size="small" class="table-shell">
        <CrudTable
          ref="$table"
          v-model:query-items="queryItems"
          :columns="columns"
          :get-data="api.getTicketList"
          @on-data-change="handleTableDataChange"
        >
          <template #queryBar>
            <QueryBarItem label="标题" :label-width="40">
              <n-input v-model:value="queryItems.title" clearable placeholder="输入标题" @keypress.enter="$table?.handleSearch()" />
            </QueryBarItem>
            <QueryBarItem label="分类" :label-width="40">
              <NSelect v-model:value="queryItems.category" :options="categoryOptions" clearable placeholder="选择分类" style="width: 180px" />
            </QueryBarItem>
            <QueryBarItem label="阶段" :label-width="40">
              <NSelect
                v-model:value="queryItems.project_phase"
                :options="projectPhaseOptions"
                clearable
                placeholder="选择阶段"
                style="width: 180px"
              />
            </QueryBarItem>
            <QueryBarItem label="状态" :label-width="40">
              <NSelect v-model:value="queryItems.status" :options="ticketStatusOptions" clearable placeholder="选择状态" style="width: 180px" />
            </QueryBarItem>
            <QueryBarItem label="根因" :label-width="40">
              <NSelect
                v-model:value="queryItems.root_cause"
                :options="rootCauseOptions"
                clearable
                placeholder="选择问题根因"
                style="width: 180px"
              />
            </QueryBarItem>
          </template>
        </CrudTable>
      </NCard>

      <TicketDetailModal v-model:visible="detailVisible" :ticket="currentTicket" />

      <NModal v-model:show="editVisible" preset="card" title="编辑工单" style="width: 920px">
        <div class="edit-shell">
          <div class="edit-alert">客服驳回后，保存会重新进入客服审核；技术驳回后，保存会直接进入技术处理。</div>
          <NForm :model="editForm" :label-width="92" label-placement="left">
            <div class="edit-section">
              <div class="edit-section-head">
                <h3>联系信息</h3>
                <p>用于后续回访、通知与处理同步。</p>
              </div>
              <div class="edit-grid two-col">
                <NFormItem label="公司名称">
                  <NInput v-model:value="editForm.company_name" placeholder="请输入公司名称" />
                </NFormItem>
                <NFormItem label="联系人">
                  <NInput v-model:value="editForm.contact_name" placeholder="请输入联系人" />
                </NFormItem>
                <NFormItem label="邮箱">
                  <NInput v-model:value="editForm.email" placeholder="请输入邮箱" />
                </NFormItem>
                <NFormItem label="手机号">
                  <NInput v-model:value="editForm.phone" placeholder="请输入手机号" />
                </NFormItem>
              </div>
            </div>

            <div class="edit-section">
              <div class="edit-section-head compact">
                <h3>问题内容</h3>
                <p>建议补充复现步骤、影响范围和错误信息。</p>
              </div>
              <div class="edit-grid single-col">
                <NFormItem label="项目阶段">
                  <NSelect v-model:value="editForm.project_phase" :options="projectPhaseOptions" placeholder="请选择项目阶段" />
                </NFormItem>
                <NFormItem label="问题分类">
                  <NSelect v-model:value="editForm.category" :options="categoryOptions" placeholder="请选择问题分类" />
                </NFormItem>
                <NFormItem label="问题标题">
                  <NInput v-model:value="editForm.title" placeholder="请输入问题标题" />
                </NFormItem>
                <NFormItem label="问题描述">
                  <RichTextEditor
                    v-model="editForm.description"
                    placeholder="请详细描述问题现象、复现步骤、影响范围"
                    :min-height="220"
                    :max-height="420"
                  />
                </NFormItem>
                <NFormItem label="附件">
                  <div class="upload-box" @paste="handleEditPasteUpload">
                    <NUpload
                      v-model:file-list="editFileList"
                      list-type="image-card"
                      :custom-request="customEditUpload"
                      :max="5"
                      accept=".zip,.rar,.png,.jpg,.jpeg,.gif"
                      @remove="handleEditRemove"
                    >
                      <NButton :loading="editUploadLoading">上传附件</NButton>
                    </NUpload>
                  </div>
                  <div class="upload-tip">支持最多 5 个附件，支持粘贴图片上传。</div>
                </NFormItem>
                <NFormItem label="验证码">
                  <div class="captcha-row">
                    <NInput v-model:value="editForm.captcha_code" placeholder="请输入验证码" style="width: 180px" />
                    <img :src="editCaptchaImage" alt="captcha" class="captcha-img" @click="fetchEditCaptcha" />
                    <NButton text type="primary" @click="fetchEditCaptcha">换一张</NButton>
                  </div>
                </NFormItem>
              </div>
            </div>
          </NForm>
        </div>
        <div class="edit-actions">
          <NButton @click="closeEditModal">取消</NButton>
          <NButton type="primary" :loading="savingEdit" @click="submitEdit">保存修改</NButton>
        </div>
      </NModal>
    </div>
  </CommonPage>
</template>

<style scoped>
.ticket-my-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.summary-card {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid #ebeef5;
  background: #fff;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.05);
}

.summary-card span {
  display: block;
  color: #6b7280;
  font-size: 13px;
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  font-size: 28px;
  line-height: 1;
  color: #111827;
}

.summary-card[data-tone='warning'] {
  background: linear-gradient(180deg, #fffaf0 0%, #ffffff 100%);
}

.summary-card[data-tone='info'] {
  background: linear-gradient(180deg, #f3f8ff 0%, #ffffff 100%);
}

.summary-card[data-tone='success'] {
  background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%);
}

.table-shell {
  border-radius: 20px;
}

.edit-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.edit-alert {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #fde68a;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
  line-height: 1.5;
}

.edit-section {
  padding: 14px;
  border: 1px solid #ebeef5;
  border-radius: 14px;
  background: #ffffff;
}

.edit-section-head {
  margin-bottom: 8px;
}

.edit-section-head h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}

.edit-section-head p {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.edit-section-head.compact {
  margin-bottom: 10px;
}

.edit-grid {
  display: grid;
  gap: 10px 14px;
}

.edit-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.edit-grid.single-col {
  grid-template-columns: minmax(0, 1fr);
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

.upload-box {
  width: 100%;
}

.captcha-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.captcha-img {
  width: 120px;
  height: 34px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  background: #fff;
  object-fit: cover;
}

@media (max-width: 960px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .edit-grid.two-col {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
