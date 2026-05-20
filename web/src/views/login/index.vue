<template>
  <AppPage :show-footer="false" class="login-page-shell">
    <div class="login-wrap">
      <section class="brand-panel">
        <div class="brand-identity">
          <div class="brand-logo-mark">
            <icon-custom-logo text-42 />
          </div>
          <div>
            <p class="brand-eyebrow">用户服务中心</p>
            <h1>{{ appStore.siteTitle || $t('app_name') }}</h1>
          </div>
        </div>

        <div class="hero-copy">
          <h2>AI驱动数据安全 · 让数据更安全</h2>
          <p>面向客户、渠道商、客服与技术团队，集中完成工单受理、知识检索、外发共享和权限审计。</p>
        </div>

        <div class="operations-board">
          <div class="capability-grid">
            <div class="capability-item">
              <icon-mdi:file-document-check-outline text-22 />
              <div>
                <h4>工单中心</h4>
                <p>问题提交、附件留痕、客服审核、技术处理全链路跟踪</p>
              </div>
            </div>
            <div class="capability-item">
              <icon-carbon:machine-learning-model text-22 />
              <div>
                <h4>AI 知识库</h4>
                <p>Markdown 文档检索、引用溯源、智能问答辅助排障</p>
              </div>
            </div>
            <div class="capability-item">
              <icon-material-symbols:cloud-sync-outline text-22 />
              <div>
                <h4>WebDAV 外发</h4>
                <p>受控文件浏览、分享链接、到期管理和记录审计</p>
              </div>
            </div>
            <div class="capability-item">
              <icon-material-symbols:admin-panel-settings-outline-rounded text-22 />
              <div>
                <h4>权限与审计</h4>
                <p>角色授权、动态菜单、接口权限和操作日志统一管理</p>
              </div>
            </div>
          </div>
        </div>

        <div class="support-strip">
          <div>
            <span>支持对象</span>
            <strong>客户 · 渠道商 · 客服 · 技术</strong>
          </div>
          <div>
            <span>紧急支持</span>
            <strong>4001381063</strong>
          </div>
        </div>
      </section>

      <section class="auth-panel">
        <div class="auth-card">
          <div class="auth-head">
            <div>
              <span class="auth-kicker">SECURE ACCESS</span>
              <h3>账号登录</h3>
              <p class="auth-tip">请输入邮箱、密码和验证码进入服务中心</p>
            </div>
            <icon-material-symbols:shield-lock-outline-rounded class="auth-head-icon" />
          </div>

          <div class="auth-form-item">
            <label>邮箱账号</label>
            <n-input v-model:value="loginInfo.username" autofocus placeholder="请输入邮箱" :maxlength="50" />
          </div>
          <div class="auth-form-item">
            <label>登录密码</label>
            <n-input
              v-model:value="loginInfo.password"
              type="password"
              show-password-on="mousedown"
              placeholder="请输入密码"
              :maxlength="50"
              @keypress.enter="handleLogin"
            />
          </div>
          <div class="auth-form-item">
            <label>安全验证码</label>
            <div class="captcha-row">
              <n-input
                v-model:value="loginInfo.captcha_code"
                placeholder="请输入登录验证码"
                :maxlength="6"
                @keypress.enter="handleLogin"
              />
              <img :src="loginCaptchaImage" alt="login-captcha" class="captcha-img" @click="fetchLoginCaptcha" />
            </div>
          </div>

          <n-button class="login-btn" type="primary" :loading="loading" @click="handleLogin">
            {{ $t('views.login.text_login') }}
          </n-button>

          <div class="auth-links">
            <n-button text type="primary" @click="openForgotPasswordModal">忘记密码</n-button>
            <n-button v-if="appStore.allowPartnerRegister" text type="primary" @click="openPartnerRegisterModal">注册账号</n-button>
          </div>

          <div class="agreement-row">
            <n-checkbox v-model:checked="loginAgree">
              <span>我已阅读并同意</span>
              <n-button text type="primary" class="agreement-link" @click.stop="showUserAgreementModal = true">《用户服务协议》</n-button>
              <span>与</span>
              <n-button text type="primary" class="agreement-link" @click.stop="showPrivacyPolicyModal = true">《隐私政策》</n-button>
            </n-checkbox>
          </div>
        </div>
      </section>
    </div>

    <n-modal v-model:show="showPartnerModal" preset="card" title="账号注册" style="width: 560px">
      <div class="service-register-modal">
        <div class="register-head">
          <h4>服务中心注册</h4>
          <p>完成注册并通过审核后，即可登录系统提交工单。</p>
        </div>

        <n-form ref="partnerFormRef" :model="partnerForm" :rules="partnerRules" label-width="90" label-placement="left">
          <n-form-item label="注册类型">
            <div class="register-type-switch">
              <n-button
                round
                :type="partnerForm.register_type === 'channel' ? 'primary' : 'default'"
                :disabled="!appStore.allowChannelRegister"
                @click="partnerForm.register_type = 'channel'"
              >
                渠道商注册
              </n-button>
              <n-button
                round
                :type="partnerForm.register_type === 'user' ? 'primary' : 'default'"
                :disabled="!appStore.allowUserRegister"
                @click="partnerForm.register_type = 'user'"
              >
                用户注册
              </n-button>
            </div>
          </n-form-item>
          <n-form-item label="公司名称" path="company_name">
            <n-input v-model:value="partnerForm.company_name" placeholder="请输入公司名称" />
          </n-form-item>
          <n-form-item label="联系人" path="contact_name">
            <n-input v-model:value="partnerForm.contact_name" placeholder="请输入联系人" />
          </n-form-item>
          <n-form-item label="邮箱" path="email">
            <n-input v-model:value="partnerForm.email" placeholder="请输入邮箱" />
          </n-form-item>
          <n-form-item label="邮箱验证码" path="email_code">
            <div class="email-code-row">
              <n-input v-model:value="partnerForm.email_code" placeholder="请输入邮箱验证码" />
              <n-button :loading="emailCodeSending" :disabled="!canSendEmailCode" @click="openCaptchaModal">{{ emailCodeButtonText }}</n-button>
            </div>
          </n-form-item>
          <n-form-item label="手机号" path="phone">
            <n-input v-model:value="partnerForm.phone" placeholder="请输入手机号" />
          </n-form-item>
          <n-form-item v-if="partnerForm.register_type === 'user'" path="hardware_id" required>
            <template #label>
              <div flex items-center gap-4>
                <span>设备机器码</span>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <icon-mdi:help-circle-outline text-15 color="#999" style="cursor: pointer" />
                  </template>
                  使用sysadmin登录系统，点击授权-更新应用授权
                </n-tooltip>
              </div>
            </template>
            <n-input v-model:value="partnerForm.hardware_id" placeholder="请输入设备机器码" />
          </n-form-item>
          <n-form-item label="密码" path="password">
            <n-input v-model:value="partnerForm.password" type="password" placeholder="请输入密码" />
          </n-form-item>
          <n-form-item path="agree_protocol" :show-label="false">
            <n-checkbox v-model:checked="partnerForm.agree_protocol">
              <span>我已阅读并同意</span>
              <n-button text type="primary" class="agreement-link" @click.stop="showUserAgreementModal = true">《用户服务协议》</n-button>
              <span>与</span>
              <n-button text type="primary" class="agreement-link" @click.stop="showPrivacyPolicyModal = true">《隐私政策》</n-button>
            </n-checkbox>
          </n-form-item>
        </n-form>

        <div class="register-hotline">
          <icon-mdi:phone-in-talk-outline text-16 />
          <span>审核会在24h内完成，如您遇到紧急问题，请拨打 4001381063</span>
        </div>
      </div>
      <template #footer>
        <div flex justify-end>
          <n-button @click="showPartnerModal = false">取消</n-button>
          <n-button ml-12 type="primary" :loading="partnerSubmitting" @click="submitPartnerRegister">提交注册</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="showCaptchaModal" preset="card" title="图形验证码" style="width: 460px">
      <div class="captcha-modal-panel">
        <div class="captcha-modal-head">
          <h4>安全校验</h4>
          <p>请输入图形验证码后发送邮箱验证码。</p>
        </div>

        <n-form :model="partnerForm" :rules="captchaRules" label-width="80" label-placement="left">
          <n-form-item label="验证码" path="captcha_code">
            <div class="captcha-modal-row">
              <n-input v-model:value="partnerForm.captcha_code" placeholder="请输入图形验证码" />
              <img :src="partnerCaptchaImage" class="captcha-modal-img" @click="fetchPartnerCaptcha" />
            </div>
          </n-form-item>
        </n-form>
      </div>
      <template #footer>
        <div flex justify-end>
          <n-button @click="showCaptchaModal = false">取消</n-button>
          <n-button ml-12 type="primary" :loading="emailCodeSending" @click="sendEmailCode">发送验证码</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="showForgotPasswordModal" preset="card" title="找回密码" style="width: 520px">
      <n-form ref="forgotFormRef" :model="forgotForm" :rules="forgotRules" label-width="90" label-placement="left">
        <n-form-item label="邮箱" path="email">
          <n-input v-model:value="forgotForm.email" placeholder="请输入注册邮箱" />
        </n-form-item>
        <n-form-item label="图形验证码" path="captcha_code">
          <div class="captcha-modal-row">
            <n-input v-model:value="forgotForm.captcha_code" placeholder="请输入图形验证码" />
            <img :src="forgotCaptchaImage" class="captcha-modal-img" @click="fetchForgotCaptcha" />
          </div>
        </n-form-item>
        <n-form-item label="邮箱验证码" path="email_code">
          <div class="email-code-row">
            <n-input v-model:value="forgotForm.email_code" placeholder="请输入邮箱验证码" />
            <n-button :loading="forgotCodeSending" :disabled="forgotCodeCooldown > 0" @click="sendForgotCode">
              {{ forgotCodeCooldown > 0 ? `${forgotCodeCooldown}s后重试` : '发送验证码' }}
            </n-button>
          </div>
        </n-form-item>
        <n-form-item label="新密码" path="new_password">
          <n-input v-model:value="forgotForm.new_password" type="password" show-password-on="mousedown" placeholder="请输入新密码" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div flex justify-end>
          <n-button @click="showForgotPasswordModal = false">取消</n-button>
          <n-button ml-12 type="primary" :loading="forgotSubmitting" @click="submitForgotPassword">重置密码</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="showUserAgreementModal" preset="card" title="用户服务协议" style="width: 760px">
      <div class="protocol-body">
        <h4>一、协议说明</h4>
        <p>欢迎使用本系统用户服务中心。您在注册、登录及使用本系统服务前，应完整阅读并同意本协议全部内容。</p>

        <h4>二、服务内容</h4>
        <p>本系统主要提供账号注册、工单提交、审核流转、技术处理、消息通知等服务能力。平台可根据业务需要对服务进行升级与优化。</p>

        <h4>三、账号与安全</h4>
        <p>您应保证注册信息真实、准确、完整，并妥善保管账号与密码。因账号保管不当导致的风险由账号持有人自行承担。</p>

        <h4>四、使用规范</h4>
        <p>您不得利用本系统发布违法、侵权、虚假或恶意信息，不得进行影响系统稳定性的行为。平台有权对违规行为采取限制、冻结或注销措施。</p>

        <h4>五、免责声明</h4>
        <p>在不可抗力、网络故障、第三方服务异常等情况下，平台不对由此造成的服务中断承担责任，但会尽力恢复服务。</p>

        <h4>六、协议变更</h4>
        <p>平台有权根据业务和法规要求更新协议内容。更新后继续使用本系统即视为您已接受更新后的条款。</p>
      </div>
    </n-modal>

    <n-modal v-model:show="showPrivacyPolicyModal" preset="card" title="隐私政策" style="width: 760px">
      <div class="protocol-body">
        <h4>一、信息收集范围</h4>
        <p>为提供服务，我们会收集您主动提交的信息，包括但不限于公司名称、联系人、邮箱、手机号、设备机器码及工单内容。</p>

        <h4>二、信息使用目的</h4>
        <p>收集的信息仅用于账号审核、身份识别、工单处理、服务通知、系统安全审计及服务质量改进，不会用于与本服务无关的用途。</p>

        <h4>三、信息共享与披露</h4>
        <p>除法律法规要求或经您授权外，我们不会向无关第三方披露您的个人信息。必要时仅在最小范围内共享给受托服务方。</p>

        <h4>四、信息安全</h4>
        <p>我们采用访问控制、传输加密、日志审计等措施保护数据安全，并持续优化安全机制以降低数据泄露风险。</p>

        <h4>五、您的权利</h4>
        <p>您有权访问、更正或申请删除您的个人信息，并可通过管理员或客服渠道反馈隐私相关问题。</p>

        <h4>六、政策更新</h4>
        <p>本政策可能根据法律法规和业务变化适时更新。更新后将通过系统页面进行公示，建议您定期查阅。</p>
      </div>
    </n-modal>
  </AppPage>
</template>

<script setup>
import { lStorage, setToken } from '@/utils'
import api from '@/api'
import { addDynamicRoutes } from '@/router'
import { useI18n } from 'vue-i18n'
import { useAppStore, usePermissionStore, useUserStore } from '@/store'

const router = useRouter()
const { query } = useRoute()
const { t } = useI18n({ useScope: 'global' })
const appStore = useAppStore()
const permissionStore = usePermissionStore()
const userStore = useUserStore()

const loginInfo = ref({
  username: '',
  password: '',
  captcha_id: '',
  captcha_code: '',
})
const loginAgree = ref(false)

const loginCaptchaImage = ref('')

const showPartnerModal = ref(false)
const showCaptchaModal = ref(false)
const showUserAgreementModal = ref(false)
const showPrivacyPolicyModal = ref(false)
const showForgotPasswordModal = ref(false)
const partnerSubmitting = ref(false)
const emailCodeSending = ref(false)
const emailCodeCooldown = ref(0)
let emailCodeTimer = null
const partnerFormRef = ref(null)
const partnerCaptchaImage = ref('')
const forgotCaptchaImage = ref('')
const forgotFormRef = ref(null)
const forgotCodeSending = ref(false)
const forgotSubmitting = ref(false)
const forgotCodeCooldown = ref(0)
let forgotCodeTimer = null
const forgotForm = ref({
  email: '',
  captcha_id: '',
  captcha_code: '',
  email_code: '',
  new_password: '',
})
const partnerForm = ref({
  register_type: 'channel',
  company_name: '',
  contact_name: '',
  email: '',
  phone: '',
  hardware_id: '',
  password: '',
  email_code: '',
  captcha_id: '',
  captcha_code: '',
  agree_protocol: false,
})

const partnerRules = {
  company_name: { required: true, message: '请输入公司名称', trigger: ['blur', 'input'] },
  contact_name: { required: true, message: '请输入联系人', trigger: ['blur', 'input'] },
  email: { required: true, message: '请输入邮箱', trigger: ['blur', 'input'] },
  email_code: { required: true, message: '请输入邮箱验证码', trigger: ['blur', 'input'] },
  phone: { required: true, message: '请输入手机号', trigger: ['blur', 'input'] },
  hardware_id: {
    validator: () => {
      if (partnerForm.value.register_type === 'user' && !partnerForm.value.hardware_id?.trim()) {
        return new Error('用户注册必须填写设备机器码')
      }
      return true
    },
    trigger: ['blur', 'input', 'change'],
  },
  password: {
    validator: (_, value) => validatePasswordPolicy(value),
    trigger: ['blur', 'input'],
  },
  captcha_code: { required: true, message: '请输入验证码', trigger: ['blur', 'input'] },
  agree_protocol: {
    validator: () => {
      if (!partnerForm.value.agree_protocol) {
        return new Error('请先同意服务协议与隐私政策')
      }
      return true
    },
    trigger: ['change'],
  },
}

const captchaRules = {
  captcha_code: { required: true, message: '请输入图形验证码', trigger: ['blur', 'input'] },
}

const canSendEmailCode = computed(() => {
  return !!partnerForm.value.email?.trim() && !emailCodeSending.value && emailCodeCooldown.value === 0
})

const emailCodeButtonText = computed(() => {
  return emailCodeCooldown.value > 0 ? `${emailCodeCooldown.value}s后重试` : '发送验证码'
})

function getDefaultRegisterType() {
  if (appStore.allowChannelRegister) return 'channel'
  if (appStore.allowUserRegister) return 'user'
  return ''
}

initLoginInfo()
fetchPublicConfig()
fetchLoginCaptcha()

function initLoginInfo() {
  const localLoginInfo = lStorage.get('loginInfo')
  if (localLoginInfo) {
    loginInfo.value.username = localLoginInfo.username || ''
    if (localLoginInfo.password) lStorage.set('loginInfo', { ...localLoginInfo, password: '' })
  }
}

const loading = ref(false)

function normalizeRedirectPath(value) {
  if (Array.isArray(value)) return value[0] || ''
  return typeof value === 'string' ? value : ''
}

function isUsableRoute(path) {
  if (!path) return false
  const resolved = router.resolve(path)
  return resolved.matched.length > 0 && resolved.path !== '/404'
}

function getDefaultLoginPath() {
  if (userStore.isSuperUser) {
    return '/workbench'
  }
  const roleNames = (userStore.role || []).map((item) => item?.name).filter(Boolean)
  if (roleNames.includes('客服')) return '/ticket/review'
  if (roleNames.includes('技术')) return '/ticket/tech'
  if (roleNames.includes('用户') || roleNames.includes('渠道商') || roleNames.includes('代理商')) return '/ticket/my'
  return '/ticket/my'
}

const forgotRules = {
  email: { required: true, message: '请输入邮箱', trigger: ['blur', 'input'] },
  captcha_code: { required: true, message: '请输入图形验证码', trigger: ['blur', 'input'] },
  email_code: { required: true, message: '请输入邮箱验证码', trigger: ['blur', 'input'] },
  new_password: {
    validator: (_, value) => validatePasswordPolicy(value),
    trigger: ['blur', 'input'],
  },
}

function resolveRoleTargetPath(redirectPath) {
  const roleDefaultPath = getDefaultLoginPath()
  if (!isUsableRoute(redirectPath)) return roleDefaultPath
  if (!userStore.isSuperUser && redirectPath.startsWith('/workbench')) {
    return roleDefaultPath
  }
  return redirectPath
}

async function handleLogin() {
  const { username, password } = loginInfo.value
  const captchaCode = loginInfo.value.captcha_code?.trim()
  if (!username || !password || !captchaCode) {
    $message.warning('请完整填写邮箱、密码和验证码后再登录')
    return
  }
  if (!loginAgree.value) {
    $message.warning('请先同意服务协议与隐私政策')
    return
  }
  if (!loginInfo.value.captcha_id) {
    await fetchLoginCaptcha()
    $message.warning('验证码已更新，请重新输入后继续登录')
    return
  }
  try {
    loading.value = true
    $message.loading(t('views.login.message_verifying'))
    const res = await api.login({
      username,
      password: password.toString(),
      captcha_id: loginInfo.value.captcha_id,
      captcha_code: captchaCode,
    })
    $message.success(t('views.login.message_login_success'))
    setToken(res.data.access_token)
    await addDynamicRoutes()
    const redirectPath = normalizeRedirectPath(query.redirect)
    const targetPath = resolveRoleTargetPath(redirectPath)
    if (redirectPath) {
      Reflect.deleteProperty(query, 'redirect')
      router.push({ path: targetPath, query })
    } else {
      router.push(targetPath)
    }
  } catch (e) {
    // ignore login error detail in production logs
    await fetchLoginCaptcha()
    loginInfo.value.captcha_code = ''
  }
  loading.value = false
}

async function fetchLoginCaptcha() {
  const res = await api.getCaptcha()
  loginInfo.value.captcha_id = res.data.captcha_id
  loginCaptchaImage.value = `data:image/png;base64,${res.data.image_base64}`
}

async function fetchPartnerCaptcha() {
  const res = await api.getCaptcha()
  partnerForm.value.captcha_id = res.data.captcha_id
  partnerCaptchaImage.value = `data:image/png;base64,${res.data.image_base64}`
}

async function fetchPublicConfig() {
  try {
    const res = await api.getPublicConfig()
    appStore.setSiteConfig(res.data || {})
    if (!isSelectedRegisterTypeEnabled()) {
      partnerForm.value.register_type = getDefaultRegisterType()
    }
  } catch (error) {
    // ignore public config fetch errors
  }
}

function isSelectedRegisterTypeEnabled() {
  if (partnerForm.value.register_type === 'channel') return appStore.allowChannelRegister
  if (partnerForm.value.register_type === 'user') return appStore.allowUserRegister
  return false
}

function openPartnerRegisterModal() {
  const registerType = getDefaultRegisterType()
  if (!registerType) {
    $message.warning('当前暂未开放注册，如需开通请联系平台管理员')
    return
  }
  partnerForm.value.register_type = registerType
  showPartnerModal.value = true
}

watch(showPartnerModal, async (v) => {
  if (v) {
    if (!isSelectedRegisterTypeEnabled()) {
      partnerForm.value.register_type = getDefaultRegisterType()
    }
    await fetchPartnerCaptcha()
  } else {
    resetPartnerRegisterState()
  }
})

function submitPartnerRegister() {
  if (!isSelectedRegisterTypeEnabled()) {
    $message.warning('当前注册类型暂未开放')
    return
  }
  partnerFormRef.value?.validate(async (err) => {
    if (err) return
    try {
      partnerSubmitting.value = true
      if (partnerForm.value.register_type === 'user') {
        await api.userRegister(partnerForm.value)
      } else {
        await api.channelRegister(partnerForm.value)
      }
      $message.success('注册申请已提交，我们会在24小时内完成审核')
      showPartnerModal.value = false
    } catch (error) {
      await fetchPartnerCaptcha()
    } finally {
      partnerSubmitting.value = false
    }
  })
}

async function openCaptchaModal() {
  if (!isSelectedRegisterTypeEnabled()) {
    $message.warning('当前注册类型暂未开放')
    return
  }
  if (!partnerForm.value.email?.trim()) {
    $message.warning('请先填写邮箱地址，再发送验证码')
    return
  }
  partnerForm.value.captcha_code = ''
  await fetchPartnerCaptcha()
  showCaptchaModal.value = true
}

async function sendEmailCode() {
  const email = partnerForm.value.email?.trim()
  const captchaCode = partnerForm.value.captcha_code?.trim()
  const captchaId = partnerForm.value.captcha_id

  if (!email) {
    $message.warning('请先填写邮箱地址')
    return
  }
  if (!captchaId) {
    await fetchPartnerCaptcha()
    $message.warning('图形验证码已更新，请输入后继续')
    return
  }
  if (!captchaCode) {
    $message.warning('请先填写图形验证码，再发送邮箱验证码')
    return
  }
  try {
    emailCodeSending.value = true
    await api.sendEmailCode({
      email,
      captcha_id: captchaId,
      captcha_code: captchaCode,
      register_type: partnerForm.value.register_type,
    })
    $message.success('验证码已发送，请注意查收邮箱')
    showCaptchaModal.value = false
    startEmailCooldown()
    await fetchPartnerCaptcha()
  } catch (error) {
    await fetchPartnerCaptcha()
  } finally {
    emailCodeSending.value = false
  }
}

function startEmailCooldown(seconds = 60) {
  emailCodeCooldown.value = seconds
  if (emailCodeTimer) {
    clearInterval(emailCodeTimer)
  }
  emailCodeTimer = setInterval(() => {
    if (emailCodeCooldown.value <= 1) {
      emailCodeCooldown.value = 0
      clearInterval(emailCodeTimer)
      emailCodeTimer = null
      return
    }
    emailCodeCooldown.value -= 1
  }, 1000)
}

onBeforeUnmount(() => {
  resetEmailCooldown()
})

function resetEmailCooldown() {
  if (emailCodeTimer) {
    clearInterval(emailCodeTimer)
    emailCodeTimer = null
  }
  emailCodeCooldown.value = 0
}

function resetPartnerRegisterState() {
  showCaptchaModal.value = false
  partnerSubmitting.value = false
  emailCodeSending.value = false
  partnerCaptchaImage.value = ''
  partnerForm.value = {
    register_type: getDefaultRegisterType() || 'channel',
    company_name: '',
    contact_name: '',
    email: '',
    phone: '',
    hardware_id: '',
    password: '',
    email_code: '',
    captcha_id: '',
    captcha_code: '',
    agree_protocol: false,
  }
  resetEmailCooldown()
}

function validatePasswordPolicy(value) {
  const text = String(value || '')
  if (!text) return new Error('请输入密码')
  const minLength = appStore.passwordMinLength || 8
  const minCategories = (appStore.passwordRequiredCategories || []).length || 2
  if (text.length < minLength) {
    return new Error(`密码长度至少 ${minLength} 位`)
  }
  const hasLetter = /[A-Za-z]/.test(text)
  const hasDigit = /\d/.test(text)
  const hasSpecial = /[^A-Za-z\d]/.test(text)
  const categories = [hasLetter, hasDigit, hasSpecial].filter(Boolean).length
  if (categories < minCategories) {
    return new Error('密码必须包含字母、数字、特殊字符中的任意两类')
  }
  return true
}

async function fetchForgotCaptcha() {
  const res = await api.getCaptcha()
  forgotForm.value.captcha_id = res.data.captcha_id
  forgotCaptchaImage.value = `data:image/png;base64,${res.data.image_base64}`
}

async function openForgotPasswordModal() {
  showForgotPasswordModal.value = true
  forgotForm.value.captcha_code = ''
  await fetchForgotCaptcha()
}

async function sendForgotCode() {
  if (!forgotForm.value.email?.trim()) {
    $message.warning('请先填写邮箱')
    return
  }
  if (!forgotForm.value.captcha_id || !forgotForm.value.captcha_code?.trim()) {
    $message.warning('请先填写图形验证码')
    return
  }
  try {
    forgotCodeSending.value = true
    await api.sendResetPasswordCode({
      email: forgotForm.value.email.trim(),
      captcha_id: forgotForm.value.captcha_id,
      captcha_code: forgotForm.value.captcha_code.trim(),
    })
    $message.success('验证码已发送，请查收邮箱')
    startForgotCodeCooldown()
    await fetchForgotCaptcha()
  } finally {
    forgotCodeSending.value = false
  }
}

function startForgotCodeCooldown(seconds = 60) {
  forgotCodeCooldown.value = seconds
  if (forgotCodeTimer) clearInterval(forgotCodeTimer)
  forgotCodeTimer = setInterval(() => {
    if (forgotCodeCooldown.value <= 1) {
      forgotCodeCooldown.value = 0
      clearInterval(forgotCodeTimer)
      forgotCodeTimer = null
      return
    }
    forgotCodeCooldown.value -= 1
  }, 1000)
}

async function submitForgotPassword() {
  forgotFormRef.value?.validate(async (err) => {
    if (err) return
    try {
      forgotSubmitting.value = true
      await api.resetPasswordByEmail({
        email: forgotForm.value.email.trim(),
        email_code: forgotForm.value.email_code.trim(),
        new_password: forgotForm.value.new_password,
      })
      $message.success('密码重置成功，请使用新密码登录')
      showForgotPasswordModal.value = false
    } finally {
      forgotSubmitting.value = false
    }
  })
}

watch(showForgotPasswordModal, (v) => {
  if (!v) {
    forgotForm.value = {
      email: '',
      captcha_id: '',
      captcha_code: '',
      email_code: '',
      new_password: '',
    }
    forgotCaptchaImage.value = ''
    if (forgotCodeTimer) {
      clearInterval(forgotCodeTimer)
      forgotCodeTimer = null
    }
    forgotCodeCooldown.value = 0
  }
})

</script>

<style scoped>
.login-page-shell {
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(244, 81, 30, 0.035), rgba(244, 81, 30, 0) 220px),
    #f5f6fb;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  box-sizing: border-box;
  color: #1f2937;
  overflow: auto;
  position: relative;
}

.login-page-shell::before {
  content: '';
  position: absolute;
  inset: 0;
  background: url('@/assets/images/login_bg.webp') center / cover no-repeat;
  opacity: 0.42;
}

.login-page-shell::after {
  display: none;
}

.login-wrap {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 1120px;
  min-height: auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 18px;
  align-items: stretch;
}

.brand-panel,
.auth-panel {
  min-width: 0;
  border: 1px solid #e5e7eb;
  background: rgba(255, 255, 255, 0.94);
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(31, 41, 55, 0.07);
}

.brand-panel {
  padding: 30px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
  position: relative;
}

.brand-panel::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--primary-color);
}

.brand-panel::after {
  display: none;
}

.brand-identity {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-logo-mark {
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: var(--primary-color);
  background: rgba(244, 81, 30, 0.08);
  border: 1px solid rgba(244, 81, 30, 0.18);
}

.brand-eyebrow {
  margin: 0 0 6px;
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}

.brand-identity h1 {
  margin: 0;
  color: #111827;
  font-size: 25px;
  line-height: 1.2;
}

.hero-copy {
  position: relative;
  z-index: 1;
  margin-top: 38px;
  max-width: 600px;
}

.hero-copy h2 {
  margin: 0;
  color: #111827;
  font-size: clamp(30px, 3.2vw, 40px);
  line-height: 1.22;
  font-weight: 900;
  letter-spacing: 0;
}

.hero-copy p {
  margin: 16px 0 0;
  max-width: 520px;
  color: #6b7280;
  font-size: 15px;
  line-height: 1.75;
}

.operations-board {
  position: relative;
  z-index: 1;
  margin-top: 28px;
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.capability-item {
  display: flex;
  gap: 12px;
  padding: 14px;
  color: var(--primary-color);
  border-radius: 8px;
  border: 1px solid #eef1f5;
  background: #fafafa;
}

.capability-item h4 {
  margin: 0;
  font-size: 15px;
  color: #1f2937;
}

.capability-item p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.55;
}

.support-strip {
  position: relative;
  z-index: 1;
  margin-top: 24px;
  display: grid;
  grid-template-columns: 1fr 0.72fr;
  gap: 12px;
}

.support-strip div {
  border-left: 3px solid var(--primary-color);
  padding-left: 12px;
}

.support-strip span {
  display: block;
  color: #6b7280;
  font-size: 12px;
  margin-bottom: 4px;
}

.support-strip strong {
  color: #1f2937;
  font-size: 15px;
}

.auth-panel {
  display: flex;
  align-items: stretch;
  padding: 30px;
}

.auth-card {
  width: 100%;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  color: #0f172a;
}

.auth-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 24px;
}

.auth-kicker {
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0;
}

.auth-panel h3 {
  margin: 0;
  color: #0f172a;
  font-size: 30px;
  line-height: 1.2;
}

.auth-tip {
  margin: 7px 0 0;
  color: #64748b;
  font-size: 13px;
}

.auth-head-icon {
  flex: none;
  color: var(--primary-color);
  font-size: 36px;
}

.auth-form-item {
  margin-top: 15px;
}

.auth-form-item label {
  display: block;
  margin-bottom: 7px;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.captcha-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.captcha-img {
  flex: none;
  width: 122px;
  height: 36px;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  cursor: pointer;
  object-fit: cover;
}

.login-btn {
  margin-top: 22px;
  width: 100%;
  height: 46px;
  font-weight: 900;
}

.auth-links {
  margin-top: 14px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.agreement-row {
  margin-top: 14px;
  color: #475569;
  font-size: 13px;
}

.agreement-link {
  padding: 0;
  margin: 0 2px;
  height: auto;
  font-size: 13px;
}

.service-register-modal {
  border-radius: 12px;
  background: linear-gradient(180deg, #fcfcfd 0%, #f9fafc 100%);
  border: 1px solid #eef1f5;
  padding: 14px 14px 10px;
}

.register-head h4 {
  margin: 0;
  font-size: 18px;
  color: #1f2937;
}

.register-head p {
  margin: 6px 0 10px;
  color: #6b7280;
  font-size: 13px;
}

.register-type-switch {
  display: flex;
  gap: 10px;
}

.email-code-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.register-hotline {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
  color: #d03050;
  font-size: 14px;
  font-weight: 700;
}

.captcha-modal-panel {
  border-radius: 12px;
  background: linear-gradient(180deg, #fcfcfd 0%, #f9fafc 100%);
  border: 1px solid #eef1f5;
  padding: 14px;
}

.captcha-modal-head h4 {
  margin: 0;
  font-size: 16px;
  color: #1f2937;
}

.captcha-modal-head p {
  margin: 6px 0 10px;
  color: #6b7280;
  font-size: 13px;
}

.captcha-modal-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.captcha-modal-img {
  height: 40px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  cursor: pointer;
}

.protocol-body {
  max-height: 58vh;
  overflow-y: auto;
  line-height: 1.8;
  color: #374151;
}

.protocol-body h4 {
  margin: 0 0 6px;
  font-size: 16px;
  color: #1f2937;
}

.protocol-body p {
  margin: 0 0 14px;
  font-size: 14px;
}

@media (max-width: 980px) {
  .login-page-shell {
    padding: 16px;
  }

  .login-wrap {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .brand-panel {
    padding: 24px;
  }

  .auth-panel {
    padding: 24px;
  }

  .operations-board,
  .support-strip {
    grid-template-columns: 1fr;
  }

  .capability-grid {
    grid-template-columns: 1fr;
  }

  .auth-card {
    min-height: auto;
  }
}
</style>
