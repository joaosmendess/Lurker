import { useState } from 'react'

import { StackChip } from '../../components/StackChip'
import type { TagCount } from '../../lib/types'

/** How many selected stacks the collapsed summary names before "+N". */
const SUMMARY_NAMES = 4

interface StackFilterProps {
  counts: TagCount[] | undefined
  selected: string[]
  /** True when the selection is the profile's preferred stacks (no choice in the URL) */
  fromProfile: boolean
  onChange: (selected: string[]) => void
}

/**
 * Stack filter. Collapsed it's one line saying what's applied; the chips only open
 * on demand, since you change this rarely and the jobs should start near the top.
 * A view filter only: it never discards jobs (CLAUDE.md).
 */
export function StackFilter({ counts, selected, fromProfile, onChange }: StackFilterProps) {
  const [open, setOpen] = useState(false)
  if (!counts || counts.length === 0) return null

  const linkClass = 'shrink-0 text-xs text-graphite underline underline-offset-2 hover:text-ink'

  if (!open) {
    const named = selected.slice(0, SUMMARY_NAMES).join(', ')
    const rest = selected.length - SUMMARY_NAMES
    return (
      <div className="flex items-baseline gap-3 text-xs">
        <p className="min-w-0 flex-1 truncate text-graphite">
          {selected.length === 0 ? (
            'Todas as stacks'
          ) : (
            <>
              {fromProfile ? 'Stacks do seu foco: ' : 'Stacks: '}
              <span className="font-mono text-ink">{named}</span>
              {rest > 0 && <span className="font-mono"> +{rest}</span>}
            </>
          )}
        </p>
        {selected.length > 0 && (
          <button type="button" onClick={() => onChange([])} className={linkClass}>
            Ver todas
          </button>
        )}
        <button type="button" onClick={() => setOpen(true)} aria-expanded={false} className={linkClass}>
          {selected.length > 0 ? 'Alterar' : 'Filtrar por stack'}
        </button>
      </div>
    )
  }

  function toggle(tag: string) {
    onChange(selected.includes(tag) ? selected.filter((item) => item !== tag) : [...selected, tag])
  }

  return (
    <div className="space-y-2">
      <div role="group" aria-label="Filtrar por stack" className="flex flex-wrap gap-1.5">
        {counts.map(({ tag, count }) => (
          <StackChip key={tag} tag={tag} count={count} selected={selected.includes(tag)} onToggle={toggle} />
        ))}
      </div>
      <div className="flex items-baseline gap-3">
        <button type="button" onClick={() => setOpen(false)} aria-expanded className={linkClass}>
          Pronto
        </button>
        {selected.length > 0 && (
          <button type="button" onClick={() => onChange([])} className={linkClass}>
            Desmarcar todas
          </button>
        )}
      </div>
    </div>
  )
}
