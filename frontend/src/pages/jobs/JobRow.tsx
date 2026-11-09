import { useEffect, useRef } from 'react'

import { ScoreStamp } from '../../components/ScoreStamp'
import { STATUS_LABELS, compactAge, formatDateTime, jobDate, sourceLabel, workModeLabel } from '../../lib/format'
import type { JobSummary } from '../../lib/types'

interface JobRowProps {
  job: JobSummary
  selected: boolean
  /** Tags chosen in the stack filter: shown first and emphasized */
  highlightedTags: string[]
  /** Reserve the score column (when any job in the list has a score) */
  showScore: boolean
  onSelect: (id: string) => void
}

const MAX_ROW_TAGS = 5

/** Highlighted tags first (they explain why the job is in a filtered list), then the rest. */
function rowTags(tags: string[], highlighted: string[]): { shown: string[]; hidden: number } {
  const ordered = [
    ...tags.filter((tag) => highlighted.includes(tag)),
    ...tags.filter((tag) => !highlighted.includes(tag)),
  ]
  return { shown: ordered.slice(0, MAX_ROW_TAGS), hidden: Math.max(ordered.length - MAX_ROW_TAGS, 0) }
}

export function JobRow({ job, selected, highlightedTags, showScore, onSelect }: JobRowProps) {
  const ref = useRef<HTMLButtonElement>(null)

  // Keyboard navigation (J/K) keeps the selected row visible
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: 'nearest' })
  }, [selected])

  const date = jobDate(job)
  const tags = rowTags(job.tags, highlightedTags)

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
        {showScore && <ScoreStamp score={job.score} />}
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{job.title}</span>
          <span className="block truncate text-sm text-graphite">
            {job.company} · {workModeLabel(job)} · {sourceLabel(job.source)}
          </span>
          {tags.shown.length > 0 && (
            <span className="mt-1 block truncate font-mono text-xs text-graphite">
              {tags.shown.map((tag, index) => (
                <span key={tag}>
                  {index > 0 && ' · '}
                  <span className={highlightedTags.includes(tag) ? 'font-semibold text-ink' : undefined}>
                    {tag}
                  </span>
                </span>
              ))}
              {tags.hidden > 0 && ` +${tags.hidden}`}
            </span>
          )}
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
