/**
 * 人工问诊工单状态展示映射（AC-F-11 / FUNCTIONAL_SPEC 5.10）。
 *
 * 0 待回复 / 1 已回复；未知值回退到既定默认「待回复」。后端回复时无条件置 1。
 */

export const CONSULT_STATUS_LABELS = {
  0: '待回复',
  1: '已回复',
}

export const CONSULT_STATUS_COLORS = {
  0: 'warning',
  1: 'success',
}

export const UNKNOWN_CONSULT_STATUS_LABEL = CONSULT_STATUS_LABELS[0]

export function consultStatusLabel(status) {
  return CONSULT_STATUS_LABELS[status] ?? UNKNOWN_CONSULT_STATUS_LABEL
}

export function consultStatusColor(status) {
  return CONSULT_STATUS_COLORS[status] ?? CONSULT_STATUS_COLORS[0]
}
