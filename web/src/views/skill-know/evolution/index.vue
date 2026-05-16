<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { NButton, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '自进化报告' })

const loading = ref(false)
const running = ref(false)
const detailLoading = ref(false)
const savingSettings = ref(false)
const gapActionId = ref('')
const candidateActionId = ref('')
const gapModalVisible = ref(false)
const candidateModalVisible = ref(false)
const selectedGap = ref(null)
const goldenForm = ref({
  expected_document_id: null,
  expected_section_id: null,
  expected_heading_contains: '',
})
const candidateForm = ref({
  title: '',
  draft_answer: '',
})
const reports = ref([])
const gaps = ref([])
const candidates = ref([])
const selected = ref(null)
const settings = ref({
  enabled: true,
  run_at: '02:10',
  top_k: 8,
})

const latestReport = computed(() => selected.value || reports.value[0] || null)
const metrics = computed(() => latestReport.value?.metrics || {})
const lowScoreQuestions = computed(() => selected.value?.low_score_questions || [])
const nextActions = computed(() => selected.value?.next_actions || [])
const evalRows = computed(() => selected.value?.eval_result?.results || [])
const pendingGapCount = computed(() => gaps.value.filter((item) => item.status === 'pending').length)
const pendingCandidateCount = computed(() => candidates.value.filter((item) => item.status === 'pending').length)

const reportColumns = [
  { title: '报告时间', key: 'started_at', minWidth: 190, ellipsis: { tooltip: true }, render: (row) => formatDate(row.started_at) },
  { title: '状态', key: 'status', width: 100, render: (row) => statusTag(row.status) },
  { title: 'Top1', key: 'top1_accuracy', width: 90, render: (row) => formatPercent(row.metrics?.top1_accuracy) },
  { title: 'Top3', key: 'top3_accuracy', width: 90, render: (row) => formatPercent(row.metrics?.top3_accuracy) },
  { title: 'TopK', key: 'top_k_accuracy', width: 90, render: (row) => formatPercent(row.metrics?.top_k_accuracy) },
  { title: '低分', key: 'low_score_count', width: 80, render: (row) => row.low_score_count ?? 0 },
  {
    title: '操作',
    key: 'actions',
    width: 96,
    fixed: 'right',
    render: (row) =>
      h(
        NButton,
        { size: 'small', type: 'primary', secondary: true, onClick: () => openReport(row.report_id) },
        { default: () => '查看' },
      ),
  },
]

const evalColumns = [
  { title: '问题', key: 'question', minWidth: 260, ellipsis: { tooltip: true } },
  { title: '命中排名', key: 'matched_rank', width: 100, render: (row) => row.matched_rank || '-' },
  { title: 'Top1', key: 'top1_hit', width: 90, render: (row) => hitTag(row.top1_hit) },
  { title: 'Top3', key: 'top3_hit', width: 90, render: (row) => hitTag(row.top3_hit) },
  { title: '耗时', key: 'latency_ms', width: 100, render: (row) => `${row.latency_ms || 0}ms` },
]

const gapColumns = [
  { title: '知识缺口', key: 'question', minWidth: 260, ellipsis: { tooltip: true } },
  { title: '状态', key: 'status', width: 90, render: (row) => gapStatusTag(row.status) },
  { title: '次数', key: 'occurrences', width: 80, render: (row) => row.occurrences || 0 },
  { title: '优先级', key: 'priority', width: 90, render: (row) => row.priority || 0 },
  { title: '更新时间', key: 'updated_at', width: 180, render: (row) => formatDate(row.updated_at) },
  {
    title: '操作',
    key: 'actions',
    width: 330,
    fixed: 'right',
    render: (row) =>
      h('div', { class: 'row-actions' }, [
        h(
          NButton,
          {
            size: 'small',
            type: 'primary',
            secondary: true,
            disabled: row.status === 'resolved',
            loading: gapActionId.value === `${row.id}:candidate`,
            onClick: () => openCandidateModal(row),
          },
          { default: () => '生成候选' },
        ),
        h(
          NButton,
          {
            size: 'small',
            secondary: true,
            disabled: row.status === 'resolved',
            loading: gapActionId.value === `${row.id}:golden`,
            onClick: () => openGapConvertModal(row),
          },
          { default: () => '转黄金问题' },
        ),
        row.status === 'ignored'
          ? h(
              NButton,
              {
                size: 'small',
                secondary: true,
                loading: gapActionId.value === `${row.id}:pending`,
                onClick: () => updateGapStatus(row, 'pending'),
              },
              { default: () => '恢复' },
            )
          : h(
              NButton,
              {
                size: 'small',
                secondary: true,
                disabled: row.status === 'resolved',
                loading: gapActionId.value === `${row.id}:ignored`,
                onClick: () => updateGapStatus(row, 'ignored'),
              },
              { default: () => '忽略' },
            ),
      ]),
  },
]

const candidateColumns = [
  { title: '候选标题', key: 'title', minWidth: 220, ellipsis: { tooltip: true } },
  { title: '来源问题', key: 'question', minWidth: 260, ellipsis: { tooltip: true } },
  { title: '状态', key: 'status', width: 90, render: (row) => candidateStatusTag(row.status) },
  { title: '优先级', key: 'priority', width: 90, render: (row) => row.priority || 0 },
  { title: '更新时间', key: 'updated_at', width: 180, render: (row) => formatDate(row.updated_at) },
  {
    title: '操作',
    key: 'actions',
    width: 300,
    fixed: 'right',
    render: (row) =>
      h('div', { class: 'row-actions' }, [
        h(
          NButton,
          {
            size: 'small',
            type: 'primary',
            secondary: true,
            disabled: row.status === 'approved',
            loading: candidateActionId.value === `${row.id}:approved`,
            onClick: () => updateCandidateStatus(row, 'approved'),
          },
          { default: () => '通过' },
        ),
        h(
          NButton,
          {
            size: 'small',
            secondary: true,
            disabled: row.status === 'rejected',
            loading: candidateActionId.value === `${row.id}:rejected`,
            onClick: () => updateCandidateStatus(row, 'rejected'),
          },
          { default: () => '拒绝' },
        ),
        h(
          NButton,
          {
            size: 'small',
            secondary: true,
            disabled: !['approved', 'drafted'].includes(row.status),
            loading: candidateActionId.value === `${row.id}:draft`,
            onClick: () => generateCandidateDraft(row),
          },
          { default: () => '生成草稿' },
        ),
        h(
          NButton,
          {
            size: 'small',
            type: 'primary',
            secondary: true,
            disabled: !['drafted', 'approved'].includes(row.status),
            loading: candidateActionId.value === `${row.id}:import`,
            onClick: () => importCandidate(row),
          },
          { default: () => '入库' },
        ),
      ]),
  },
]

onMounted(async () => {
  await Promise.all([loadSettings(), loadReports(), loadGaps(), loadCandidates()])
  if (reports.value[0]?.report_id) await openReport(reports.value[0].report_id)
})

async function loadSettings() {
  const res = await api.skillKnowEvolutionSettings()
  settings.value = {
    enabled: res.data?.enabled !== false,
    run_at: res.data?.run_at || '02:10',
    top_k: res.data?.top_k || 8,
  }
}

async function loadReports() {
  loading.value = true
  try {
    const res = await api.skillKnowEvolutionReports({ limit: 30 })
    reports.value = Array.isArray(res.data) ? res.data : []
  } finally {
    loading.value = false
  }
}

async function loadGaps() {
  const res = await api.skillKnowKnowledgeGaps({ limit: 100 })
  gaps.value = Array.isArray(res.data) ? res.data : []
}

async function loadCandidates() {
  const res = await api.skillKnowLearningCandidates({ limit: 100 })
  candidates.value = Array.isArray(res.data) ? res.data : []
}

async function openReport(reportId) {
  if (!reportId) return
  detailLoading.value = true
  try {
    const res = await api.skillKnowEvolutionReport(reportId)
    selected.value = res.data
  } finally {
    detailLoading.value = false
  }
}

async function runReport() {
  running.value = true
  try {
    const res = await api.skillKnowRunEvolutionReport({ top_k: settings.value.top_k || 8 })
    selected.value = res.data
    $message.success('自进化评测报告已生成')
    await Promise.all([loadReports(), loadGaps()])
  } finally {
    running.value = false
  }
}

async function saveSettings() {
  savingSettings.value = true
  try {
    const payload = {
      enabled: settings.value.enabled !== false,
      run_at: settings.value.run_at || '02:10',
      top_k: settings.value.top_k || 8,
    }
    const res = await api.skillKnowSaveEvolutionSettings(payload)
    settings.value = res.data
    $message.success('自进化设置已保存')
  } finally {
    savingSettings.value = false
  }
}

async function updateGapStatus(row, status) {
  gapActionId.value = `${row.id}:${status}`
  try {
    await api.skillKnowUpdateKnowledgeGapStatus(row.id, { status })
    $message.success(status === 'ignored' ? '知识缺口已忽略' : '知识缺口已恢复')
    await loadGaps()
  } finally {
    gapActionId.value = ''
  }
}

function openGapConvertModal(row) {
  selectedGap.value = row
  goldenForm.value = {
    expected_document_id: null,
    expected_section_id: null,
    expected_heading_contains: '',
  }
  gapModalVisible.value = true
}

function openCandidateModal(row) {
  selectedGap.value = row
  candidateForm.value = {
    title: row.question || '',
    draft_answer: '',
  }
  candidateModalVisible.value = true
}

async function convertGap() {
  if (!selectedGap.value?.id) return
  const gapId = selectedGap.value.id
  gapActionId.value = `${gapId}:golden`
  try {
    await api.skillKnowConvertGapToGoldenCase(gapId, normalizeGoldenPayload())
    $message.success('已转为黄金问题')
    gapModalVisible.value = false
    selectedGap.value = null
    await loadGaps()
  } finally {
    gapActionId.value = ''
  }
}

async function createCandidate() {
  if (!selectedGap.value?.id) return
  const gapId = selectedGap.value.id
  gapActionId.value = `${gapId}:candidate`
  try {
    await api.skillKnowCreateLearningCandidate(gapId, {
      title: candidateForm.value.title || selectedGap.value.question,
      draft_answer: candidateForm.value.draft_answer || '',
    })
    $message.success('学习候选已生成')
    candidateModalVisible.value = false
    selectedGap.value = null
    await Promise.all([loadGaps(), loadCandidates()])
  } finally {
    gapActionId.value = ''
  }
}

async function updateCandidateStatus(row, status) {
  candidateActionId.value = `${row.id}:${status}`
  try {
    await api.skillKnowUpdateLearningCandidateStatus(row.id, { status })
    $message.success(status === 'approved' ? '学习候选已通过' : '学习候选已拒绝')
    await loadCandidates()
  } finally {
    candidateActionId.value = ''
  }
}

async function generateCandidateDraft(row) {
  candidateActionId.value = `${row.id}:draft`
  try {
    await api.skillKnowGenerateLearningCandidateDraft(row.id)
    $message.success('Markdown 草稿已生成')
    await loadCandidates()
  } finally {
    candidateActionId.value = ''
  }
}

async function importCandidate(row) {
  candidateActionId.value = `${row.id}:import`
  try {
    await api.skillKnowImportLearningCandidate(row.id, {})
    $message.success('学习候选已入库并开始重建索引')
    await loadCandidates()
  } finally {
    candidateActionId.value = ''
  }
}

function normalizeGoldenPayload() {
  return {
    expected_document_id: goldenForm.value.expected_document_id || null,
    expected_section_id: goldenForm.value.expected_section_id || null,
    expected_heading_contains: String(goldenForm.value.expected_heading_contains || '').trim() || null,
  }
}

function statusTag(status) {
  const type = status === 'success' ? 'success' : status === 'failed' ? 'error' : 'warning'
  const label = status === 'success' ? '成功' : status === 'failed' ? '失败' : status || '-'
  return h(NTag, { size: 'small', type, bordered: false }, { default: () => label })
}

function gapStatusTag(status) {
  const typeMap = { pending: 'warning', resolved: 'success', ignored: 'default' }
  const labelMap = { pending: '待处理', resolved: '已解决', ignored: '已忽略' }
  return h(
    NTag,
    { size: 'small', type: typeMap[status] || 'default', bordered: false },
    { default: () => labelMap[status] || status || '-' },
  )
}

function candidateStatusTag(status) {
  const typeMap = { pending: 'warning', approved: 'success', rejected: 'error', drafted: 'info', imported: 'success' }
  const labelMap = { pending: '待审核', approved: '已通过', rejected: '已拒绝', drafted: '已出草稿', imported: '已入库' }
  return h(
    NTag,
    { size: 'small', type: typeMap[status] || 'default', bordered: false },
    { default: () => labelMap[status] || status || '-' },
  )
}

function hitTag(value) {
  return h(
    NTag,
    { size: 'small', type: value ? 'success' : 'error', bordered: false },
    { default: () => (value ? '命中' : '未命中') },
  )
}

function formatPercent(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '0%'
  return `${Math.round(number * 1000) / 10}%`
}

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}
</script>

<template>
  <CommonPage title="自进化报告" :show-header="false" show-footer>
    <div class="evolution-workspace">
      <header class="evolution-header">
        <div>
          <div class="eyebrow">Skill-Know Evolution</div>
          <h1>自进化报告</h1>
          <p>运行黄金问题回归评测，跟踪检索命中率、知识缺口和待审核学习候选。</p>
        </div>
        <NSpace align="center">
          <NButton secondary :loading="loading" @click="loadReports">刷新</NButton>
          <NButton type="primary" :loading="running" @click="runReport">运行评测</NButton>
        </NSpace>
      </header>

      <section class="settings-panel">
        <div class="setting-item switch-item">
          <span>每日自动评测</span>
          <NSwitch v-model:value="settings.enabled" />
        </div>
        <div class="setting-item">
          <span>运行时间</span>
          <NInput v-model:value="settings.run_at" size="small" placeholder="02:10" />
        </div>
        <div class="setting-item">
          <span>TopK</span>
          <NInputNumber v-model:value="settings.top_k" :min="1" :max="20" size="small" />
        </div>
        <NButton type="primary" secondary :loading="savingSettings" @click="saveSettings">保存设置</NButton>
      </section>

      <section class="metric-grid">
        <div class="metric-card">
          <span>黄金问题</span>
          <b>{{ metrics.total || 0 }}</b>
          <p>{{ latestReport ? formatDate(latestReport.started_at) : '暂无报告' }}</p>
        </div>
        <div class="metric-card">
          <span>Top1 命中率</span>
          <b>{{ formatPercent(metrics.top1_accuracy) }}</b>
          <p>首位结果是否直接命中目标章节</p>
        </div>
        <div class="metric-card">
          <span>知识缺口</span>
          <b>{{ pendingGapCount }}</b>
          <p>低分问题会沉淀为待处理缺口</p>
        </div>
        <div class="metric-card alert">
          <span>学习候选</span>
          <b>{{ pendingCandidateCount }}</b>
          <p>候选内容通过人工审核后再进入后续入库流程</p>
        </div>
      </section>

      <main class="evolution-grid">
        <section class="panel report-list-panel">
          <div class="panel-head">
            <div>
              <h3>报告列表</h3>
              <p>最新报告排在最上方。</p>
            </div>
          </div>
          <NDataTable :columns="reportColumns" :data="reports" :loading="loading" size="small" :pagination="{ pageSize: 10 }" :scroll-x="760" />
        </section>

        <section class="panel gap-panel">
          <div class="panel-head">
            <div>
              <h3>知识缺口</h3>
              <p>来自每日评测未命中的问题，按优先级和出现次数排序。</p>
            </div>
            <NButton size="small" secondary @click="loadGaps">刷新</NButton>
          </div>
          <NDataTable :columns="gapColumns" :data="gaps" size="small" :pagination="{ pageSize: 8 }" :scroll-x="1100" />
        </section>

        <section class="panel candidate-panel">
          <div class="panel-head">
            <div>
              <h3>学习候选</h3>
              <p>先审核候选内容，再决定是否沉淀为正式知识。</p>
            </div>
            <NButton size="small" secondary @click="loadCandidates">刷新</NButton>
          </div>
          <NDataTable :columns="candidateColumns" :data="candidates" size="small" :pagination="{ pageSize: 8 }" :scroll-x="920" />
        </section>

        <section class="panel detail-panel">
          <div class="panel-head">
            <div>
              <h3>报告详情</h3>
              <p>{{ selected?.report_id || '选择一份报告查看详情' }}</p>
            </div>
            <NTag v-if="selected" :type="selected.status === 'success' ? 'success' : 'error'" round>
              {{ selected.status === 'success' ? '成功' : '失败' }}
            </NTag>
          </div>

          <NSpin :show="detailLoading">
            <div v-if="selected" class="detail-body">
              <div class="detail-meta">
                <div>
                  <span>开始时间</span>
                  <b>{{ formatDate(selected.started_at) }}</b>
                </div>
                <div>
                  <span>结束时间</span>
                  <b>{{ formatDate(selected.finished_at) }}</b>
                </div>
                <div>
                  <span>平均耗时</span>
                  <b>{{ selected.metrics?.avg_latency_ms || 0 }}ms</b>
                </div>
              </div>

              <section class="sub-panel">
                <div class="sub-head">
                  <h4>低分问题</h4>
                  <NTag size="small" type="warning" :bordered="false">{{ lowScoreQuestions.length }}</NTag>
                </div>
                <div v-if="lowScoreQuestions.length" class="question-list">
                  <div v-for="question in lowScoreQuestions" :key="question" class="question-item">
                    {{ question }}
                  </div>
                </div>
                <NEmpty v-else description="本次没有低分问题" />
              </section>

              <section class="sub-panel">
                <div class="sub-head">
                  <h4>下一步建议</h4>
                  <NTag size="small" type="info" :bordered="false">{{ nextActions.length }}</NTag>
                </div>
                <div v-if="nextActions.length" class="action-list">
                  <div v-for="(item, index) in nextActions" :key="`${item.type}-${index}`" class="action-item">
                    <b>{{ item.title || item.type }}</b>
                    <p>{{ item.detail }}</p>
                  </div>
                </div>
                <NEmpty v-else description="暂无建议" />
              </section>

              <section class="sub-panel">
                <div class="sub-head">
                  <h4>评测明细</h4>
                  <NTag size="small" :bordered="false">{{ evalRows.length }}</NTag>
                </div>
                <NDataTable :columns="evalColumns" :data="evalRows" size="small" :pagination="{ pageSize: 8 }" :scroll-x="720" />
              </section>
            </div>
            <NEmpty v-else description="暂无自进化报告，先运行一次评测" />
          </NSpin>
        </section>
      </main>

      <NModal v-model:show="gapModalVisible" preset="dialog" title="转为黄金问题" positive-text="保存" negative-text="取消" @positive-click="convertGap">
        <div class="dialog-form">
          <p class="dialog-question">{{ selectedGap?.question || '-' }}</p>
          <NForm label-placement="top">
            <NFormItem label="预期文档 ID">
              <NInputNumber v-model:value="goldenForm.expected_document_id" :min="1" clearable placeholder="可选" />
            </NFormItem>
            <NFormItem label="预期章节 ID">
              <NInputNumber v-model:value="goldenForm.expected_section_id" :min="1" clearable placeholder="可选" />
            </NFormItem>
            <NFormItem label="预期标题包含">
              <NInput v-model:value="goldenForm.expected_heading_contains" placeholder="例如：加解密、网关、移动存储" />
            </NFormItem>
          </NForm>
        </div>
      </NModal>

      <NModal v-model:show="candidateModalVisible" preset="dialog" title="生成学习候选" positive-text="保存" negative-text="取消" @positive-click="createCandidate">
        <div class="dialog-form">
          <p class="dialog-question">{{ selectedGap?.question || '-' }}</p>
          <NForm label-placement="top">
            <NFormItem label="候选标题">
              <NInput v-model:value="candidateForm.title" placeholder="候选知识标题" />
            </NFormItem>
            <NFormItem label="候选答案草稿">
              <NInput v-model:value="candidateForm.draft_answer" type="textarea" :autosize="{ minRows: 4, maxRows: 8 }" placeholder="可先写处理思路、标准答案或需要补充的知识点" />
            </NFormItem>
          </NForm>
        </div>
      </NModal>
    </div>
  </CommonPage>
</template>

<style scoped>
.evolution-workspace {
  --line: rgba(17, 24, 39, 0.1);
  --text: #111827;
  --muted: #6b7280;
  min-height: calc(100vh - 96px);
  padding: 22px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #f8faf9;
}

.evolution-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--line);
}

.eyebrow {
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

h1,
h3,
h4,
p {
  margin: 0;
}

h1 {
  margin-top: 5px;
  color: var(--text);
  font-size: 26px;
  font-weight: 800;
}

.evolution-header p,
.panel-head p,
.metric-card p,
.action-item p {
  margin-top: 6px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.settings-panel {
  display: grid;
  grid-template-columns: minmax(160px, 0.7fr) minmax(140px, 0.7fr) 120px auto;
  gap: 12px;
  align-items: end;
  margin-top: 16px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.82);
}

.setting-item {
  display: grid;
  gap: 7px;
}

.setting-item span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.switch-item {
  min-height: 54px;
  align-content: center;
}

.metric-card,
.panel,
.sub-panel {
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.05);
}

.metric-card {
  min-height: 118px;
  padding: 16px;
  border-radius: 12px;
}

.metric-card span {
  color: var(--muted);
  font-size: 12px;
}

.metric-card b {
  display: block;
  margin-top: 8px;
  color: var(--text);
  font-size: 24px;
}

.metric-card.alert {
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(255, 251, 235, 0.82);
}

.evolution-grid {
  display: grid;
  grid-template-columns: minmax(460px, 0.9fr) minmax(0, 1.1fr);
  gap: 16px;
  margin-top: 16px;
}

.panel {
  overflow: hidden;
  border-radius: 12px;
}

.candidate-panel,
.detail-panel {
  grid-column: span 2;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 16px;
  border-bottom: 1px solid var(--line);
  background: #fbfcfa;
}

.panel-head h3,
.sub-head h4 {
  color: var(--text);
  font-weight: 800;
}

.row-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.detail-body {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.detail-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.detail-meta div {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
}

.detail-meta span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}

.detail-meta b {
  display: block;
  margin-top: 5px;
  overflow: hidden;
  color: var(--text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sub-panel {
  padding: 14px;
  border-radius: 12px;
}

.sub-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.question-list,
.action-list {
  display: grid;
  gap: 10px;
}

.question-item,
.action-item {
  padding: 10px 12px;
  border: 1px solid rgba(245, 158, 11, 0.24);
  border-radius: 8px;
  background: #fffdf7;
  color: var(--text);
  line-height: 1.6;
  word-break: break-word;
}

.action-item {
  border-color: rgba(15, 118, 110, 0.2);
  background: #f7fffc;
}

.dialog-form {
  display: grid;
  gap: 14px;
}

.dialog-question {
  padding: 10px 12px;
  border: 1px solid rgba(15, 118, 110, 0.18);
  border-radius: 8px;
  background: #f7fffc;
  color: var(--text);
  line-height: 1.6;
  word-break: break-word;
}

@media (max-width: 1180px) {
  .metric-grid,
  .evolution-grid,
  .detail-meta,
  .settings-panel {
    grid-template-columns: 1fr;
  }

  .candidate-panel,
  .detail-panel {
    grid-column: auto;
  }

  .evolution-header {
    flex-direction: column;
  }
}
</style>
