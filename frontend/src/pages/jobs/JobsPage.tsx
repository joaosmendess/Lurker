import { useCallback, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router'

import { useToast } from '../../components/toast-context'
import type { JobFilters } from '../../lib/api'
import { useHotkeys } from '../../lib/useHotkeys'
import { useJobList, useProfile, useTagCounts, useTriage, useUndoTriage } from '../../lib/queries'
import type { ApplicationStatus, JobSummary } from '../../lib/types'
import { CollectPanel } from '../../layout/CollectPanel'
import { JobDetailPane } from './JobDetailPane'
import { JobRow } from './JobRow'
import { JobToolbar, type JobTab, type WorkModeFilter } from './JobToolbar'
import { StackFilter } from './StackFilter'
import { Kbd } from '../../components/Kbd'

function toFilters(
  tab: JobTab,
  query: string,
  source: string,
  workMode: WorkModeFilter,
  stack: string[],
): JobFilters {
  return {
    // "Para triar" = passes my profile's pre-filter and has no application yet
    ...(tab === 'triar' ? { untriaged: true, prefiltered: true } : {}),
    ...(query ? { q: query } : {}),
    ...(source ? { source } : {}),
    ...(workMode ? { remote: workMode === 'remoto' } : {}),
    ...(stack.length ? { stack } : {}),
  }
}

// Stacks live in the URL as one comma-separated param: ?stack=.NET,React.
// No param = use the profile's preferred stacks; ?stack=todas = explicitly none
// (otherwise clearing the chips would bring the preferred ones right back).
const STACK_SEPARATOR = ','
const ALL_STACKS = 'todas'
const NO_TAGS: string[] = [] // stable reference, so memoized values don't change for nothing

function parseStack(param: string | null, preferred: string[]): string[] {
  if (param === null) return preferred
  if (param === ALL_STACKS) return NO_TAGS
  return param.split(STACK_SEPARATOR).filter(Boolean)
}

const TRIAGE_MESSAGES: Record<'interested' | 'discarded', string> = {
  interested: 'Marcada como interesse',
  discarded: 'Vaga descartada',
}

export function JobsPage() {
  // All list state lives in the URL: reload, back button and links keep it
  const [params, setParams] = useSearchParams()
  const tab: JobTab = params.get('aba') === 'todas' ? 'todas' : 'triar'
  const query = params.get('q') ?? ''
  const source = params.get('fonte') ?? ''
  const workMode = (params.get('modo') ?? '') as WorkModeFilter
  const stackParam = params.get('stack')
  const selectedId = params.get('vaga')

  const profile = useProfile()
  const preferredStack = profile.data?.preferred_stack ?? NO_TAGS
  const stack = useMemo(() => parseStack(stackParam, preferredStack), [stackParam, preferredStack])
  const filters = useMemo(
    () => toFilters(tab, query, source, workMode, stack),
    [tab, query, source, workMode, stack],
  )
  const list = useJobList(filters)
  const tagCounts = useTagCounts(filters)
  const jobs = useMemo(() => list.data?.pages.flatMap((page) => page.items) ?? [], [list.data])
  const total = list.data?.pages.at(-1)?.total

  const triage = useTriage()
  const undo = useUndoTriage()
  const showToast = useToast()
  const searchRef = useRef<HTMLInputElement>(null)

  const updateParams = useCallback(
    (updates: Record<string, string>, options: { replace?: boolean } = {}) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          for (const [key, value] of Object.entries(updates)) {
            if (value) next.set(key, value)
            else next.delete(key)
          }
          return next
        },
        { replace: options.replace ?? true },
      )
    },
    [setParams],
  )

  // A click pushes a history entry (so "back" on mobile returns to the list);
  // J/K replace it, so walking through 30 jobs doesn't create 30 entries.
  const select = (id: string | null, push = false) => updateParams({ vaga: id ?? '' }, { replace: !push })

  const selectedIndex = jobs.findIndex((job) => job.id === selectedId)
  const selectedJob = selectedIndex >= 0 ? jobs[selectedIndex] : undefined

  function move(step: 1 | -1) {
    if (jobs.length === 0) return
    const nextIndex =
      selectedIndex < 0 ? 0 : Math.min(Math.max(selectedIndex + step, 0), jobs.length - 1)
    select(jobs[nextIndex].id)
    if (nextIndex >= jobs.length - 5 && list.hasNextPage && !list.isFetchingNextPage) {
      void list.fetchNextPage()
    }
  }

  function handleTriage(job: JobSummary, status: ApplicationStatus) {
    if (job.application_status !== null) return
    // In "Para triar" the job leaves the list, so move on to the next one
    if (tab === 'triar') {
      const index = jobs.findIndex((item) => item.id === job.id)
      const next = jobs[index + 1] ?? jobs[index - 1]
      select(next ? next.id : null)
    }
    triage.mutate(
      { jobId: job.id, status },
      {
        onSuccess: (application) => {
          showToast({
            message: TRIAGE_MESSAGES[status as 'interested' | 'discarded'],
            action: {
              label: 'Desfazer',
              onClick: () => {
                undo.mutate({ applicationId: application.id, jobId: job.id })
                select(job.id)
              },
            },
          })
        },
        onError: (error) => showToast({ message: `Não deu para salvar: ${error.message}`, tone: 'error' }),
      },
    )
  }

  function handleUndo(job: JobSummary) {
    if (job.application_id === null) return
    undo.mutate(
      { applicationId: job.application_id, jobId: job.id },
      { onSuccess: () => showToast({ message: 'Triagem desfeita' }) },
    )
  }

  useHotkeys({
    j: () => move(1),
    k: () => move(-1),
    i: () => selectedJob && handleTriage(selectedJob, 'interested'),
    x: () => selectedJob && handleTriage(selectedJob, 'discarded'),
    o: () => selectedJob && window.open(selectedJob.url, '_blank', 'noopener,noreferrer'),
    '/': () => searchRef.current?.focus(),
    escape: () => select(null),
  })

  const hasFilters = Boolean(query || source || workMode || stack.length)

  return (
    <div className="flex h-full">
      {/* List: full width on mobile (hidden while a job is open), fixed column on desktop */}
      <section
        aria-label="Vagas"
        className={`${selectedId ? 'hidden lg:flex' : 'flex'} min-w-0 flex-1 flex-col lg:max-w-xl lg:flex-none lg:basis-[30rem] lg:border-r lg:border-rule`}
      >
        <JobToolbar
          tab={tab}
          query={query}
          source={source}
          workMode={workMode}
          total={total}
          searchRef={searchRef}
          onChange={updateParams}
          extra={
            <StackFilter
              counts={tagCounts.data}
              selected={stack}
              onChange={(next) =>
                updateParams({
                  stack: next.length ? next.join(STACK_SEPARATOR) : preferredStack.length ? ALL_STACKS : '',
                  vaga: '',
                })
              }
            />
          }
        />

        <div className="min-h-0 flex-1 overflow-y-auto">
          {list.isPending && <p className="p-4 text-sm text-graphite">Carregando vagas…</p>}

          {list.isError && (
            <div className="space-y-1 p-4 text-sm" role="alert">
              <p className="font-medium text-signal">Não foi possível carregar as vagas.</p>
              <p className="text-graphite">{list.error.message}</p>
            </div>
          )}

          {list.isSuccess && jobs.length === 0 && (
            <div className="space-y-3 p-6">
              {hasFilters ? (
                <>
                  <p className="font-medium">Nenhuma vaga com esses filtros.</p>
                  <button
                    type="button"
                    onClick={() =>
                      updateParams({
                        q: '',
                        fonte: '',
                        modo: '',
                        stack: preferredStack.length ? ALL_STACKS : '',
                      })
                    }
                    className="text-sm text-signal underline-offset-2 hover:underline"
                  >
                    Limpar filtros
                  </button>
                </>
              ) : tab === 'triar' ? (
                <>
                  <p className="font-medium">Nada para triar.</p>
                  <p className="text-sm text-graphite">
                    Todas as vagas que passam no seu filtro já foram triadas. A coleta automática roda
                    nos dias úteis às 07:00, ou você pode buscar agora.
                  </p>
                  <CollectPanel compact />
                </>
              ) : (
                <p className="text-sm text-graphite">Nenhuma vaga coletada ainda.</p>
              )}
            </div>
          )}

          {jobs.length > 0 && (
            <ul className="divide-y divide-rule">
              {jobs.map((job) => (
                <JobRow
                  key={job.id}
                  job={job}
                  selected={job.id === selectedId}
                  highlightedTags={stack}
                  onSelect={(id) => select(id, true)}
                />
              ))}
            </ul>
          )}

          {list.hasNextPage && (
            <div className="p-4">
              <button
                type="button"
                onClick={() => void list.fetchNextPage()}
                disabled={list.isFetchingNextPage}
                className="w-full rounded-md border border-rule py-2 text-sm text-graphite hover:border-graphite hover:text-ink disabled:cursor-wait"
              >
                {list.isFetchingNextPage ? 'Carregando…' : 'Carregar mais'}
              </button>
            </div>
          )}
        </div>
      </section>

      {/* Detail: full screen on mobile when a job is open, side panel on desktop */}
      <section
        aria-label="Detalhe da vaga"
        className={`${selectedId ? 'flex' : 'hidden lg:flex'} min-w-0 flex-1 flex-col overflow-y-auto`}
      >
        {selectedId ? (
          <JobDetailPane
            key={selectedId}
            jobId={selectedId}
            summary={selectedJob}
            onTriage={handleTriage}
            onUndo={handleUndo}
            onBack={() => select(null)}
          />
        ) : (
          <div className="m-auto max-w-xs space-y-2 p-6 text-center text-sm text-graphite">
            <p className="font-medium text-ink">Selecione uma vaga</p>
            <p>
              Navegue com <Kbd>J</Kbd> e <Kbd>K</Kbd>, marque interesse com <Kbd>I</Kbd> e descarte
              com <Kbd>X</Kbd>.
            </p>
          </div>
        )}
      </section>
    </div>
  )
}
