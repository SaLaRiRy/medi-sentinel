/** Vectorization state labels (AC-F-11): 0-3 mapped, anything else is unknown. */

export const VECTOR_STATUS_LABELS = {
  0: '已上传',
  1: '处理中',
  2: '已向量化',
  3: '失败',
}

/** el-tag 的 type（AC-F-11）；未知值回退与「未知状态」一致的中性色。 */
export const VECTOR_STATUS_COLORS = {
  0: 'info',
  1: 'warning',
  2: 'success',
  3: 'danger',
}

export const UNKNOWN_VECTOR_STATUS_LABEL = '未知状态'
export const UNKNOWN_VECTOR_STATUS_COLOR = 'info'

export function vectorStatusLabel(status) {
  return VECTOR_STATUS_LABELS[status] ?? UNKNOWN_VECTOR_STATUS_LABEL
}

export function vectorStatusColor(status) {
  return VECTOR_STATUS_COLORS[status] ?? UNKNOWN_VECTOR_STATUS_COLOR
}
