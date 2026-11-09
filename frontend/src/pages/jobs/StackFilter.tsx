import { useState } from 'react'

import type { TagCount } from '../../lib/types'

const COLLAPSED_COUNT = 12

interface StackFilterProps {
  counts: TagCount[] | undefined
  selected: string[]
  onChange: (selected: string[]) => void
}

/** Toggleable stack chips. A view filter only: it never discards jobs (CLAUDE.md). */
export function StackFilter({ counts, selected, onChange }: StackFilterProps) {
  const [expanded, setExpanded] = useState(false)
  if (!counts || counts.length === 0) return null

  // Selected chips always stay visible, even if they're outside the top N
  const top = expanded ? counts : counts.slice(0, COLLAPSED_COUNT)
  const visible = [
    ...top,
    ...counts.filter((item) => selected.includes(item.tag) && !top.includes(item)),
  ]
  const hiddenCount = counts.length - visible.length

  function toggle(tag: string) {
    onChange(selected.includes(tag) ? selected.filter((item) => item !== tag) : [...selected, tag])
  }

  return (
    <div role="group" aria-label="Filtrar por stack" className="flex flex-wrap items-center gap-1.5">
      {visible.map(({ tag, count }) => {
        const active = selected.includes(tag)
        return (
          <button
            key={tag}
            type="button"
            aria-pressed={active}
            onClick={() => toggle(tag)}
            className={`rounded border px-1.5 py-0.5 font-mono text-xs ${
              active
                ? 'border-signal bg-surface text-ink'
                : 'border-rule text-graphite hover:border-graphite hover:text-ink'
            }`}
          >
            {tag} <span className="opacity-70">{count}</span>
          </button>
        )
      })}
      {(hiddenCount > 0 || expanded) && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="px-1 text-xs text-graphite underline-offset-2 hover:text-ink hover:underline"
        >
          {expanded ? 'Menos' : `+${hiddenCount}`}
        </button>
      )}
      {selected.length > 0 && (
        <button
          type="button"
          onClick={() => onChange([])}
          className="px-1 text-xs text-signal underline-offset-2 hover:underline"
        >
          Limpar stacks
        </button>
      )}
    </div>
  )
}
