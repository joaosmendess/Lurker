import { Description } from '../../components/Description'
import { Kbd } from '../../components/Kbd'
import { STATUS_LABELS, formatDateTime, jobDate, relativeAge, sourceLabel, workModeLabel } from '../../lib/format'
import { useJob } from '../../lib/queries'
import type { ApplicationStatus, JobSummary } from '../../lib/types'

interface JobDetailPaneProps {
  /** The row from the list: shown instantly while the full description loads */
  summary: JobSummary | undefined
  jobId: string
  onTriage: (job: JobSummary, status: ApplicationStatus) => void
  onUndo: (job: JobSummary) => void
  onBack: () => void
}

export function JobDetailPane({ summary, jobId, onTriage, onUndo, onBack }: JobDetailPaneProps) {
  const detail = useJob(jobId)
  const job = detail.data ?? summary

  // Always available on mobile, even while loading or on error, so there's a way out
  const backButton = (
    <button type="button" onClick={onBack} className="text-sm text-graphite hover:text-ink lg:hidden">
      ← Voltar para a lista
    </button>
  )

  if (!job) {
    return (
      <div className="space-y-4 px-5 py-5 lg:p-6">
        {backButton}
        <p className="text-sm text-graphite">
          {detail.isError ? 'Vaga não encontrada.' : 'Carregando vaga…'}
        </p>
      </div>
    )
  }

  const date = jobDate(job)
  const triaged = job.application_status !== null

  return (
    // 64ch of Atkinson ≈ 70-75 letters per line: the comfortable range for long reading
    <article className="mx-auto max-w-[64ch] space-y-6 px-5 py-5 lg:px-8 lg:py-7">
      {backButton}

      <header className="space-y-2">
        <h1 className="font-display text-2xl leading-tight font-bold tracking-tight text-balance">
          {job.title}
        </h1>
        <p className="text-base">{job.company}</p>
        <p className="text-sm text-graphite">
          {workModeLabel(job)} · {sourceLabel(job.source)} ·{' '}
          <time dateTime={date} title={formatDateTime(date)}>
            {job.published_at ? `publicada ${relativeAge(date)}` : `coletada ${relativeAge(date)}`}
          </time>
        </p>
        {job.tags.length > 0 && (
          <ul aria-label="Stack" className="flex flex-wrap gap-1.5 pt-1">
            {job.tags.map((tag) => (
              <li key={tag} className="rounded border border-rule px-1.5 py-0.5 font-mono text-xs text-graphite">
                {tag}
              </li>
            ))}
          </ul>
        )}
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {triaged ? (
          <>
            <p className="text-sm">
              Triada como <strong>{STATUS_LABELS[job.application_status as ApplicationStatus]}</strong>.
            </p>
            <button
              type="button"
              onClick={() => onUndo(job)}
              className="rounded-md border border-rule px-3 py-1.5 text-sm hover:border-graphite"
            >
              Desfazer triagem
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => onTriage(job, 'interested')}
              className="inline-flex items-center gap-2 rounded-md bg-signal px-3 py-1.5 text-sm font-medium text-on-signal hover:opacity-90"
            >
              Tenho interesse <Kbd>I</Kbd>
            </button>
            <button
              type="button"
              onClick={() => onTriage(job, 'discarded')}
              className="inline-flex items-center gap-2 rounded-md border border-rule px-3 py-1.5 text-sm hover:border-graphite"
            >
              Descartar <Kbd>X</Kbd>
            </button>
          </>
        )}
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-graphite underline-offset-2 hover:text-ink hover:underline"
        >
          Abrir vaga ↗ <Kbd>O</Kbd>
        </a>
      </div>

      <section aria-labelledby="analysis-heading" className="space-y-1 border-y border-rule py-4">
        <h2 id="analysis-heading" className="font-display text-sm font-semibold">
          Análise
        </h2>
        <p className="text-sm text-graphite">
          Ainda sem análise. A nota e o pitch aparecem aqui quando a pontuação com a IA for ativada.
        </p>
      </section>

      <section aria-labelledby="description-heading" className="space-y-2">
        <h2 id="description-heading" className="font-display text-sm font-semibold">
          Descrição
        </h2>
        {detail.data ? (
          <Description text={detail.data.description} />
        ) : (
          <p className="text-sm text-graphite">Carregando descrição…</p>
        )}
      </section>
    </article>
  )
}
