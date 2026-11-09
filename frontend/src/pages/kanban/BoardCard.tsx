import { useDraggable } from '@dnd-kit/core'

import { compactAge, formatDateTime } from '../../lib/format'
import type { ApplicationRead } from '../../lib/types'

/** What a card shows, shared by the card in its column and the copy being dragged. */
export function CardBody({ card }: { card: ApplicationRead }) {
  return (
    <>
      <p className="line-clamp-3 text-sm leading-snug font-medium">{card.job.title}</p>
      <p className="mt-1 truncate text-xs text-graphite">{card.job.company}</p>
      <p className="mt-2 flex items-center justify-between gap-2 font-mono text-[11px] text-graphite">
        <span title={`Nesta etapa desde ${formatDateTime(card.updated_at)}`}>
          {compactAge(card.updated_at)}
        </span>
        {card.notes.trim() !== '' && <span>com nota</span>}
      </p>
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
