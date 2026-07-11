export const ticketStatusTypeMap = {
  pending_review: 'warning',
  cs_rejected: 'error',
  tech_processing: 'info',
  test_filtering: 'warning',
  product_evaluation: 'info',
  rd_processing: 'info',
  test_verification: 'warning',
  field_verification: 'warning',
  pending_close: 'success',
  tech_rejected: 'error',
  done: 'success',
}

export const ticketStatusTextMap = {
  pending_review: '审核中',
  cs_rejected: '客服驳回',
  tech_processing: '技术处理中',
  test_filtering: '测试过滤',
  product_evaluation: '产品评估',
  rd_processing: '研发处理',
  test_verification: '测试验证',
  field_verification: '现场验证',
  pending_close: '待关闭',
  tech_rejected: '技术驳回',
  done: '已关闭',
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
    tech_note: '处理备注',
    test_filter: '测试过滤',
    product_evaluate: '产品评估',
    rd_process: '研发处理',
    test_verify: '测试验证',
    field_verify: '现场验证',
    field_reject: '验证不通过',
    tech_reject: '技术驳回',
    finish: '处理完成',
    close: '关闭工单',
  }
  return actionMap[action] || action || '-'
}
