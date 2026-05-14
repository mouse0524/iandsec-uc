<script setup>
import { onMounted, ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '在线升级' })

const formRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const checking = ref(false)
const checkResult = ref(null)
const form = ref({
  latest_version: '',
  webdav_path: '',
  enabled: true,
  force_upgrade: false,
  release_notes: '',
  report_token: '',
  download_expire_hours: 168,
})
const testForm = ref({
  currentVersion: '',
  platform: 'windows',
  companyName: '',
})

const rules = {
  latest_version: { required: true, message: '请输入最新版本号', trigger: ['input', 'blur'] },
  webdav_path: { required: true, message: '请输入WebDAV升级包路径', trigger: ['input', 'blur'] },
  download_expire_hours: {
    required: true,
    type: 'number',
    min: 1,
    message: '下载链接有效期必须大于0',
    trigger: ['blur', 'change'],
  },
}

onMounted(loadConfig)

async function loadConfig() {
  loading.value = true
  try {
    const res = await api.terminalUpgradeConfig()
    if (res.data) {
      form.value = {
        ...form.value,
        ...res.data,
      }
    }
  } finally {
    loading.value = false
  }
}

function saveConfig() {
  formRef.value?.validate(async (err) => {
    if (err) return
    saving.value = true
    try {
      const res = await api.terminalSaveUpgradeConfig(form.value)
      form.value = { ...form.value, ...res.data }
      $message.success('升级配置已保存')
    } finally {
      saving.value = false
    }
  })
}

async function checkUpgrade() {
  if (!testForm.value.currentVersion) {
    $message.warning('请输入当前版本号')
    return
  }
  checking.value = true
  try {
    const res = await api.terminalCheckUpgrade(testForm.value)
    checkResult.value = res.data
  } finally {
    checking.value = false
  }
}
</script>

<template>
  <CommonPage title="在线升级" :show-header="false" show-footer>
    <NSpin :show="loading">
      <div class="upgrade-page">
        <header class="page-head">
          <div>
            <div class="eyebrow">Terminal Upgrade</div>
            <h1>在线升级</h1>
            <p>维护最新版本与 WebDAV 升级包路径，客户端检测到新版本后可获取签名下载链接。</p>
          </div>
          <NTag :type="form.enabled ? 'success' : 'warning'" round>{{ form.enabled ? '已启用' : '已停用' }}</NTag>
        </header>

        <section class="content-grid">
          <div class="config-panel">
            <div class="panel-head">
              <h3>升级配置</h3>
              <p>路径填写 WebDAV 中升级包的完整文件路径，例如 /release/tdlp/6.0.9.zip。</p>
            </div>
            <NForm ref="formRef" :model="form" :rules="rules" label-placement="top">
              <div class="form-grid">
                <NFormItem label="启用升级检测">
                  <NSwitch v-model:value="form.enabled" />
                </NFormItem>
                <NFormItem label="强制升级">
                  <NSwitch v-model:value="form.force_upgrade" />
                </NFormItem>
                <NFormItem label="最新版本号" path="latest_version">
                  <NInput v-model:value="form.latest_version" placeholder="例如 6.0.9-20260101" />
                </NFormItem>
                <NFormItem label="下载链接有效期(小时)" path="download_expire_hours">
                  <NInputNumber v-model:value="form.download_expire_hours" :min="1" :max="8760" />
                </NFormItem>
              </div>
              <NFormItem label="WebDAV升级包路径" path="webdav_path">
                <NInput v-model:value="form.webdav_path" placeholder="/release/tdlp/6.0.9.zip" />
              </NFormItem>
              <NFormItem label="第三方上报密钥">
                <NInput
                  v-model:value="form.report_token"
                  type="password"
                  show-password-on="mousedown"
                  placeholder="可选；配置后第三方上报需携带 X-Terminal-Token"
                />
              </NFormItem>
              <NFormItem label="版本说明">
                <NInput
                  v-model:value="form.release_notes"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 8 }"
                  placeholder="请输入本次升级说明"
                />
              </NFormItem>
              <NButton type="primary" :loading="saving" @click="saveConfig">保存配置</NButton>
            </NForm>
          </div>

          <div class="check-panel">
            <div class="panel-head">
              <h3>接口自测</h3>
              <p>模拟客户端调用升级检测接口，确认版本比较和下载链接生成结果。</p>
            </div>
            <NForm label-placement="top">
              <NFormItem label="当前版本号">
                <NInput v-model:value="testForm.currentVersion" placeholder="例如 6.0.8-20251221" />
              </NFormItem>
              <NFormItem label="终端平台">
                <NSelect
                  v-model:value="testForm.platform"
                  :options="[
                    { label: 'Windows', value: 'windows' },
                    { label: 'macOS', value: 'mac' },
                    { label: 'Linux', value: 'linux' },
                    { label: '手机', value: 'mobile' },
                  ]"
                />
              </NFormItem>
              <NFormItem label="公司名称">
                <NInput v-model:value="testForm.companyName" placeholder="可选" />
              </NFormItem>
              <NButton secondary type="primary" :loading="checking" @click="checkUpgrade">检测升级</NButton>
            </NForm>

            <div v-if="checkResult" class="result-card">
              <div>
                <span>是否需要升级</span>
                <b>{{ checkResult.upgrade ? '是' : '否' }}</b>
              </div>
              <div>
                <span>当前版本</span>
                <b>{{ checkResult.currentVersion || '-' }}</b>
              </div>
              <div>
                <span>最新版本</span>
                <b>{{ checkResult.latestVersion || '-' }}</b>
              </div>
              <div v-if="checkResult.downloadUrl">
                <span>下载链接</span>
                <b>{{ checkResult.downloadUrl }}</b>
              </div>
            </div>
          </div>
        </section>
      </div>
    </NSpin>
  </CommonPage>
</template>

<style scoped>
.upgrade-page {
  --upgrade-line: rgba(17, 24, 39, .10);
  --upgrade-muted: #64748b;
  --upgrade-text: #111827;
  display: grid;
  gap: 16px;
  min-height: calc(100vh - 128px);
  padding: 22px;
  border: 1px solid var(--upgrade-line);
  border-radius: 16px;
  background: #f7f8fa;
}
.page-head, .content-grid {
  display: flex;
  gap: 16px;
}
.page-head {
  justify-content: space-between;
  align-items: flex-start;
}
.content-grid {
  align-items: flex-start;
}
.config-panel, .check-panel {
  min-width: 0;
  border: 1px solid var(--upgrade-line);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 10px 26px rgba(15, 23, 42, .06);
}
.config-panel {
  flex: 1 1 auto;
  padding: 18px;
}
.check-panel {
  flex: 0 0 380px;
  padding: 18px;
}
.panel-head {
  margin-bottom: 16px;
}
.eyebrow {
  color: var(--primary-color, #f4511e);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}
h1, h3, p {
  margin: 0;
}
h1, h3 {
  color: var(--upgrade-text);
  font-weight: 800;
}
.page-head p, .panel-head p {
  margin-top: 6px;
  color: var(--upgrade-muted);
  font-size: 13px;
  line-height: 1.6;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}
.result-card {
  display: grid;
  gap: 0;
  margin-top: 18px;
  overflow: hidden;
  border: 1px solid var(--upgrade-line);
  border-radius: 10px;
}
.result-card div {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr);
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(17, 24, 39, .08);
}
.result-card div:last-child {
  border-bottom: 0;
}
.result-card span {
  color: var(--upgrade-muted);
  font-size: 12px;
}
.result-card b {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--upgrade-text);
}
@media (max-width: 1100px) {
  .content-grid {
    flex-direction: column;
  }
  .check-panel {
    flex: 1 1 auto;
    width: 100%;
  }
}
@media (max-width: 640px) {
  .upgrade-page {
    padding: 14px;
  }
  .page-head {
    flex-direction: column;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
