/**
 * AC-F-11「图谱节点类型」: the legend has exactly three groups — 疾病 / 症状 /
 * 其他 — so every non-Disease, non-Symptom label collapses to 其他, and a node
 * is coloured the same way wherever it is rendered.
 */

export const NODE_GROUPS = { Disease: 'disease', Symptom: 'symptom' }

export const NODE_GROUP_LABELS = {
  disease: '疾病',
  symptom: '症状',
  other: '其他',
}

export const NODE_GROUP_COLORS = {
  disease: '#d64545',
  symptom: '#2f6fdd',
  other: '#6b7280',
}

export function nodeGroup(label) {
  return NODE_GROUPS[label] ?? 'other'
}

export function nodeGroupLabel(label) {
  return NODE_GROUP_LABELS[nodeGroup(label)]
}

export function nodeColor(label) {
  return NODE_GROUP_COLORS[nodeGroup(label)]
}
