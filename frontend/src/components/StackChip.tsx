interface StackChipProps {
  tag: string
  /** Jobs with this tag, when the chip filters a list */
  count?: number
  selected: boolean
  onToggle: (tag: string) => void
}

/**
 * A toggleable stack tag. Selected = inverted (ink background), like a stamped
 * entry: it reads as "on" in both themes without spending the signal color,
 * which stays reserved for the main action, focus and new items.
 */
export function StackChip({ tag, count, selected, onToggle }: StackChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={() => onToggle(tag)}
      className={`rounded border px-1.5 py-0.5 font-mono text-xs ${
        selected
          ? 'border-ink bg-ink text-paper'
          : 'border-rule text-graphite hover:border-graphite hover:text-ink'
      }`}
    >
      {tag}
      {count !== undefined && <span className="ml-1 opacity-70">{count}</span>}
    </button>
  )
}
