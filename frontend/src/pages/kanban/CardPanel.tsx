import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'

import { useToast } from '../../components/toast-context'
import { formatDateTime, sourceLabel, STATUS_LABELS, workModeLabel } from '../../lib/format'
import {
  BOARD_STATUSES,
  useApplication,
  useMoveApplication,
  useReturnToTriage,
  useUpdateNotes,
} from '../../lib/queries'
import type { ApplicationStatus, StatusChange } from '../../lib/types'

/** Every status the card can go to: the columns, plus discarding it. */
const MOVE_OPTIONS: ApplicationStatus[] = [...BOARD_STATUSES, 'discarded']

interface CardPanelProps {
  id: number
  /** The status shown on the board (already updated while a move is in flight) */
  boardStatus: ApplicationStatus | undefined
  onClose: () => void
}

/** Side panel of one application: stage, notes, history. Full screen on mobile. */
export function CardPanel({ id, boardStatus, onClose }: CardPanelProps) {
  const detail = useApplication(id)
  const move = useMoveApplication()
  const returnToTriage = useReturnToTriage()
  const showToast = useToast()
  const closeRef = useRef<HTMLButtonElement>(null)
  const [confirmingReturn, setConfirmingReturn] = useState(false)

  // Focus goes into the panel when it opens; Escape closes it
  useEffect(() => {
    closeRef.current?.focus()
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  const application = detail.data
  const status = boardStatus ?? application?.status

  function handleMove(next: ApplicationStatus) {
    move.mutate(
      { id, status: next },
      {
        onSuccess: () => {
          if (next === 'discarded') {
            onClose()
            showToast({ message: 'Candidatura descartada. Ela sai do quadro.' })
          }
        },
        onError: (error) => showToast({ message: `Não deu para mover: ${error.message}`, tone: 'error' }),
      },
    )
  }

  function handleReturn() {
    returnToTriage.mutate(id, {
      onSuccess: () => {
        onClose()
        showToast({ message: 'A vaga voltou para “Para triar”.' })
      },
      onError: (error) => showToast({ message: `Não deu para desfazer: ${error.message}`, tone: 'error' }),
    })
  }

  return (
    <div className="fixed inset-0 z-30 flex justify-end">
      {/* Backdrop: a click outside closes, like most side panels */}
      <div aria-hidden="true" onClick={onClose} className="absolute inset-0 bg-ink/25" />

      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="card-panel-title"
        className="relative flex h-full w-full max-w-md flex-col border-l border-rule bg-paper shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-rule px-5 py-3">
          <p className="font-mono text-xs text-graphite">Candidatura</p>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-graphite hover:bg-surface hover:text-ink"
          >
            Fechar
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5">
          {detail.isPending && <p className="text-sm text-graphite">Carregando…</p>}
          {detail.isError && (
            <p role="alert" className="text-sm text-signal">
              Não foi possível carregar: {detail.error.message}
            </p>
          )}

          {application && status && (
            <>
              <header className="space-y-1.5">
                <h2 id="card-panel-title" className="font-display text-xl leading-tight font-bold">
                  {application.job.title}
                </h2>
                <p className="text-sm text-graphite">
                  {application.job.company} · {workModeLabel(application.job)} ·{' '}
                  {sourceLabel(application.job.source)}
                </p>
                <p className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-sm">
                  <a
                    href={application.job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-signal underline-offset-2 hover:underline"
                  >
                    Abrir vaga original
                  </a>
                  <Link
                    to={`/vagas?${new URLSearchParams({ aba: 'todas', vaga: application.job.id })}`}
                    className="text-graphite underline-offset-2 hover:text-ink hover:underline"
                  >
                    Ver descrição no Lurker
                  </Link>
                </p>
              </header>

              <label className="block space-y-1.5">
                <span className="font-display text-sm font-semibold">Etapa</span>
                <select
                  value={status}
                  onChange={(event) => handleMove(event.target.value as ApplicationStatus)}
                  className="w-full rounded-md border border-rule bg-paper px-2 py-1.5 text-sm hover:border-graphite"
                >
                  {MOVE_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {STATUS_LABELS[option]}
                    </option>
                  ))}
                </select>
              </label>

              {/* key: a different application starts a fresh draft */}
              <NotesField key={application.id} id={application.id} initial={application.notes} />

              <History changes={application.history} />
            </>
          )}
        </div>

        <footer className="border-t border-rule px-5 py-3">
          {confirmingReturn ? (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-graphite">Apagar a candidatura e o histórico?</span>
              <button
                type="button"
                onClick={handleReturn}
                disabled={returnToTriage.isPending}
                className="rounded-md bg-signal px-2.5 py-1 font-medium text-on-signal hover:opacity-90 disabled:opacity-40"
              >
                Voltar para a triagem
              </button>
              <button
                type="button"
                onClick={() => setConfirmingReturn(false)}
                className="rounded-md px-2.5 py-1 text-graphite hover:bg-surface hover:text-ink"
              >
                Cancelar
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingReturn(true)}
              className="text-sm text-graphite underline-offset-2 hover:text-ink hover:underline"
            >
              Voltar para a triagem
            </button>
          )}
        </footer>
      </aside>
    </div>
  )
}

/** Notes save when the field loses focus, only if something changed. */
function NotesField({ id, initial }: { id: number; initial: string }) {
  const [draft, setDraft] = useState(initial)
  const [saved, setSaved] = useState(initial)
  const update = useUpdateNotes()

  function save() {
    if (draft === saved) return
    update.mutate({ id, notes: draft }, { onSuccess: (application) => setSaved(application.notes) })
  }

  let state = ''
  if (update.isPending) state = 'Salvando…'
  else if (update.isError) state = 'Não salvou. Clique fora do campo para tentar de novo.'
  else if (draft !== saved) state = 'Salva ao sair do campo'
  else if (update.isSuccess) state = 'Salvo'

  return (
    <label className="block space-y-1.5">
      <span className="font-display text-sm font-semibold">Notas</span>
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={save}
        rows={6}
        placeholder="Recrutador, salário combinado, datas, próximos passos…"
        className="w-full rounded-md border border-rule bg-paper px-3 py-2 text-sm leading-relaxed placeholder:text-graphite hover:border-graphite"
      />
      <span
        aria-live="polite"
        className={`block min-h-4 font-mono text-xs ${update.isError ? 'text-signal' : 'text-graphite'}`}
      >
        {state}
      </span>
    </label>
  )
}

function History({ changes }: { changes: StatusChange[] }) {
  // Newest first: what happened last is what you usually want to know
  const newestFirst = [...changes].reverse()
  return (
    <section className="space-y-2">
      <h3 className="font-display text-sm font-semibold">Histórico</h3>
      <ol className="space-y-1.5 border-l border-rule pl-3">
        {newestFirst.map((change, index) => (
          <li key={`${change.changed_at}-${index}`} className="text-sm">
            <span className="text-ink">
              {change.from_status === null
                ? `Triada como ${STATUS_LABELS[change.to_status]}`
                : `${STATUS_LABELS[change.from_status]} → ${STATUS_LABELS[change.to_status]}`}
            </span>
            <span className="ml-2 font-mono text-xs text-graphite">
              {formatDateTime(change.changed_at)}
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}
