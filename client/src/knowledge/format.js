/**
 * 知识库文件大小展示（视觉重做 第二阶段）。
 *
 * 后端 `file_size` 是字节数；列表里转成人类可读的 KB / MB，
 * 未知或非法值回退到 `-`（与其它展示映射的默认值一致）。
 */

function trim(value) {
  return value >= 100 ? value.toFixed(0) : value.toFixed(1)
}

export function formatFileSize(bytes) {
  if (bytes === null || bytes === undefined || bytes === '') return '-'
  const size = Number(bytes)
  if (!Number.isFinite(size) || size < 0) return '-'
  if (size < 1024) return `${size} B`

  const kb = size / 1024
  if (kb < 1024) return `${trim(kb)} KB`

  return `${trim(kb / 1024)} MB`
}
