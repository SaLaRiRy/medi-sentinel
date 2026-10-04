/**
 * 文章 / 公告状态展示映射（FUNCTIONAL_SPEC 5.20 / AC-F-11）。
 *
 * 1 → 已发布（success）；其余（含 0 与未定义值）→ 已下架（info）。文章分类沿用
 * 功能规格的 6 个建议值，界面同时允许自由输入（FUNCTIONAL_SPEC 5.17）。
 */

export const ARTICLE_CATEGORIES = [
  '健康科普',
  '疾病预防',
  '用药指南',
  '营养饮食',
  '运动康复',
  '其他',
]

export function contentStatusLabel(status) {
  return status === 1 ? '已发布' : '已下架'
}

export function contentStatusColor(status) {
  return status === 1 ? 'success' : 'info'
}
