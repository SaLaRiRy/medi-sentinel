/**
 * 统计数据展示映射（AC-F-11 / FUNCTIONAL_SPEC 2.9）。
 *
 * 知识库类型是自由文本（`t_knowledge_file.file_type` 由上传时的扩展名映射得到，
 * 未识别的扩展名落为 `unknown`），所以按类型的分布里可能出现任意值；未知值回退
 * 到既定默认「未知类型」，与其它状态映射（向量化状态回退「未知状态」）一致。
 */

export const KNOWLEDGE_TYPE_LABELS = {
  txt: '文本',
  markdown: 'Markdown',
  md: 'Markdown',
  pdf: 'PDF',
  doc: 'Word',
  docx: 'Word',
}

export const UNKNOWN_KNOWLEDGE_TYPE_LABEL = '未知类型'

export function knowledgeTypeLabel(type) {
  return KNOWLEDGE_TYPE_LABELS[type] ?? UNKNOWN_KNOWLEDGE_TYPE_LABEL
}
