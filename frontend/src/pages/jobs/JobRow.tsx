import { useEffect, useRef } from 'react'

import { STATUS_LABELS, compactAge, formatDateTime, jobDate, sourceLabel, workModeLabel } from '../../lib/format'
import type { JobSummary } from '../../lib/types'

interface JobRowProps {
  job: JobSummary
  selected: boolean
  onSelect: (id: string) => void
}

export function JobRow({ job, selected, onSelect }: JobRowProps) {
  const ref = useRef<HTMLButtonElement>(null)

  // Keyboard navigation (J/K) keeps the selected row visible
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: 'nearest' })
  }, [selected])

  const date = jobDate(job)

  return (
    <li>
      <button
        ref={ref}
        type="button"
        onClick={() => onSelect(job.id)}
        aria-current={selected ? 'true' : undefined}
        className={`flex w-full items-baseline gap-3 border-l-2 px-4 py-2.5 text-left ${
          selected ? 'border-signal bg-surface' : 'border-transparent hover:bg-surface'
        }`}
      >
        {/* The score "stamp" column (docs/ui-research.md) comes back with the AI scoring.
            A placeholder dash here read like a list bullet, so it's left out until then. */}
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{job.title}</span>
          <span className="block truncate text-sm text-graphite">
            {job.company} · {workModeLabel(job)} · {sourceLabel(job.source)}
          </span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-1">
          <time dateTime={date} title={formatDateTime(date)} className="font-mono text-xs text-graphite">
            {compactAge(date)}
          </time>
          {job.application_status && (
            <span className="rounded border border-rule px-1.5 text-xs text-graphite">
              {STATUS_LABELS[job.application_status]}
            </span>
          )}
        </span>
      </button>
    </li>
  )
}
