import { useState } from 'react'

import { useToast } from '../components/toast-context'
import { ApiError } from '../lib/api'
import { formatTime } from '../lib/format'
import { useLLMStatus, useRefreshJobs, useScoringStatus, useStartScoring } from '../lib/queries'

/** The AI in the sidebar: how many jobs have a score, and the "analyze" button. */
export function ScoringPanel() {
  const llm = useLLMStatus()
  const status = useScoringStatus()
  const start = useStartScoring()
  const refreshJobs = useRefreshJobs()
  const showToast = useToast()
  // How many were scored when the list was last refreshed, to offer "show new scores"
  const [shownAnalyzed, setShownAnalyzed] = useState<number | null>(null)
  const analyzedNow = status.data?.analyzed
  // Setting state while rendering is allowed for "remember the first value seen":
  // React re-renders right away, before painting (react.dev, "storing information
  // from previous renders")
  if (shownAnalyzed === null && analyzedNow !== undefined) setShownAnalyzed(analyzedNow)

  if (!llm.data?.configured || !status.data) return null
  const data = status.data
  const newScores = shownAnalyzed === null ? 0 : data.analyzed - shownAnalyzed

  function handleStart() {
    start.mutate(undefined, {
      onError: (error) =>
        showToast({
          message: error instanceof ApiError ? error.message : 'Não foi possível iniciar a análise.',
          tone: 'error',
        }),
    })
  }

  function handleRefresh() {
    setShownAnalyzed(data.analyzed)
    refreshJobs()
  }

  const link = 'text-left underline underline-offset-2 hover:text-ink'

  return (
    <section aria-label="Análise com IA" className="space-y-2 text-xs text-graphite">
      <p>
        <span className="font-mono text-ink">{data.analyzed}</span> com nota ·{' '}
        <span className="font-mono">{data.pending}</span> sem nota
      </p>

      {data.running ? (
        <p aria-live="polite">
          Analisando {data.batch_done} de {data.batch_total}
          {data.waiting_until && ` · aguardando a cota até ${formatTime(data.waiting_until)}`}
        </p>
      ) : (
        data.pending > 0 && (
          <button
            type="button"
            onClick={handleStart}
            disabled={start.isPending}
            className="rounded-md border border-rule px-3 py-1.5 text-sm font-medium text-ink hover:border-graphite disabled:cursor-wait"
          >
            Analisar vagas
          </button>
        )
      )}

      {data.stopped_reason && !data.running && <p>{data.stopped_reason}</p>}

      {newScores > 0 && (
        <button type="button" onClick={handleRefresh} className={link}>
          Mostrar {newScores} {newScores === 1 ? 'nota nova' : 'notas novas'} na lista
        </button>
      )}
    </section>
  )
}
