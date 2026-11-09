import { ApiError } from '../lib/api'
import { formatDateTime, formatTime } from '../lib/format'
import { useCollectStatus, useStartCollection } from '../lib/queries'
import { useToast } from '../components/toast-context'

/** Last collection summary + "Coletar agora". `compact` is the mobile top-bar version. */
export function CollectPanel({ compact = false }: { compact?: boolean }) {
  const status = useCollectStatus()
  const start = useStartCollection()
  const showToast = useToast()

  const running = status.data?.running ?? false
  const cooldownUntil = status.data?.cooldown_until ?? null
  const lastRun = status.data?.last_run ?? null
  const disabled = running || cooldownUntil !== null || start.isPending

  function handleClick() {
    start.mutate(undefined, {
      onError: (error) => {
        const message = error instanceof ApiError ? error.message : 'Não foi possível iniciar a coleta.'
        showToast({ message, tone: 'error' })
      },
    })
  }

  const buttonLabel = running ? 'Coletando…' : 'Coletar agora'
  const button = (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      // The compact (mobile) version has no room for the explanation below the button
      title={cooldownUntil && !running ? `Disponível às ${formatTime(cooldownUntil)}` : undefined}
      className="rounded-md border border-rule px-3 py-1.5 text-sm font-medium hover:border-graphite disabled:cursor-not-allowed disabled:text-graphite disabled:hover:border-rule"
    >
      {buttonLabel}
    </button>
  )

  if (compact) return button

  return (
    <section aria-label="Coleta" className="space-y-2 text-xs text-graphite">
      <p>
        {lastRun
          ? `Última coleta: ${formatDateTime(lastRun.started_at)}${lastRun.finished_at ? ` · ${lastRun.saved} novas` : ''}`
          : 'Nenhuma coleta registrada.'}
      </p>
      {lastRun?.failed_sources.length ? (
        <p>Falharam: {lastRun.failed_sources.join(', ')}</p>
      ) : null}
      {button}
      {cooldownUntil && !running && (
        <p>Disponível às {formatTime(cooldownUntil)}, para respeitar o limite da Remotive.</p>
      )}
    </section>
  )
}
