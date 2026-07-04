<script setup>
import { computed, ref, watch } from 'vue'
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, NUpload } from 'naive-ui'
import RichTextEditor from '@/components/editor/RichTextEditor.vue'
import api from '@/api'
import { isImageName } from '@/utils'
import { useAppStore } from '@/store'
import HumanChallenge from '@/components/HumanChallenge.vue'

const props = defineProps({
  visible: Boolean,
  ticket: { type: Object, default: () => ({}) },
  options: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:visible', 'saved'])

const appStore = useAppStore()
const saving = ref(false)
const uploadLoading = ref(false)
const challengeRef = ref(null)
const fileList = ref([])
const form = ref(defaultForm())
const challengeEnabled = computed(() => appStore.loginChallengeEnabled !== false)
const requiresCaptcha = computed(() => challengeEnabled.value && ['captcha', 'both'].includes(appStore.loginChallengeType || 'captcha'))
const requiresTurnstile = computed(() => challengeEnabled.value && ['turnstile', 'both'].includes(appStore.loginChallengeType || 'captcha'))

watch(
  () => props.visible,
  async (visible) => {
    if (visible) await resetForm()
  }
)

function defaultForm() {
  return {
    company_name: '',
    contact_name: '',
    email: '',
    phone: '',
    project_phase: '',
    issue_type: '',
    impact_scope: '',
    category: '',
    title: '',
    description: '',
    attachment_ids: [],
    captcha_id: '',
    captcha_code: '',
    turnstile_token: '',
  }
}

function normalizeOptions(key) {
  return Array.isArray(props.options?.[key]) ? props.options[key] : []
}

function buildObjectUrl(rawFile) {
  if (!rawFile) return ''
  try {
    return URL.createObjectURL(rawFile)
  } catch {
    return ''
  }
}

async function uploadFile(rawFile, targetFile = null) {
  const res = await api.uploadTicketAttachment(rawFile)
  const attachmentId = Number(res?.data?.id || 0)
  if (!attachmentId) throw new Error('上传成功但未返回附件ID')
  if (targetFile) {
    targetFile.attachmentId = attachmentId
    if (isImageName(targetFile.name)) targetFile.url = buildObjectUrl(rawFile)
  }
  if (!form.value.attachment_ids.includes(attachmentId)) {
    form.value.attachment_ids.push(attachmentId)
  }
}

async function buildPreviewItem(item) {
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

async function resetForm() {
  const source = props.ticket || {}
  const attachments = Array.isArray(source.attachments) ? source.attachments : []
  const ids = attachments.map((item) => Number(item.id)).filter((id) => id > 0)
  form.value = {
    ...defaultForm(),
    company_name: source.company_name || '',
    contact_name: source.contact_name || '',
    email: source.email || '',
    phone: source.phone || '',
    project_phase: source.project_phase || '',
    issue_type: source.issue_type || normalizeOptions('issueTypes')[0]?.value || '',
    impact_scope: source.impact_scope || normalizeOptions('impactScopes')[0]?.value || '',
    category: source.category || '',
    title: source.title || '',
    description: source.description || '',
    attachment_ids: ids,
  }
  fileList.value = await Promise.all(attachments.map((item) => buildPreviewItem(item)))
}

async function customUpload({ file, onFinish, onError }) {
  try {
    uploadLoading.value = true
    await uploadFile(file.file, file)
    onFinish()
  } catch {
    onError()
  } finally {
    uploadLoading.value = false
  }
}

async function handlePasteUpload(event) {
  const files = Array.from(event?.clipboardData?.files || [])
  const imageFiles = files.filter((item) => /^image\//.test(item.type || ''))
  if (!imageFiles.length) return
  event.preventDefault()
  for (const rawFile of imageFiles) {
    if (fileList.value.length >= 5) break
    const uploadItem = {
      id: `${Date.now()}-${Math.random()}`,
      name: rawFile.name || `pasted-${Date.now()}.png`,
      status: 'uploading',
      file: rawFile,
      url: buildObjectUrl(rawFile),
    }
    fileList.value = [...fileList.value, uploadItem]
    try {
      uploadLoading.value = true
      await uploadFile(rawFile, uploadItem)
      uploadItem.status = 'finished'
    } catch {
      uploadItem.status = 'error'
    } finally {
      uploadLoading.value = false
    }
  }
}

function handleRemove({ file }) {
  const attachmentId = Number(file?.attachmentId || 0)
  if (attachmentId > 0) {
    form.value.attachment_ids = form.value.attachment_ids.filter((id) => id !== attachmentId)
  }
}

function close() {
  emit('update:visible', false)
}

async function submit() {
  if (!props.ticket?.id) return
  const challengeError = validateChallenge()
  if (challengeError !== true) {
    window.$message?.warning(challengeError.message)
    return
  }
  try {
    saving.value = true
    await api.updateTicket({ ticket_id: props.ticket.id, ...form.value })
    window.$message?.success('工单已更新')
    emit('saved')
    close()
  } finally {
    saving.value = false
  }
}

function validateChallenge() {
  if (!challengeEnabled.value) return true
  const hasCaptcha = !!form.value.captcha_id && !!form.value.captcha_code?.trim()
  if (requiresCaptcha.value && !hasCaptcha) {
    return new Error('请先完成图形验证码')
  }
  if (requiresTurnstile.value && !form.value.turnstile_token && !hasCaptcha) {
    return new Error('请先完成 Cloudflare Turnstile 安全校验')
  }
  return true
}
</script>

<template>
  <NModal :show="visible" preset="card" title="编辑工单" style="width: 920px" @update:show="emit('update:visible', $event)">
    <div class="edit-shell">
      <div class="edit-alert">提交者、客服、当前技术均可编辑工单内容；已关闭工单不可编辑。</div>
      <NForm :model="form" :label-width="92" label-placement="left">
        <div class="edit-section">
          <div class="edit-section-head">
            <h3>联系信息</h3>
            <p>用于后续回访、通知与处理同步。</p>
          </div>
          <div class="edit-grid two-col">
            <NFormItem label="公司名称">
              <NInput v-model:value="form.company_name" placeholder="请输入公司名称" />
            </NFormItem>
            <NFormItem label="联系人">
              <NInput v-model:value="form.contact_name" placeholder="请输入联系人" />
            </NFormItem>
            <NFormItem label="邮箱">
              <NInput v-model:value="form.email" placeholder="请输入邮箱" />
            </NFormItem>
            <NFormItem label="手机号">
              <NInput v-model:value="form.phone" placeholder="请输入手机号" />
            </NFormItem>
          </div>
        </div>

        <div class="edit-section">
          <div class="edit-section-head compact">
            <h3>问题内容</h3>
            <p>可补充复现步骤、影响范围和错误信息。</p>
          </div>
          <div class="edit-grid single-col">
            <NFormItem label="项目阶段">
              <NSelect v-model:value="form.project_phase" :options="normalizeOptions('projectPhases')" placeholder="请选择项目阶段" />
            </NFormItem>
            <NFormItem label="跟踪">
              <NSelect v-model:value="form.issue_type" :options="normalizeOptions('issueTypes')" placeholder="请选择跟踪" />
            </NFormItem>
            <NFormItem label="影响范围">
              <NSelect v-model:value="form.impact_scope" :options="normalizeOptions('impactScopes')" placeholder="请选择影响范围" />
            </NFormItem>
            <NFormItem label="问题分类">
              <NSelect v-model:value="form.category" :options="normalizeOptions('categories')" placeholder="请选择问题分类" />
            </NFormItem>
            <NFormItem label="问题标题">
              <NInput v-model:value="form.title" placeholder="请输入问题标题" />
            </NFormItem>
            <NFormItem label="问题描述">
              <RichTextEditor v-model="form.description" placeholder="请详细描述问题现象、复现步骤、影响范围" :min-height="220" :max-height="420" />
            </NFormItem>
            <NFormItem label="附件">
              <div class="upload-box" @paste="handlePasteUpload">
                <NUpload
                  v-model:file-list="fileList"
                  list-type="image-card"
                  :custom-request="customUpload"
                  :max="5"
                  accept=".zip,.rar,.png,.jpg,.jpeg,.gif"
                  @remove="handleRemove"
                >
                  <NButton :loading="uploadLoading">上传附件</NButton>
                </NUpload>
              </div>
              <div class="upload-tip">支持最多 5 个附件，支持粘贴图片上传。</div>
            </NFormItem>
            <NFormItem v-if="challengeEnabled" label="安全校验">
              <HumanChallenge
                ref="challengeRef"
                v-model:captcha-id="form.captcha_id"
                v-model:captcha-code="form.captcha_code"
                v-model:turnstile-token="form.turnstile_token"
              />
            </NFormItem>
          </div>
        </div>
      </NForm>
    </div>
    <div class="edit-actions">
      <NButton @click="close">取消</NButton>
      <NButton type="primary" :loading="saving" @click="submit">保存修改</NButton>
    </div>
  </NModal>
</template>

<style scoped>
.edit-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.edit-alert {
  padding: 10px 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  color: #1d4ed8;
}

.edit-section {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
}

.edit-section-head {
  margin-bottom: 14px;
}

.edit-section-head h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}

.edit-section-head p {
  margin: 4px 0 0;
  color: #6b7280;
}

.edit-section-head.compact {
  margin-bottom: 8px;
}

.edit-grid {
  display: grid;
  gap: 12px;
}

.edit-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.edit-grid.single-col {
  grid-template-columns: 1fr;
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

.upload-tip {
  margin-top: 6px;
  color: #6b7280;
  font-size: 12px;
}

.captcha-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.captcha-img {
  height: 34px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
}

@media (max-width: 760px) {
  .edit-grid.two-col {
    grid-template-columns: 1fr;
  }
}
</style>
