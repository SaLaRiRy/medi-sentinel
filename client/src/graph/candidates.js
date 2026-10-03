/**
 * AC-F-14: the candidate list is shown by `coverage` descending, and a missing
 * `coverage` means "no progress bar" — never a 0% bar.
 */

export function sortedCandidates(candidates) {
  return [...(candidates ?? [])].sort(
    (left, right) => (right.coverage ?? -1) - (left.coverage ?? -1)
  )
}

export function coveragePercent(coverage) {
  return typeof coverage === 'number' ? Math.round(coverage * 100) : null
}
