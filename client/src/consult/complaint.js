/**
 * 主诉的前后端编码约定（AC-F-15 / FUNCTIONAL_SPEC 5.15 / SPEC.md 5.15）。
 *
 * 后端把主诉当作一个不透明字符串：患者提交时前端拼成「标题：正文」（全角冒号），
 * 医生端展示时按 **第一个** 全角冒号拆回；无冒号时整串作为标题，正文为空。
 */

export const FULLWIDTH_COLON = '：'

export function encodeChiefComplaint(title, body) {
  return `${title}${FULLWIDTH_COLON}${body}`
}

export function decodeChiefComplaint(complaint) {
  const text = complaint ?? ''
  const index = text.indexOf(FULLWIDTH_COLON)
  if (index === -1) return { title: text, body: '' }
  return { title: text.slice(0, index), body: text.slice(index + 1) }
}
