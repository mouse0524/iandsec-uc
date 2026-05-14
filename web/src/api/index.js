import { request } from '@/utils'

export default {
  login: (data) => request.post('/base/access_token', data, { noNeedToken: true }),
  getCaptcha: () => request.get('/base/captcha', { noNeedToken: true }),
  getPublicConfig: () => request.get('/base/public_config', { noNeedToken: true }),
  getWorkbenchStats: () => request.get('/base/workbench_stats'),
  sendEmailCode: (data = {}) => request.post('/base/send_email_code', data, { noNeedToken: true }),
  sendResetPasswordCode: (data = {}) => request.post('/base/send_reset_password_code', data, { noNeedToken: true }),
  resetPasswordByEmail: (data = {}) => request.post('/base/reset_password_by_email', data, { noNeedToken: true }),
  getUserInfo: () => request.get('/base/userinfo'),
  getUserMenu: () => request.get('/base/usermenu'),
  getUserApi: () => request.get('/base/userapi'),
  // profile
  updatePassword: (data = {}) => request.post('/base/update_password', data),
  // users
  getUserList: (params = {}) => request.get('/user/list', { params }),
  getUserById: (params = {}) => request.get('/user/get', { params }),
  createUser: (data = {}) => request.post('/user/create', data),
  updateUser: (data = {}) => request.post('/user/update', data),
  deleteUser: (params = {}) => request.delete(`/user/delete`, { params }),
  resetPassword: (data = {}) => request.post(`/user/reset_password`, data),
  // role
  getRoleList: (params = {}) => request.get('/role/list', { params }),
  createRole: (data = {}) => request.post('/role/create', data),
  updateRole: (data = {}) => request.post('/role/update', data),
  deleteRole: (params = {}) => request.delete('/role/delete', { params }),
  updateRoleAuthorized: (data = {}) => request.post('/role/authorized', data),
  getRoleAuthorized: (params = {}) => request.get('/role/authorized', { params }),
  // menus
  getMenus: (params = {}) => request.get('/menu/list', { params }),
  createMenu: (data = {}) => request.post('/menu/create', data),
  updateMenu: (data = {}) => request.post('/menu/update', data),
  deleteMenu: (params = {}) => request.delete('/menu/delete', { params }),
  // apis
  getApis: (params = {}) => request.get('/api/list', { params }),
  createApi: (data = {}) => request.post('/api/create', data),
  updateApi: (data = {}) => request.post('/api/update', data),
  deleteApi: (params = {}) => request.delete('/api/delete', { params }),
  refreshApi: (data = {}) => request.post('/api/refresh', data),
  // depts
  getDepts: (params = {}) => request.get('/dept/list', { params }),
  createDept: (data = {}) => request.post('/dept/create', data),
  updateDept: (data = {}) => request.post('/dept/update', data),
  deleteDept: (params = {}) => request.delete('/dept/delete', { params }),
  // auditlog
  getAuditLogList: (params = {}) => request.get('/auditlog/list', { params }),
  // ticket
  uploadTicketAttachment: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/ticket/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  createTicket: (data = {}) => request.post('/ticket/create', data),
  getTicketPrefill: () => request.get('/ticket/prefill'),
  getTicketList: (params = {}) => request.get('/ticket/list', { params }),
  getTicketById: (params = {}) => request.get('/ticket/get', { params }),
  updateTicket: (data = {}) => request.post('/ticket/update', data),
  reviewTicket: (data = {}) => request.post('/ticket/review', data),
  techActionTicket: (data = {}) => request.post('/ticket/tech/action', data),
  downloadTicketAttachment: (params = {}) =>
    request.get('/ticket/attachment/download', {
      params,
      responseType: 'blob',
    }),
  resubmitTicket: (data = {}) => request.post('/ticket/resubmit', data),
  getTicketActions: (params = {}) => request.get('/ticket/actions', { params }),
  uploadPublicTicketAttachment: (file, captcha = {}) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('captcha_id', captcha.captcha_id || '')
    formData.append('captcha_code', captcha.captcha_code || '')
    return request.post('/public/ticket/upload', formData, {
      noNeedToken: true,
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  createPublicTicket: (data = {}) => request.post('/public/ticket/create', data, { noNeedToken: true }),
  // partner
  channelRegister: (data = {}) =>
    request.post('/partner/register', { ...data, register_type: 'channel' }, { noNeedToken: true }),
  userRegister: (data = {}) =>
    request.post('/partner/register', { ...data, register_type: 'user' }, { noNeedToken: true }),
  getPartnerRegisterList: (params = {}) => {
    const query = { ...params }
    if (query.register_type === 'all' || query.register_type === '' || query.register_type == null) {
      delete query.register_type
    } else {
      query.register_type = String(query.register_type)
    }
    if (query.reviewed == null || query.reviewed === '') {
      delete query.reviewed
    }
    if (!query.keyword) delete query.keyword
    return request.get('/partner/register/list', { params: query })
  },
  reviewPartnerRegister: (data = {}) => request.post('/partner/register/review', data),
  // global notice
  createNotice: (data = {}) => request.post('/notice/create', data),
  getNoticeList: (params = {}) => request.get('/notice/list', { params }),
  getNoticeInbox: (params = {}) => request.get('/notice/inbox', { params }),
  getNoticeUnreadCount: () => request.get('/notice/unread_count'),
  readNotice: (data = {}) => request.post('/notice/read', data),
  readAllNotice: () => request.post('/notice/read_all'),
  // settings
  getSystemSettings: () => request.get('/settings/get'),
  updateSystemSettings: (data = {}) => request.post('/settings/update', data),
  testWebdavConnection: (data = {}) => request.post('/settings/webdav/test', data),
  uploadSiteLogo: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/settings/upload_logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  // webdav
  webdavList: (params = {}) => request.get('/webdav/list', { params }),
  webdavCreateShare: (data = {}) => request.post('/webdav/share/create', data),
  webdavShareList: (params = {}) => request.get('/webdav/share/list', { params }),
  webdavShareDelete: (data = {}) => request.post('/webdav/share/delete', data),
  // skill know - folders
  skillKnowFolders: (params = {}) => request.get('/skill-know/folders/list', { params }),
  skillKnowCreateFolder: (data = {}) => request.post('/skill-know/folders/create', data),
  skillKnowUpdateFolder: (data = {}) => request.post('/skill-know/folders/update', data),
  skillKnowDeleteFolder: (params = {}) => request.delete('/skill-know/folders/delete', { params }),
  // skill know - documents
  skillKnowInitChunkUpload: (data = {}) => request.post('/skill-know/documents/upload/init', data, { timeout: 300000 }),
  skillKnowUploadChunk: (formData) => request.post('/skill-know/documents/upload/chunk', formData, {
    timeout: 90000,
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  skillKnowChunkUploadStatus: (params = {}) => request.get('/skill-know/documents/upload/status', { params, timeout: 300000 }),
  skillKnowCompleteChunkUpload: (data = {}) => request.post('/skill-know/documents/upload/complete', data, { timeout: 300000 }),
  skillKnowUploadDocument: (file, data = {}) => {
    const formData = new FormData()
    formData.append('file', file)
    Object.keys(data).forEach((key) => {
      if (data[key] !== undefined && data[key] !== null && data[key] !== '') formData.append(key, data[key])
    })
    return request.post('/skill-know/documents/upload', formData, {
      timeout: 300000,
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  skillKnowDocuments: (params = {}) => request.get('/skill-know/documents/list', { params }),
  skillKnowGetDocument: (params = {}) => request.get('/skill-know/documents/get', { params }),
  skillKnowUpdateDocument: (data = {}) => request.post('/skill-know/documents/update', data),
  skillKnowDeleteDocument: (params = {}) => request.delete('/skill-know/documents/delete', { params }),
  skillKnowMoveDocument: (data = {}) => request.post('/skill-know/documents/move', data),
  skillKnowSearchDocuments: (params = {}) => request.get('/skill-know/documents/search', { params }),
  skillKnowReindexDocument: (params = {}) => request.post('/skill-know/documents/reindex', null, { params }),
  // skill know - chat/prompts/settings
  skillKnowChat: (data = {}) => request.post('/skill-know/chat', data),
  skillKnowConversations: (params = {}) => request.get('/skill-know/chat/conversations', { params }),
  skillKnowGetConversation: (params = {}) => request.get('/skill-know/chat/conversations/get', { params }),
  skillKnowConversationMessages: (params = {}) => request.get('/skill-know/chat/conversations/messages', { params }),
  skillKnowConversationStats: (params = {}) => request.get('/skill-know/chat/conversations/stats', { params }),
  skillKnowDeleteConversation: (params = {}) => request.delete('/skill-know/chat/conversations/delete', { params }),
  skillKnowFeedbackMessage: (data = {}) => request.post('/skill-know/chat/messages/feedback', data),
  skillKnowFeedbackList: (params = {}) => request.get('/skill-know/chat/feedback/list', { params }),
  skillKnowLearningCandidates: (params = {}) => request.get('/skill-know/chat/learning/candidates', { params }),
  skillKnowCreateLearningCandidate: (data = {}) => request.post('/skill-know/chat/learning/candidates/create', data),
  skillKnowApproveLearningCandidate: (data = {}) => request.post('/skill-know/chat/learning/candidates/approve', data),
  skillKnowRejectLearningCandidate: (data = {}) => request.post('/skill-know/chat/learning/candidates/reject', data),
  skillKnowPrompts: (params = {}) => request.get('/skill-know/prompts/list', { params }),
  skillKnowGetPrompt: (params = {}) => request.get('/skill-know/prompts/get', { params }),
  skillKnowUpdatePrompt: (key, data = {}) => request.post(`/skill-know/prompts/update?key=${encodeURIComponent(key)}`, data),
  skillKnowResetPrompt: (key) => request.post(`/skill-know/prompts/reset?key=${encodeURIComponent(key)}`),
  skillKnowSyncDefaultPrompts: () => request.post('/skill-know/prompts/sync-defaults'),
  skillKnowSetupState: () => request.get('/skill-know/llm-settings/state'),
  skillKnowSetupChecklist: () => request.get('/skill-know/llm-settings/checklist'),
  skillKnowProviders: () => request.get('/skill-know/llm-settings/providers'),
  skillKnowProviderModels: (providerId) => request.get(`/skill-know/llm-settings/providers/${providerId}/models`),
  skillKnowCompleteSetup: (data = {}) => request.post('/skill-know/llm-settings/essential', data),
  skillKnowTestConnection: (data = {}) => request.post('/skill-know/llm-settings/test-connection', data),
  skillKnowResetSetup: () => request.post('/skill-know/llm-settings/reset'),
  skillKnowHealth: () => request.get('/skill-know/health'),
  skillKnowHealthDetail: () => request.get('/skill-know/health/detail'),
}
