import { useEffect, useRef, useState, type RefObject } from 'react'

export type JobTab = 'triar' | 'todas'
export type WorkModeFilter = '' | 'remoto' | 'presencial'

interface JobToolbarProps {
  tab: JobTab
  query: string
  source: string
  workMode: WorkModeFilter
  total: number | undefined
  searchRef: RefObject<HTMLInputElement | null>
  onChange: (updates: Record<string, string>) => void
}

const TABS: { value: JobTab; label: string }[] = [
  { value: 'triar', label: 'Para triar' },
  { value: 'todas', label: 'Todas' },
]

const SEARCH_DELAY_MS = 300

export function JobToolbar({ tab, query, source, workMode, total, searchRef, onChange }: JobToolbarProps) {
  // The input updates instantly; the URL (and the API call) only after a pause in typing
  const [draft, setDraft] = useState(query)
  const lastSent = useRef(query)

  useEffect(() => {
    if (draft === lastSent.current) return
    const timer = window.setTimeout(() => {
      lastSent.current = draft
      onChange({ q: draft })
    }, SEARCH_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [draft, onChange])

  const selectClass =
    'w-full rounded-md border border-rule bg-paper px-2 py-1.5 text-sm text-ink hover:border-graphite'

  return (
    <div className="space-y-3 border-b border-rule px-4 pt-4 pb-3">
      <div className="flex items-baseline justify-between gap-3">
        <div role="tablist" aria-label="Lista" className="flex gap-4">
          {TABS.map((item) => (
            <button
              key={item.value}
              type="button"
              role="tab"
              aria-selected={tab === item.value}
              onClick={() => onChange({ aba: item.value, vaga: '' })}
              className={`border-b-2 pb-1 font-display text-base font-semibold ${
                tab === item.value
                  ? 'border-signal text-ink'
                  : 'border-transparent text-graphite hover:text-ink'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        {total !== undefined && (
          <span className="font-mono text-xs text-graphite">
            {total} {total === 1 ? 'vaga' : 'vagas'}
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <label className="basis-full">
          <span className="sr-only">Buscar por título ou empresa</span>
          <input
            ref={searchRef}
            type="search"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Buscar título ou empresa  /"
            className="w-full rounded-md border border-rule bg-paper px-2.5 py-1.5 text-sm placeholder:text-graphite hover:border-graphite"
          />
        </label>
        <label className="min-w-0 flex-1">
          <span className="sr-only">Fonte</span>
          <select value={source} onChange={(event) => onChange({ fonte: event.target.value })} className={selectClass}>
            <option value="">Todas as fontes</option>
            <option value="gupy">Gupy</option>
            <option value="remotive">Remotive</option>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
          </select>
        </label>
        <label className="min-w-0 flex-1">
          <span className="sr-only">Modalidade</span>
          <select
            value={workMode}
            onChange={(event) => onChange({ modo: event.target.value })}
            className={selectClass}
          >
            <option value="">Qualquer modalidade</option>
            <option value="remoto">Remoto</option>
            <option value="presencial">Presencial/híbrido</option>
          </select>
        </label>
      </div>
    </div>
  )
}
