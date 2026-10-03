/**
 * AC-F-13: the knowledge list keeps polling while any row is still 0「已上传」
 * or 1「处理中」, and stops as soon as every row has settled.
 */

export const POLL_INTERVAL_MS = 3000

export const PENDING_VECTOR_STATUSES = new Set([0, 1])

export function needsPolling(items) {
  return (items ?? []).some((item) =>
    PENDING_VECTOR_STATUSES.has(item?.vector_status)
  )
}
