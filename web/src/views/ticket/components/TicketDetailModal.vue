<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { NButton, NEmpty, NModal, NSpin, NTag } from 'naive-ui'
import CrudModal from '@/components/table/CrudModal.vue'
import api from '@/api'
import { isImageName, sanitizeHtml } from '@/utils'
import { mapTicketActionText, ticketStatusTextMap, ticketStatusTypeMap } from './ticket-meta'

defineEmits(['update:visible'])

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  ticket: {
    type: Object,
    default() {
      return {}
    },
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const attachments = computed(() => props.ticket?.attachments || [])
const imageAttachments = computed(() => attachments.value.filter((item) => isImageName(item.origin_name || item.file_path || '')))
const imagePreviewMap = ref({})
const descriptionImagePreviewVisible = ref(false)
const descriptionImagePreviewSrc = ref('')
const descriptionImagePreviewAlt = ref('')
const safeDescription = computed(() => sanitizeHtml(props.ticket?.description || '-'))
const hasActions = computed(() => Array.isArray(props.ticket?.actions) && props.ticket.actions.length > 0)

function revokeImagePreviewUrls() {
  Object.values(imagePreviewMap.value || {}).forEach((url) => {
    if (url) URL.revokeObjectURL(url)
  })
}

function getImagePreviewUrl(item) {
  return imagePreviewMap.value[item.id] || ''
}

function closeDescriptionImagePreview() {
  descriptionImagePreviewVisible.value = false
  descriptionImagePreviewSrc.value = ''
  descriptionImagePreviewAlt.value = ''
}

function openDescriptionImagePreview(event) {
  const target = event?.target
  if (!(target instanceof HTMLImageElement)) return
  const src = target.currentSrc || target.src
  if (!src) return
  event.preventDefault()
  descriptionImagePreviewSrc.value = src
  descriptionImagePreviewAlt.value = target.alt || '问题描述图片'
  descriptionImagePreviewVisible.value = true
}

function openTimelineImagePreview(event) {
  openDescriptionImagePreview(event)
}

watch(
  () => [props.visible, props.ticket?.id, imageAttachments.value.length],
  async ([visible]) => {
    if (!visible) {
      revokeImagePreviewUrls()
      imagePreviewMap.value = {}
      closeDescriptionImagePreview()
      return
    }
    revokeImagePreviewUrls()
    const nextMap = {}
    for (const item of imageAttachments.value) {
      try {
        const res = await api.downloadTicketAttachment({ attachment_id: item.id })
        const blob = res instanceof Blob ? res : new Blob([res])
        nextMap[item.id] = URL.createObjectURL(blob)
      } catch {
        nextMap[item.id] = ''
      }
    }
    imagePreviewMap.value = nextMap
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  revokeImagePreviewUrls()
  imagePreviewMap.value = {}
})

async function openAttachment(item) {
  if (!item?.id) return
  const res = await api.downloadTicketAttachment({ attachment_id: item.id })
  const blob = res instanceof Blob ? res : new Blob([res])
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = item.origin_name || `attachment-${item.id}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

async function copyImage(item) {
  const res = await api.downloadTicketAttachment({ attachment_id: item.id })
  const blob = res instanceof Blob ? res : new Blob([res])
  if (!blob.type.startsWith('image/')) {
    $message.warning('仅支持复制图片附件')
    return
  }
  await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })])
  $message.success('图片已复制')
}

function renderActionContent(item) {
  if (!item) return '-'
  if (item.action === 'finish' && props.ticket?.root_cause) {
    const base = item.comment?.trim() || '处理完成'
    return sanitizeHtml(`${base}（根因：${props.ticket.root_cause}）`)
  }
  return sanitizeHtml(item.comment || '-')
}

function isRejectAction(action) {
  return action === 'cs_reject' || action === 'tech_reject'
}

function getActionIcon(action) {
  if (action === 'finish') return 'finish'
  if (action === 'submit' || action === 'resubmit') return 'submit'
  if (action === 'tech_start') return 'handle'
  if (isRejectAction(action)) return 'reject'
  return 'pass'
}

function getActionIconClass(action) {
  if (isRejectAction(action)) return 'is-reject'
  if (action === 'finish') return 'is-finish'
  if (action === 'submit' || action === 'resubmit') return 'is-submit'
  if (action === 'tech_start') return 'is-handle'
  return 'is-pass'
}

</script>

<template>
  <CrudModal :visible="visible" title="工单详情" width="min(96vw, 1280px)" :show-footer="false" @update:visible="$emit('update:visible', $event)">
    <div class="detail-header">
      <div>
        <div class="detail-no">{{ ticket.ticket_no }}</div>
        <div class="detail-title">{{ ticket.title }}</div>
      </div>
      <NTag :type="ticketStatusTypeMap[ticket.status] || 'default'">{{ ticketStatusTextMap[ticket.status] || '-' }}</NTag>
    </div>

    <div class="detail-grid">
      <div class="detail-card">
        <span>项目名称</span>
        <strong>{{ ticket.company_name || '-' }}</strong>
      </div>
      <div class="detail-card">
        <span>联系人</span>
        <strong>{{ ticket.contact_name || '-' }}</strong>
      </div>
      <div class="detail-card">
        <span>联系方式</span>
        <strong>{{ ticket.phone || '-' }}</strong>
      </div>
      <div class="detail-card">
        <span>项目阶段</span>
        <strong>{{ ticket.project_phase || '-' }}</strong>
      </div>
      <div class="detail-card">
        <span>问题分类</span>
        <strong>{{ ticket.category || '-' }}</strong>
      </div>
      <div class="detail-card">
        <span>创建时间</span>
        <strong>{{ ticket.created_at || '-' }}</strong>
      </div>
      <div class="detail-card">
        <span>提交人</span>
        <strong>{{ ticket.submitter_name || ticket.submitter_id || '-' }}</strong>
      </div>
      <div class="detail-card">
        <span>附件数量</span>
        <strong>{{ ticket.attachment_count ?? attachments.length }}</strong>
      </div>
      <div class="detail-card">
        <span>客服审核人</span>
        <strong>{{ ticket.reviewer_name || ticket.reviewer_id || '-' }}</strong>
      </div>
      <div class="detail-card">
        <span>指派技术</span>
        <strong>{{ ticket.tech_name || ticket.tech_id || '-' }}</strong>
      </div>
      <div class="detail-card">
        <span>问题根因</span>
        <strong>{{ ticket.root_cause || '-' }}</strong>
      </div>
      <div class="detail-card detail-card-wide">
        <span>完成时间</span>
        <strong>{{ ticket.finished_at || '-' }}</strong>
      </div>
    </div>

    <div class="description-card">
      <div class="section-title">问题描述</div>
      <div v-if="loading" class="detail-loading">
        <NSpin size="small" />
        <span>详情加载中...</span>
      </div>
      <div v-else class="description-content" @click="openDescriptionImagePreview" v-html="safeDescription"></div>
    </div>

    <div class="detail-secondary-grid">
    <div class="attachment-card">
      <div class="section-title">附件列表</div>
      <div v-if="loading" class="detail-loading">
        <NSpin size="small" />
        <span>附件加载中...</span>
      </div>
      <div v-else-if="imageAttachments.length" class="image-preview-grid">
        <a
          v-for="item in imageAttachments"
          :key="`img-${item.id}`"
          :href="getImagePreviewUrl(item)"
          target="_blank"
          rel="noopener"
          class="image-preview-item"
        >
          <img :src="getImagePreviewUrl(item)" :alt="item.origin_name || `image-${item.id}`" />
        </a>
      </div>
      <div v-if="!loading && attachments.length" class="attachment-list">
        <div v-for="item in attachments" :key="item.id" class="attachment-item">
          <div>
            <div class="attachment-name">{{ item.origin_name || item.file_path }}</div>
            <div class="attachment-meta">{{ item.mime_type || 'application/octet-stream' }} / {{ item.file_size || 0 }} bytes</div>
          </div>
          <div class="attachment-actions">
            <NButton v-if="isImageName(item.origin_name || item.file_path || '')" size="small" type="info" quaternary @click="copyImage(item)">复制图片</NButton>
            <NButton size="small" type="primary" quaternary @click="openAttachment(item)">下载</NButton>
          </div>
        </div>
      </div>
      <NEmpty v-else-if="!loading" description="暂无附件" size="small" />
    </div>

    <div class="timeline-card">
      <div class="section-title">流转日志</div>
      <div v-if="loading" class="detail-loading">
        <NSpin size="small" />
        <span>流转日志加载中...</span>
      </div>
      <n-timeline v-else-if="hasActions" class="ticket-timeline">
        <n-timeline-item
          v-for="item in ticket.actions || []"
          :key="item.id"
          :title="mapTicketActionText(item.action)"
          :type="isRejectAction(item.action) ? 'error' : 'success'"
        >
          <template #icon>
            <span class="timeline-icon" :class="getActionIconClass(item.action)">
              <svg v-if="getActionIcon(item.action) === 'finish'" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12.5l3.2 3.2L14 10" />
                <path d="M10 12.5l3.2 3.2L19 10" />
              </svg>
              <svg v-else-if="getActionIcon(item.action) === 'submit'" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="12" r="3.5" fill="currentColor" stroke="none" />
              </svg>
              <svg v-else-if="getActionIcon(item.action) === 'handle'" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M16.5 7.5A6 6 0 1 0 18 12" />
                <path d="M16.5 4.5v3h-3" />
              </svg>
              <svg v-else-if="getActionIcon(item.action) === 'reject'" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M8 8l8 8" />
                <path d="M16 8l-8 8" />
              </svg>
              <svg v-else viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 12.5l4 4L18 8.5" />
              </svg>
            </span>
          </template>
          <div class="timeline-content">
            <div class="timeline-comment" @dblclick="openTimelineImagePreview" v-html="renderActionContent(item)"></div>
            <div class="timeline-meta">操作者：{{ item.operator_display || item.operator_name || item.operator_id || '-' }}</div>
            <div v-if="item.created_at" class="timeline-meta">时间：{{ item.created_at }}</div>
          </div>
        </n-timeline-item>
      </n-timeline>
      <NEmpty v-else description="暂无流转日志" size="small" />
    </div>
    </div>
  </CrudModal>
  <NModal v-model:show="descriptionImagePreviewVisible" preset="card" title="图片预览" class="description-image-modal">
    <div class="description-image-preview">
      <img :src="descriptionImagePreviewSrc" :alt="descriptionImagePreviewAlt" />
    </div>
  </NModal>
</template>

<style scoped>
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.detail-no {
  color: #9ca3af;
  font-size: 13px;
}

.detail-title {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 700;
  color: #111827;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.detail-card,
.description-card,
.attachment-card,
.timeline-card {
  padding: 16px;
  border: 1px solid #eceff5;
  border-radius: 18px;
  background: #fafbfd;
}

.detail-card span,
.section-title {
  display: block;
  color: #6b7280;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.detail-card strong {
  display: block;
  margin-top: 8px;
  color: #111827;
  font-size: 15px;
}

.detail-card-wide {
  grid-column: span 1;
}

.description-card,
.attachment-card,
.timeline-card {
  margin-top: 10px;
}

.detail-secondary-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.1fr);
  gap: 12px;
  align-items: start;
}

.detail-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 72px;
  margin-top: 10px;
  color: #6b7280;
  font-size: 13px;
}

.description-content {
  margin-top: 10px;
  color: #374151;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: hidden;
}

.description-content :deep(img) {
  display: inline-block;
  max-width: min(180px, 100%);
  max-height: 140px;
  width: auto;
  height: auto;
  margin: 8px 8px 8px 0;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  object-fit: contain;
  vertical-align: top;
  cursor: zoom-in;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
}

.description-content :deep(p) {
  max-width: 100%;
}

.description-content :deep(*) {
  max-width: 100%;
}

.description-image-modal {
  width: min(92vw, 960px);
}

.description-image-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  max-height: 78vh;
  overflow: auto;
  background: #0f172a;
  border-radius: 8px;
  padding: 12px;
}

.description-image-preview img {
  max-width: 100%;
  max-height: 74vh;
  object-fit: contain;
  display: block;
}

.ticket-timeline {
  margin-top: 10px;
}

.timeline-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.timeline-comment {
  color: #374151;
  line-height: 1.7;
  word-break: break-word;
}

.timeline-comment :deep(img) {
  max-width: min(100%, 420px);
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  display: block;
  margin-top: 6px;
  cursor: zoom-in;
}

.timeline-meta {
  color: #6b7280;
  font-size: 12px;
}

.timeline-icon {
  display: inline-flex;
  width: 26px;
  height: 26px;
  min-width: 26px;
  min-height: 26px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  color: #fff;
  line-height: 1;
}

.timeline-icon svg {
  width: 16px;
  height: 16px;
  display: block;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
  fill: none;
}

.timeline-icon.is-pass {
  background: #16a34a;
  animation: timelinePop 0.28s ease-out, timelineGlowPass 1.3s ease-out;
}

.timeline-icon.is-finish {
  background: #0ea5e9;
  animation: timelinePop 0.28s ease-out, timelineGlowFinish 1.3s ease-out;
}

.timeline-icon.is-submit {
  background: #6b7280;
  animation: timelinePop 0.28s ease-out, timelineGlowSubmit 1.3s ease-out;
}

.timeline-icon.is-handle {
  background: #f59e0b;
  animation: timelinePop 0.28s ease-out, timelineGlowHandle 1.3s ease-out;
}

.timeline-icon.is-handle svg {
  animation: timelineSpinIn 0.42s ease-out;
}

.timeline-icon.is-reject {
  background: #dc2626;
  animation: timelinePop 0.28s ease-out, timelineGlowReject 1.3s ease-out;
}

@keyframes timelinePop {
  0% {
    transform: scale(0.72);
    opacity: 0.68;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes timelineGlowPass {
  0% {
    box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.45);
  }
  100% {
    box-shadow: 0 0 0 10px rgba(22, 163, 74, 0);
  }
}

@keyframes timelineGlowReject {
  0% {
    box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.45);
  }
  100% {
    box-shadow: 0 0 0 10px rgba(220, 38, 38, 0);
  }
}

@keyframes timelineGlowFinish {
  0% {
    box-shadow: 0 0 0 0 rgba(14, 165, 233, 0.45);
  }
  100% {
    box-shadow: 0 0 0 10px rgba(14, 165, 233, 0);
  }
}

@keyframes timelineGlowSubmit {
  0% {
    box-shadow: 0 0 0 0 rgba(107, 114, 128, 0.45);
  }
  100% {
    box-shadow: 0 0 0 10px rgba(107, 114, 128, 0);
  }
}

@keyframes timelineGlowHandle {
  0% {
    box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.45);
  }
  100% {
    box-shadow: 0 0 0 10px rgba(245, 158, 11, 0);
  }
}

@keyframes timelineSpinIn {
  0% {
    transform: rotate(-120deg) scale(0.78);
    opacity: 0.45;
  }
  100% {
    transform: rotate(0deg) scale(1);
    opacity: 1;
  }
}

.attachment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.attachment-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #e5e7eb;
}

.attachment-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.image-preview-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
}

.image-preview-item {
  display: block;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #fff;
}

.image-preview-item img {
  width: 100%;
  height: 120px;
  object-fit: cover;
  display: block;
}

.attachment-name {
  color: #111827;
  font-weight: 600;
}

.attachment-meta {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
}

@media (max-width: 960px) {
  .detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .detail-secondary-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .detail-card-wide {
    grid-column: span 1;
  }
}

@media (max-width: 640px) {
  .detail-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
