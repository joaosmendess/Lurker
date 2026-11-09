import { useDraggable } from '@dnd-kit/core'

import { daysSince, formatDateTime } from '../../lib/format'
import type { ApplicationRead, ApplicationStatus } from '../../lib/types'

/** A card this long in one stage probably needs a follow-up (docs/ui-research.md 5.2). */
const STALE_DAYS = 7

/** Stages where waiting is the end of the story, so time stopped means nothing. */
const FINAL_STATUSES: ApplicationStatus[] = ['offer', 'rejected', 'discarded']

/** What a card shows, shared by the card in its column and the copy being dragged. */
export function CardBody({ card }: { card: ApplicationRead }) {
  const days = daysSince(card.updated_at)
  const stale = days >= STALE_DAYS && !FINAL_STATUSES.includes(card.status)
  const hasNotes = card.notes.trim() !== ''

  return (
    <>
      <p className="line-clamp-3 text-sm leading-snug font-medium">{card.job.title}</p>
      <p className="mt-1 truncate text-xs text-graphite">{card.job.company}</p>
      {(stale || hasNotes) && (
        <p className="mt-2 flex items-center justify-between gap-2 font-mono text-[11px] text-graphite">
          {stale ? (
            <span className="text-fit-mid" title={`Nesta etapa desde ${formatDateTime(card.updated_at)}`}>
              parada há {days} dias
            </span>
          ) : (
            <span />
          )}
          {hasNotes && <span>com nota</span>}
        </p>
      )}
    </>
  )
}

interface BoardCardProps {
  card: ApplicationRead
  onOpen: (id: number) => void
}

/** A card you can drag to another column (mouse, or Space + arrows) or open (click, Enter). */
export function BoardCard({ card, onOpen }: BoardCardProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: card.id,
    attributes: { roleDescription: 'card arrastável' },
  })

  return (
    <li>
      <div
        ref={setNodeRef}
        {...attributes}
        {...listeners}
        // After the spread, so it wins: Enter opens, every other key goes to dnd-kit
        onKeyDown={(event) => {
          if (event.key === 'Enter') onOpen(card.id)
          else listeners?.onKeyDown?.(event)
        }}
        // A plain click (no drag: the pointer sensor needs 6px of movement) opens it
        onClick={() => onOpen(card.id)}
        aria-label={`${card.job.title}, ${card.job.company}`}
        className={`cursor-grab rounded-md border border-rule bg-paper p-3 hover:border-graphite active:cursor-grabbing ${
          isDragging ? 'opacity-40' : ''
        }`}
      >
        <CardBody card={card} />
      </div>
    </li>
  )
}
