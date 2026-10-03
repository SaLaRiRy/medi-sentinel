/**
 * AC-F-11「图谱关系名」: the seven ontology relationship types have fixed
 * display names; anything the ontology does not know shows its raw value rather
 * than a blank cell.
 */

export const RELATION_LABELS = {
  HAS_SYMPTOM: '有症状',
  BELONGS_TO: '所属科室',
  RECOMMEND_DRUG: '推荐药物',
  NEED_CHECK: '需检查',
  ACCOMPANY_WITH: '并发症',
  SHOULD_EAT: '宜吃',
  AVOID_EAT: '忌吃',
}

export function relationLabel(type) {
  return RELATION_LABELS[type] ?? type
}
