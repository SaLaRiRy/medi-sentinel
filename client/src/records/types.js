/**
 * 档案类型的建议取值（FUNCTIONAL_SPEC 4.3.6）。`record_type` 在后端是自由文本
 * （1..50），这里只是界面的候选列表，表单默认「门诊记录」。
 */

export const RECORD_TYPES = ['门诊记录', '住院记录', '体检报告', '复诊记录', '其他']

export const DEFAULT_RECORD_TYPE = RECORD_TYPES[0]
