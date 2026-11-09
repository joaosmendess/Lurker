/** Fit bands from docs/ui-research.md: high ≥ 75, mid 50-74, low < 50. */
function fitBand(score: number): 'high' | 'mid' | 'low' {
  if (score >= 75) return 'high'
  if (score >= 50) return 'mid'
  return 'low'
}

const BAND_CLASS = {
  high: 'border-fit-high text-fit-high',
  mid: 'border-fit-mid text-fit-mid',
  low: 'border-rule text-fit-low',
} as const

interface ScoreStampProps {
  /** null keeps the column's width, so titles stay aligned in a mixed list */
  score: number | null
  size?: 'sm' | 'lg'
}

/**
 * The AI score as a classified-ad code: a mono number in a thin box, left of each job.
 * The signature of direction A. The color repeats what the number says, never replaces it.
 */
export function ScoreStamp({ score, size = 'sm' }: ScoreStampProps) {
  const box = size === 'lg' ? 'w-14 py-1 text-2xl' : 'w-9 py-px text-sm'
  if (score === null) return <span aria-hidden="true" className={`${box} shrink-0`} />

  return (
    <span
      aria-label={`Nota ${score} de 100`}
      title={`Nota da IA: ${score} de 100`}
      className={`${box} ${BAND_CLASS[fitBand(score)]} inline-flex shrink-0 justify-center rounded border font-mono font-semibold tabular-nums`}
    >
      {score}
    </span>
  )
}
