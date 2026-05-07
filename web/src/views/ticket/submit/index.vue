<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NForm, NFormItem, NInput, NSelect, NUpload, NAlert, NSpace, NTag } from 'naive-ui'
import { getToken, isImageName, isNullOrWhitespace } from '@/utils'
import api from '@/api'
import RichTextEditor from '@/components/editor/RichTextEditor.vue'

defineOptions({ name: '提交工单' })

const isAuthed = computed(() => !isNullOrWhitespace(getToken()))
const pageTitle = computed(() => (isAuthed.value ? '提交工单' : '游客工单提交'))
const pageDesc = computed(() =>
  isAuthed.value
    ? '请尽量详细描述问题，客服审核后会转技术处理。'
    : '无需登录即可提交工单，我们会通过你填写的联系方式反馈处理进度。'
)
const router = useRouter()

const formRef = ref(null)
const uploadLoading = ref(false)
const submitting = ref(false)
const captchaImage = ref('')
const uploadedAttachmentIds = ref([])
const uploadFileList = ref([])
const attachmentAccept = ref('.zip,.rar,.png,.jpg,.gif')
const projectPhaseOptions = ref([
  { label: '售前', value: '售前' },
  { label: '实施', value: '实施' },
  { label: '售后', value: '售后' },
])
const descriptionTemplateOptions = ref([])

function buildTemplateLabel(value, index) {
  const plainText = String(value || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return plainText ? `模板${index + 1} · ${plainText.slice(0, 12)}` : `模板${index + 1}`
}

const form = ref({
  company_name: '',
  contact_name: '',
  email: '',
  phone: '',
  project_phase: '',
  category: '',
  title: '',
  description: '',
  captcha_id: '',
  captcha_code: '',
})

const categoryOptions = ref([
  { label: '登录问题', value: '登录问题' },
  { label: '权限问题', value: '权限问题' },
  { label: '系统异常', value: '系统异常' },
  { label: '其他', value: '其他' },
])

const rules = {
  company_name: { required: true, message: '请输入公司名称', trigger: ['blur', 'input'] },
  contact_name: { required: true, message: '请输入联系人', trigger: ['blur', 'input'] },
  email: { required: true, message: '请输入邮箱', trigger: ['blur', 'input'] },
  phone: { required: true, message: '请输入手机号', trigger: ['blur', 'input'] },
  project_phase: { required: true, message: '请选择项目阶段', trigger: ['change'] },
  category: { required: true, message: '请选择分类', trigger: ['change'] },
  title: { required: true, message: '请输入标题', trigger: ['blur', 'input'] },
  description: { required: true, message: '请输入问题描述', trigger: ['blur', 'input'] },
  captcha_code: { required: true, message: '请输入验证码', trigger: ['blur', 'input'] },
}

watch(descriptionTemplateOptions, (options) => {
  if (!options.length) return
  if (!form.value.description || !form.value.description.trim() || options.every((item) => item.value !== form.value.description)) {
    form.value.description = options[0].value
  }
})

onMounted(async () => {
  await Promise.all([fetchPublicConfig(), fetchCaptcha()])
  if (isAuthed.value) {
    await fetchPrefill()
  }
})

async function fetchPublicConfig() {
  try {
    const res = await api.getPublicConfig()
    const projectPhases = res.data?.ticket_project_phases || []
    const categories = res.data?.ticket_categories || []
    const descriptionTemplates = res.data?.ticket_description_templates || []
    const attachmentExtensions = res.data?.ticket_attachment_extensions || []
    if (projectPhases.length > 0) {
      projectPhaseOptions.value = projectPhases.map((item) => ({ label: item, value: item }))
      if (!form.value.project_phase) {
        form.value.project_phase = projectPhaseOptions.value[0].value
      }
    }
    if (categories.length > 0) {
      categoryOptions.value = categories.map((item) => ({ label: item, value: item }))
      if (!form.value.category) {
        form.value.category = categoryOptions.value[0].value
      }
    }
    descriptionTemplateOptions.value = descriptionTemplates.map((item, index) => ({
      label: buildTemplateLabel(item, index),
      value: item,
    }))
    if (attachmentExtensions.length > 0) {
      attachmentAccept.value = attachmentExtensions.map((item) => `.${String(item).replace(/^\./, '')}`).join(',')
    }
  } catch (error) {
    // ignore config fetch errors
  }
}

async function fetchCaptcha() {
  const res = await api.getCaptcha()
  form.value.captcha_id = res.data.captcha_id
  captchaImage.value = `data:image/png;base64,${res.data.image_base64}`
}

async function fetchPrefill() {
  try {
    const res = await api.getTicketPrefill()
    form.value.company_name = res.data?.company_name || form.value.company_name
    form.value.contact_name = res.data?.contact_name || form.value.contact_name
    form.value.email = res.data?.email || form.value.email
    form.value.phone = res.data?.phone || form.value.phone
  } catch (error) {
    // ignore prefill errors
  }
}

function quickFill() {
  fetchPrefill()
}

function applyDescriptionTemplate(value) {
  if (!value) return
  form.value.description = value
}

function buildObjectUrl(rawFile) {
  if (!rawFile) return ''
  try {
    return URL.createObjectURL(rawFile)
  } catch {
    return ''
  }
}

async function uploadSingleFile(rawFile, targetFile = null) {
  const res = isAuthed.value ? await api.uploadTicketAttachment(rawFile) : await api.uploadPublicTicketAttachment(rawFile)
  const attachmentId = Number(res?.data?.id || 0)
  if (!attachmentId) throw new Error('上传成功但未返回附件ID')
  if (targetFile) {
    targetFile.attachmentId = attachmentId
    if (isImageName(targetFile.name)) {
      targetFile.url = buildObjectUrl(rawFile)
    }
  }
  uploadedAttachmentIds.value = [...new Set([...uploadedAttachmentIds.value, attachmentId])]
}

async function customUpload({ file, onFinish, onError }) {
  try {
    uploadLoading.value = true
    await uploadSingleFile(file.file, file)
    onFinish()
  } catch (error) {
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
    if (uploadFileList.value.length >= 5) break
    const fileName = rawFile.name || `pasted-${Date.now()}.png`
    const uploadFile = {
      id: `${Date.now()}-${Math.random()}`,
      name: fileName,
      status: 'uploading',
      file: rawFile,
      url: buildObjectUrl(rawFile),
    }
    uploadFileList.value = [...uploadFileList.value, uploadFile]
    try {
      uploadLoading.value = true
      await uploadSingleFile(rawFile, uploadFile)
      uploadFile.status = 'finished'
    } catch {
      uploadFile.status = 'error'
    } finally {
      uploadLoading.value = false
    }
  }
}

function handleRemove({ file }) {
  const attachmentId = Number(file?.attachmentId || 0)
  if (attachmentId > 0) {
    uploadedAttachmentIds.value = uploadedAttachmentIds.value.filter((id) => id !== attachmentId)
  }
}

function resetForm() {
  const keepCaptchaId = form.value.captcha_id
  form.value = {
    company_name: '',
    contact_name: '',
    email: '',
    phone: '',
    project_phase: projectPhaseOptions.value[0]?.value || '',
    category: categoryOptions.value[0]?.value || '',
    title: '',
    description: descriptionTemplateOptions.value[0]?.value || '',
    captcha_id: keepCaptchaId,
    captcha_code: '',
  }
  uploadedAttachmentIds.value = []
  uploadFileList.value = []
}

function submit() {
  formRef.value?.validate(async (err) => {
    if (err) return
    try {
      submitting.value = true
      const payload = {
        ...form.value,
        attachment_ids: [...uploadedAttachmentIds.value],
      }
      if (isAuthed.value) {
        await api.createTicket(payload)
      } else {
        await api.createPublicTicket(payload)
      }
      $message.success('工单已提交，我们会尽快处理并反馈进度')
      if (isAuthed.value) {
        await router.push({ path: '/ticket/my', query: { status: 'pending_review' } })
        return
      }
      resetForm()
      await fetchCaptcha()
      if (isAuthed.value) {
        await fetchPrefill()
      }
    } catch (error) {
      await fetchCaptcha()
    } finally {
      submitting.value = false
    }
  })
}
</script>

<template>
  <div class="ticket-submit-page">
    <div class="hero">
      <div class="hero-left">
        <div class="eyebrow">Support Desk</div>
        <h2>{{ pageTitle }}</h2>
        <p>{{ pageDesc }}</p>
        <NSpace class="hero-tags">
          <NTag class="hero-tag" :bordered="false">客服审核</NTag>
          <NTag class="hero-tag" :bordered="false">技术处理</NTag>
          <NTag class="hero-tag" :bordered="false">状态可追踪</NTag>
        </NSpace>
      </div>
      <div class="hero-right">
        <div class="hero-stat-card">
          <span class="stat-label">建议内容</span>
          <strong>现象 + 复现 + 影响</strong>
          <span class="stat-tip">越完整，处理越快</span>
        </div>
        <div class="orb orb-a"></div>
        <div class="orb orb-b"></div>
      </div>
    </div>

    <div class="content-grid">
      <div class="form-shell">
        <NAlert type="info" class="mb-16">
          提交后我们将按工单状态推进处理。请确保邮箱和手机号可联系。
        </NAlert>

        <NForm ref="formRef" :model="form" :rules="rules" :label-width="100" label-placement="left">
          <div class="section-card">
            <div class="section-head">
              <div>
                <h3>联系信息</h3>
                <p>用于客服回访、结果通知与工单状态同步。</p>
              </div>
              <NButton v-if="isAuthed" quaternary type="primary" @click="quickFill">一键填充</NButton>
            </div>
            <div class="form-grid two-col">
              <NFormItem label="公司名称" path="company_name">
                <NInput v-model:value="form.company_name" placeholder="请输入公司名称" />
              </NFormItem>
              <NFormItem label="联系人" path="contact_name">
                <NInput v-model:value="form.contact_name" placeholder="请输入联系人" />
              </NFormItem>
              <NFormItem label="邮箱" path="email">
                <NInput v-model:value="form.email" placeholder="请输入邮箱" />
              </NFormItem>
              <NFormItem label="手机号" path="phone">
                <NInput v-model:value="form.phone" placeholder="请输入手机号" />
              </NFormItem>
            </div>
          </div>

          <div class="section-card">
            <div class="section-head compact">
              <div>
                <h3>问题内容</h3>
                <p>清楚描述问题场景，能大幅减少来回确认时间。</p>
              </div>
            </div>
            <div class="form-grid single-col">
              <NFormItem label="项目阶段" path="project_phase">
                <NSelect v-model:value="form.project_phase" :options="projectPhaseOptions" placeholder="请选择项目阶段" />
              </NFormItem>
              <NFormItem label="问题分类" path="category">
                <NSelect v-model:value="form.category" :options="categoryOptions" placeholder="请选择分类" />
              </NFormItem>
              <NFormItem label="问题标题" path="title">
                <NInput v-model:value="form.title" placeholder="例如：用户导入报错 500" />
              </NFormItem>
              <NFormItem label="问题描述" path="description">
                <div class="editor-host">
                  <div v-if="descriptionTemplateOptions.length" class="template-toolbar">
                    <span class="template-label">描述模板</span>
                    <NSpace size="small">
                      <NButton
                        v-for="item in descriptionTemplateOptions"
                        :key="item.value"
                        size="small"
                        secondary
                        @click="applyDescriptionTemplate(item.value)"
                      >
                        {{ item.label }}
                      </NButton>
                    </NSpace>
                  </div>
                  <RichTextEditor
                    v-model="form.description"
                    placeholder="建议包含问题现象、复现步骤、影响范围"
                    :min-height="240"
                    :max-height="520"
                  />
                </div>
              </NFormItem>
            </div>
          </div>

          <div class="section-card">
            <div class="section-head compact">
              <div>
                <h3>附件与校验</h3>
                <p>截图、日志、报错文件有助于快速定位问题。</p>
              </div>
            </div>
            <div class="form-grid single-col">
              <NFormItem label="附件">
                <div class="upload-box" @paste="handlePasteUpload">
                  <NUpload
                    v-model:file-list="uploadFileList"
                    list-type="image-card"
                    :custom-request="customUpload"
                    :max="5"
                    :accept="attachmentAccept"
                    @remove="handleRemove"
                  >
                    <NButton class="upload-btn" :loading="uploadLoading">上传附件</NButton>
                  </NUpload>
                  <span class="upload-tip">支持最多 5 个附件，支持粘贴图片上传，当前允许类型：{{ attachmentAccept }}。</span>
                </div>
              </NFormItem>
              <NFormItem label="验证码" path="captcha_code">
                <div class="captcha-row">
                  <NInput v-model:value="form.captcha_code" placeholder="请输入验证码" style="width: 180px" />
                  <img :src="captchaImage" alt="captcha" class="captcha-img" @click="fetchCaptcha" />
                  <NButton text type="primary" @click="fetchCaptcha">换一张</NButton>
                </div>
              </NFormItem>
            </div>
          </div>

          <NFormItem>
            <div class="submit-row">
              <NButton class="submit-btn" type="primary" :loading="submitting" @click="submit">提交工单</NButton>
              <span class="submit-tip">提交后将进入客服审核流程，处理进度可在工单中心查看。</span>
            </div>
          </NFormItem>
        </NForm>
      </div>

      <aside class="side-panel">
        <div class="panel-card highlight">
          <div class="panel-kicker">填写建议</div>
          <h3>提高处理效率的 3 个关键点</h3>
          <ul>
            <li>写清问题现象，例如报错提示、出现频率、是否必现。</li>
            <li>补充复现步骤，例如谁操作、在哪个页面、点了什么按钮。</li>
            <li>说明影响范围，例如是否影响全部用户、是否阻塞业务。</li>
          </ul>
        </div>

        <div class="panel-card process-card">
          <div class="panel-kicker">处理流程</div>
          <div class="step-item">
            <span class="step-index">01</span>
            <div>
              <strong>提交工单</strong>
              <p>提交问题内容与附件，系统立即生成编号。</p>
            </div>
          </div>
          <div class="step-item">
            <span class="step-index">02</span>
            <div>
              <strong>客服审核</strong>
              <p>确认问题归类与信息完整度，不完整会回退补充。</p>
            </div>
          </div>
          <div class="step-item">
            <span class="step-index">03</span>
            <div>
              <strong>技术处理</strong>
              <p>技术同学跟进分析与修复，状态全程可追踪。</p>
            </div>
          </div>
        </div>

        <div class="panel-card checklist-card">
          <div class="panel-kicker">提交前确认</div>
          <NSpace vertical size="small">
            <NTag class="check-tag" :bordered="false">联系方式可用</NTag>
            <NTag class="check-tag" :bordered="false">问题标题明确</NTag>
            <NTag class="check-tag" :bordered="false">附件已补充</NTag>
          </NSpace>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.ticket-submit-page {
  min-height: calc(100vh - 90px);
  padding: 20px;
  box-sizing: border-box;
  overflow-y: auto;
  max-height: calc(100vh - 90px);
  background: #f8fafc;
}

.template-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.template-label {
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
}

.hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-radius: 14px;
  padding: 18px 20px;
  background: #fff;
  color: #111827;
  border: 1px solid #e5e7eb;
  box-shadow: none;
  overflow: hidden;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  margin-bottom: 10px;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-left h2 {
  margin: 0;
  font-size: 30px;
  line-height: 1.2;
}

.hero-left p {
  max-width: 560px;
  margin: 10px 0 16px;
  opacity: 0.92;
  font-size: 15px;
}

.hero-tag {
  color: #fff;
  background: rgba(255, 255, 255, 0.14);
}

.hero-tags {
  flex-wrap: wrap;
}

.submit-btn {
  min-width: 136px;
  height: 42px;
  border-radius: 999px;
}

.submit-btn :deep(.n-button__border),
.submit-btn :deep(.n-button__state-border) {
  border: none;
}

.submit-btn :deep(.n-button__color) {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--primary-color) 72%, #7a2a0f 28%) 0%,
    color-mix(in srgb, var(--primary-color) 64%, #374151 36%) 55%,
    color-mix(in srgb, var(--primary-color-hover) 58%, #ffffff 42%) 100%
  );
}

.submit-btn:hover :deep(.n-button__color) {
  filter: brightness(1.02);
}

.hero-right {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  width: 260px;
  height: 120px;
}

.hero-stat-card {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.12);
}

.hero-stat-card strong {
  font-size: 16px;
}

.stat-label,
.stat-tip {
  font-size: 12px;
  opacity: 0.88;
}

.orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(1px);
}

.orb-a {
  width: 120px;
  height: 120px;
  right: -18px;
  top: -18px;
  background: rgba(255, 255, 255, 0.2);
}

.orb-b {
  width: 70px;
  height: 70px;
  right: 70px;
  top: 34px;
  background: rgba(255, 255, 255, 0.26);
}

.content-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 20px;
  align-items: start;
}

.form-shell {
  border-radius: 18px;
  padding: 24px;
  background: #fff;
  box-shadow: 0 10px 26px rgba(9, 30, 66, 0.08);
}

.section-card {
  margin-bottom: 18px;
  padding: 18px 18px 6px;
  border: 1px solid #eef2f7;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.section-head h3 {
  margin: 0;
  font-size: 17px;
  color: #111827;
}

.section-head p {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.section-head.compact {
  margin-bottom: 10px;
}

.form-grid {
  display: grid;
  gap: 2px 18px;
}

.form-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.form-grid.single-col {
  grid-template-columns: minmax(0, 1fr);
}

.captcha-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.captcha-img {
  height: 40px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid #e5e7eb;
}

.editor-host {
  width: 100%;
}

.upload-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.upload-btn {
  width: fit-content;
}

.upload-tip,
.submit-tip {
  color: #6b7280;
  font-size: 13px;
}

.submit-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.side-panel {
  position: sticky;
  top: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-card {
  padding: 18px;
  border-radius: 18px;
  background: #fff;
  border: 1px solid #eef2f7;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.panel-card h3 {
  margin: 0 0 12px;
  font-size: 18px;
  color: #111827;
}

.panel-kicker {
  margin-bottom: 8px;
  color: #c2410c;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.highlight {
  background:
    radial-gradient(circle at top right, rgba(251, 146, 60, 0.14), transparent 35%),
    linear-gradient(180deg, #fffaf5 0%, #ffffff 100%);
}

.highlight ul {
  margin: 0;
  padding-left: 18px;
  color: #4b5563;
  line-height: 1.8;
}

.step-item {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.step-item:last-child {
  margin-bottom: 0;
}

.step-item p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
}

.step-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: #fef2f2;
  color: #c2410c;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.check-tag {
  width: fit-content;
  color: #374151;
  background: #f3f4f6;
}

@media (max-width: 900px) {
  .ticket-submit-page {
    padding: 12px;
  }

  .hero {
    padding: 18px;
  }

  .hero-right {
    display: none;
  }

  .content-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .side-panel {
    position: static;
  }

  .form-shell {
    padding: 16px;
  }

  .form-grid.two-col {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
