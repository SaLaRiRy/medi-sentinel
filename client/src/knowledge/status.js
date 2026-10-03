/** Vectorization state labels (AC-F-11): 0-3 mapped, anything else is unknown. */

export const VECTOR_STATUS_LABELS = {
  0: '已上传',
  1: '处理中',
  2: '已向量化',
  3: '失败',
}

export const UNKNOWN_VECTOR_STATUS_LABEL = '未知状态'

export function vectorStatusLabel(status) {
  return VECTOR_STATUS_LABELS[status] ?? UNKNOWN_VECTOR_STATUS_LABEL
}
