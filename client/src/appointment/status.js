/**
 * 预约状态展示映射（AC-F-11 / FUNCTIONAL_SPEC 5.20）。
 *
 * 0 待确认 / 1 已确认 / 2 已完成 / 3 已取消；未知值回退到既定默认「待确认」。
 * 着色只在医生端使用（warning / success / info / danger）。
 */

export const APPOINTMENT_STATUS_LABELS = {
  0: '待确认',
  1: '已确认',
  2: '已完成',
  3: '已取消',
}

export const APPOINTMENT_STATUS_COLORS = {
  0: 'warning',
  1: 'success',
  2: 'info',
  3: 'danger',
}

export const UNKNOWN_APPOINTMENT_STATUS_LABEL = APPOINTMENT_STATUS_LABELS[0]

/** 医生端与管理端可写入的三个目标状态（跳过默认态 0「待确认」）。 */
export const APPOINTMENT_STATUS_ACTIONS = [
  { value: 1, label: '确认' },
  { value: 2, label: '完成' },
  { value: 3, label: '取消' },
]

export function appointmentStatusLabel(status) {
  return APPOINTMENT_STATUS_LABELS[status] ?? UNKNOWN_APPOINTMENT_STATUS_LABEL
}

export function appointmentStatusColor(status) {
  return APPOINTMENT_STATUS_COLORS[status] ?? APPOINTMENT_STATUS_COLORS[0]
}
