/**
 * 账号状态展示映射（AC-F-11 / FUNCTIONAL_SPEC 5.20）。
 *
 * 1 → 正常（success）；其余（含 0 与未定义值）→ 禁用（danger）。按钮文案随当前
 * 状态取反：正常时是「禁用」，其余是「启用」。账号与科室共用同一套 0/1 语义
 * （FUNCTIONAL_SPEC 5.10）。
 */

export function accountStatusLabel(status) {
  return status === 1 ? '正常' : '禁用'
}

export function accountStatusColor(status) {
  return status === 1 ? 'success' : 'danger'
}

export function accountStatusAction(status) {
  return status === 1 ? '禁用' : '启用'
}

/** 点击状态按钮后要写入的目标状态值。 */
export function accountStatusToggleValue(status) {
  return status === 1 ? 0 : 1
}
