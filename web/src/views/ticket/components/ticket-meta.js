export const ticketStatusTypeMap = {
  pending_review: 'warning',
  cs_rejected: 'error',
  tech_processing: 'info',
  tech_rejected: 'error',
  done: 'success',
}

export const ticketStatusTextMap = {
  pending_review: '审核中',
  cs_rejected: '客服驳回',
  tech_processing: '技术处理中',
  tech_rejected: '技术驳回',
  done: '已完成',
}

export const ticketStatusOptions = Object.entries(ticketStatusTextMap).map(([value, label]) => ({
  value,
  label,
}))

export function mapTicketActionText(action) {
  const actionMap = {
    submit: '提交工单',
    resubmit: '重新提交',
    cs_approve: '客服通过',
    cs_reject: '客服驳回',
    tech_start: '技术接手',
    tech_assign: '改派技术',
    tech_progress: '处理备注',
    tech_reject: '技术驳回',
    finish: '处理完成',
  }
  return actionMap[action] || action || '-'
}
