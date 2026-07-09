import { request } from '@/utils'

export default {
  login: (data) => request.post('/base/access_token', data, { noNeedToken: true }),
  getCaptcha: () => request.get('/base/captcha', { noNeedToken: true }),
  getPublicConfig: () => request.get('/base/public_config', { noNeedToken: true }),
  getAppConfig: () => request.get('/base/app_config'),
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
  exportDepts: () => request.get('/dept/export', { responseType: 'blob' }),
  importDepts: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/dept/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })
  },
  // auditlog
  getAuditLogList: (params = {}) => request.get('/auditlog/list', { params }),
  archiveAuditLogs: (params = {}) => request.post('/auditlog/archive', null, { params }),
  clearAuditLogs: (params = {}) => request.post('/auditlog/clear', null, { params }),
  exportAuditLogs: (params = {}) =>
    request.get('/auditlog/export', {
      params,
      responseType: 'blob',
    }),
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
  exportTickets: (params = {}) =>
    request.get('/ticket/export', {
      params,
      responseType: 'blob',
    }),
  getTicketById: (params = {}) => request.get('/ticket/get', { params }),
  updateTicket: (data = {}) => request.post('/ticket/update', data),
  closeTicket: (data = {}) => request.post('/ticket/close', data),
  fieldVerificationTicket: (data = {}) => request.post('/ticket/field-verification', data),
  reviewTicket: (data = {}) => request.post('/ticket/review', data),
  techActionTicket: (data = {}) => request.post('/ticket/tech/action', data),
  assignTicketTech: (data = {}) => request.post('/ticket/assign-tech', data),
  pushTicketRedmine: (data = {}) => request.post('/ticket/redmine/push', data),
  pullTicketRedmine: (data = {}) => request.post('/ticket/redmine/pull', data),
  downloadTicketAttachment: (params = {}) =>
    request.get('/ticket/attachment/download', {
      params,
      responseType: 'blob',
    }),
  previewTicketAttachment: (params = {}) => request.get('/ticket/attachment/preview-cache', { params, timeout: 300000 }),
  resubmitTicket: (data = {}) => request.post('/ticket/resubmit', data),
  getTicketActions: (params = {}) => request.get('/ticket/actions', { params }),
  // project
  projectList: (params = {}) => request.get('/project/list', { params }),
  projectGet: (params = {}) => request.get('/project/get', { params }),
  uploadProjectAttachment: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/project/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  importProjects: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/project/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })
  },
  downloadProjectAttachment: (params = {}) =>
    request.get('/project/attachment/download', {
      params,
      responseType: 'blob',
    }),
  projectCreate: (data = {}) => request.post('/project/create', data),
  projectUpdate: (data = {}) => request.post('/project/update', data),
  projectSetStatus: (data = {}) => request.post('/project/status', data),
  projectAssign: (data = {}) => request.post('/project/assign', data),
  projectBatchUpdate: (data = {}) => request.post('/project/batch-update', data),
  projectBatchDelete: (data = {}) => request.post('/project/batch-delete', data),
  projectActivityList: (params = {}) => request.get('/project/activity/list', { params }),
  projectActivityCreate: (data = {}) => request.post('/project/activity/create', data),
  projectActivityUpdate: (data = {}) => request.post('/project/activity/update', data),
  projectActivityDelete: (data = {}) => request.post('/project/activity/delete', data),
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
  createPartnerInvite: () => request.post('/partner/invite/create'),
  // global notice
  createNotice: (data = {}) => request.post('/notice/create', data),
  getNoticeList: (params = {}) => request.get('/notice/list', { params }),
  getNoticeInbox: (params = {}) => request.get('/notice/inbox', { params }),
  getNoticeUnreadCount: () => request.get('/notice/unread_count'),
  readNotice: (data = {}) => request.post('/notice/read', data),
  readAllNotice: () => request.post('/notice/read_all'),
  // monitor
  monitorOverview: () => request.get('/monitor/overview'),
  monitorResources: () => request.get('/monitor/resources'),
  monitorMysql: () => request.get('/monitor/mysql'),
  monitorRedis: () => request.get('/monitor/redis'),
  monitorClearRedis: (params = {}) => request.post('/monitor/redis/clear', null, { params }),
  // terminal
  terminalAuthReports: (params = {}) => request.get('/terminal/auth/list', { params }),
  terminalLatestAuthReport: (params = {}) => request.get('/terminal/auth/latest', { params }),
  terminalUpgradeConfig: () => request.get('/terminal/upgrade/config'),
  terminalSaveUpgradeConfig: (data = {}) => request.post('/terminal/upgrade/config', data),
  terminalCheckUpgrade: (data = {}) => request.post('/public/terminal/upgrade/check', data, { noNeedToken: true }),
  // settings
  getSystemSettings: () => request.get('/settings/get'),
  updateSystemSettings: (data = {}) => request.post('/settings/update', data),
  getTimeSyncStatus: () => request.get('/settings/time-sync/status'),
  syncSystemTime: () => request.post('/settings/time-sync/sync'),
  testWebdavConnection: (data = {}) => request.post('/settings/webdav/test', data),
  getDatabaseBackupStatus: () => request.get('/settings/database-backup/status'),
  testDatabaseBackupDirectory: (data = {}) => request.post('/settings/database-backup/test', data),
  runDatabaseBackup: (data = {}) => request.post('/settings/database-backup/run', data, { timeout: 300000 }),
  getRedmineMetadata: (data = {}) => request.post('/settings/redmine/metadata', data),
  uploadSiteLogo: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/settings/upload_logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  // webdav
  webdavList: (params = {}) => request.get('/webdav/list', { params }),
  webdavClearCache: () => request.post('/webdav/cache/clear'),
  webdavDownload: (params = {}) => request.get('/webdav/download-url', { params }),
  webdavPreviewCache: (params = {}) => request.get('/webdav/preview-cache', { params, timeout: 300000 }),
  webdavOpsPassword: () => request.get('/webdav/ops-password'),
  webdavReplaceDecryptPassword: () => request.get('/webdav/replace-decrypt-password'),
  webdavCreateShare: (data = {}) => request.post('/webdav/share/create', data),
  webdavShareList: (params = {}) => request.get('/webdav/share/list', { params }),
  webdavShareDelete: (data = {}) => request.post('/webdav/share/delete', data),
  webdavDownloadLogList: (params = {}) => request.get('/webdav/download-log/list', { params }),
  // release records
  releaseViewList: () => request.get('/release/view-list'),
  releaseList: () => request.get('/release/list'),
  releaseSave: (data = {}) => request.post('/release/save', data),
  releaseDelete: (data = {}) => request.post('/release/delete', data),
  releaseClear: () => request.post('/release/clear'),
  // wiki
  wikiUploadSource: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/wiki/source/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })
  },
  wikiInitChunkUpload: (data = {}) => request.post('/wiki/source/upload/init', data, { timeout: 300000 }),
  wikiUploadChunk: (params = {}, file) => {
    const formData = new FormData()
    formData.append('chunk', file)
    return request.post('/wiki/source/upload/chunk', formData, {
      params,
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })
  },
  wikiCompleteChunkUpload: (data = {}) => request.post('/wiki/source/upload/complete', data, { timeout: 300000 }),
  wikiRetrySource: (params = {}) => request.post('/wiki/source/retry', null, { params }),
  wikiDeleteSource: (params = {}) => request.delete('/wiki/source/delete', { params }),
  wikiSourceList: (params = {}) => request.get('/wiki/source/list', { params }),
  wikiSourceMarkdown: (params = {}) => request.get('/wiki/source/markdown', { params }),
  wikiFileTree: () => request.get('/wiki/file/tree'),
  wikiFileGet: (params = {}) => request.get('/wiki/file/get', { params }),
  wikiAsset: (params = {}) => request.get('/wiki/asset', { params, responseType: 'blob' }),
  wikiConversations: (params = {}) => request.get('/wiki/conversations', { params }),
  wikiConversationGet: (params = {}) => request.get('/wiki/conversations/get', { params }),
  wikiHealth: () => request.get('/wiki/health'),
  wikiAsk: (data = {}) => request.post('/wiki/ask', data, { timeout: 300000 }),
  wikiMarkUnhelpful: (data = {}) => request.post('/wiki/feedback/unhelpful', data),
  wikiAdminMessages: (params = {}) => request.get('/wiki/admin/messages', { params }),
  wikiArchiveMessage: (params = {}) => request.post('/wiki/admin/messages/archive', null, { params }),
  wikiLearningList: (params = {}) => request.get('/wiki/learning/list', { params }),
  wikiLearningApprove: (data = {}) => request.post('/wiki/learning/approve', data),
  wikiLearningReject: (data = {}) => request.post('/wiki/learning/reject', data),
}
