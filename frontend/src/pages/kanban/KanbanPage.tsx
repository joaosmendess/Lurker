import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type KeyboardCoordinateGetter,
} from '@dnd-kit/core'
import { useCallback, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'

import { useToast } from '../../components/toast-context'
import { STATUS_LABELS } from '../../lib/format'
import { BOARD_STATUSES, useBoard, useMoveApplication } from '../../lib/queries'
import type { ApplicationRead, ApplicationStatus } from '../../lib/types'
import { BoardCard, CardBody } from './BoardCard'
import { CardPanel } from './CardPanel'

type BoardStatus = (typeof BOARD_STATUSES)[number]

const EMPTY_TEXT: Partial<Record<BoardStatus, string>> = {
  interested: 'Marque vagas com interesse na lista (tecla I) e elas aparecem aqui.',
}

/** Column headers carry meaning only where the stage does: an offer, a rejection. */
const HEADER_TONE: Partial<Record<BoardStatus, string>> = {
  offer: 'text-fit-high',
  rejected: 'text-graphite',
}

/**
 * Keyboard dragging: ← and → jump straight to the neighbouring column.
 * (dnd-kit's default moves 25px per key press, ten presses per column.)
 * It returns the new top-left corner of the dragged card, or undefined to stay put.
 */
const columnKeyboardCoordinates: KeyboardCoordinateGetter = (event, { context }) => {
  const step = event.code === 'ArrowRight' ? 1 : event.code === 'ArrowLeft' ? -1 : 0
  const card = context.collisionRect
  if (step === 0 || !card) return undefined
  event.preventDefault() // don't scroll the page

  const columns = [...context.droppableRects.values()]
    .filter((rect) => rect.width > 0) // hidden columns (mobile) measure 0
    .sort((a, b) => a.left - b.left)
  const center = card.left + card.width / 2
  const current = columns.findIndex((rect) => center >= rect.left && center <= rect.right)
  const target = columns[current + step]
  return target ? { x: target.left + 12, y: card.top } : undefined
}

function statusLabel(id: unknown): string {
  return STATUS_LABELS[id as ApplicationStatus] ?? String(id)
}

export function KanbanPage() {
  const board = useBoard()
  const move = useMoveApplication()
  const showToast = useToast()
  const [params, setParams] = useSearchParams()
  const [draggingId, setDraggingId] = useState<number | null>(null)

  // Mobile shows one column at a time (tabs); desktop shows them all
  const mobileColumn = (params.get('coluna') ?? 'interested') as BoardStatus
  const openId = params.get('card') ? Number(params.get('card')) : null

  const cards = useMemo(() => board.data ?? [], [board.data])
  // Object.groupBy: like LINQ's GroupBy, returns { interested: [...], applied: [...] }
  const byStatus = useMemo(() => Object.groupBy(cards, (card) => card.status), [cards])
  const findCard = useCallback((id: unknown) => cards.find((card) => card.id === id), [cards])

  const sensors = useSensors(
    // 6px of movement before a drag starts, so a click still opens the card
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, {
      keyboardCodes: { start: ['Space'], cancel: ['Escape'], end: ['Space', 'Enter'] },
      coordinateGetter: columnKeyboardCoordinates,
    }),
  )

  const setParam = useCallback(
    (key: string, value: string | null, replace = false) =>
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          if (value === null) next.delete(key)
          else next.set(key, value)
          return next
        },
        { replace },
      ),
    [setParams],
  )
  // Stable function: CardPanel's Escape listener isn't re-attached on every render
  const closePanel = useCallback(() => setParam('card', null), [setParam])

  function moveCard(card: ApplicationRead, to: ApplicationStatus) {
    const from = card.status
    move.mutate(
      { id: card.id, status: to },
      {
        onSuccess: () =>
          showToast({
            message: `Movida para ${STATUS_LABELS[to]}`,
            action: { label: 'Desfazer', onClick: () => move.mutate({ id: card.id, status: from }) },
          }),
        onError: (error) =>
          showToast({ message: `Não deu para mover: ${error.message}. O card voltou.`, tone: 'error' }),
      },
    )
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    setDraggingId(null)
    const card = findCard(active.id)
    if (!card || !over || over.id === card.status) return
    moveCard(card, over.id as ApplicationStatus)
  }

  // What a screen reader hears during a drag (dnd-kit's defaults are in English)
  const announcements: Announcements = {
    onDragStart: ({ active }) =>
      `${findCard(active.id)?.job.title ?? 'Card'} pego. Use as setas para trocar de coluna e Espaço para soltar.`,
    onDragOver: ({ over }) => (over ? `Sobre a coluna ${statusLabel(over.id)}.` : 'Fora das colunas.'),
    onDragEnd: ({ over }) =>
      over ? `Solto em ${statusLabel(over.id)}.` : 'Solto fora das colunas. Nada mudou.',
    onDragCancel: () => 'Movimento cancelado. Nada mudou.',
  }

  const dragging = draggingId === null ? undefined : findCard(draggingId)
  const inProgress = cards.filter((card) => card.status !== 'rejected').length

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-rule px-5 py-4 lg:px-6">
        <h1 className="font-display text-xl font-bold tracking-tight">Candidaturas</h1>
        {board.isSuccess && (
          <p className="font-mono text-xs text-graphite">
            {inProgress} em andamento · arraste os cards ou abra um para mudar a etapa
          </p>
        )}
      </header>

      {/* Mobile: one column at a time */}
      <div role="tablist" aria-label="Etapas" className="flex gap-5 overflow-x-auto border-b border-rule px-5 lg:hidden">
        {BOARD_STATUSES.map((status) => (
          <button
            key={status}
            type="button"
            role="tab"
            aria-selected={mobileColumn === status}
            onClick={() => setParam('coluna', status, true)}
            className={`shrink-0 border-b-2 py-2.5 text-sm ${
              mobileColumn === status ? 'border-signal font-semibold text-ink' : 'border-transparent text-graphite'
            }`}
          >
            {STATUS_LABELS[status]}{' '}
            <span className="font-mono text-xs text-graphite">{byStatus[status]?.length ?? 0}</span>
          </button>
        ))}
      </div>

      {board.isPending && <p className="p-6 text-sm text-graphite">Carregando candidaturas…</p>}
      {board.isError && (
        <p role="alert" className="p-6 text-sm text-signal">
          Não foi possível carregar o quadro: {board.error.message}
        </p>
      )}

      {board.isSuccess && (
        <DndContext
          sensors={sensors}
          accessibility={{
            announcements,
            screenReaderInstructions: {
              draggable:
                'Enter abre o card. Para mover, aperte Espaço, troque de coluna com as setas e aperte Espaço de novo. Escape cancela.',
            },
          }}
          onDragStart={({ active }) => setDraggingId(Number(active.id))}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setDraggingId(null)}
        >
          <div className="min-h-0 flex-1 overflow-x-auto">
            <div className="flex h-full">
              {BOARD_STATUSES.map((status) => (
                <Column
                  key={status}
                  status={status}
                  cards={byStatus[status] ?? []}
                  hiddenOnMobile={status !== mobileColumn}
                  onOpen={(id) => setParam('card', String(id))}
                />
              ))}
            </div>
          </div>

          {/* The floating copy under the pointer: rendered outside the columns,
              so their scroll areas never clip it */}
          <DragOverlay dropAnimation={null}>
            {dragging && (
              <div className="w-56 cursor-grabbing rounded-md border border-graphite bg-paper p-3 shadow-lg">
                <CardBody card={dragging} />
              </div>
            )}
          </DragOverlay>
        </DndContext>
      )}

      {openId !== null && (
        <CardPanel id={openId} boardStatus={findCard(openId)?.status} onClose={closePanel} />
      )}
    </div>
  )
}

interface ColumnProps {
  status: BoardStatus
  cards: ApplicationRead[]
  hiddenOnMobile: boolean
  onOpen: (id: number) => void
}

function Column({ status, cards, hiddenOnMobile, onOpen }: ColumnProps) {
  // The whole column is the drop target, not just its cards
  const { setNodeRef, isOver } = useDroppable({ id: status })

  return (
    <section
      ref={setNodeRef}
      aria-label={STATUS_LABELS[status]}
      className={`${hiddenOnMobile ? 'hidden lg:flex' : 'flex'} min-h-0 w-full flex-col border-rule lg:w-auto lg:min-w-48 lg:flex-1 lg:basis-0 lg:border-r lg:last:border-r-0 ${
        isOver ? 'bg-surface' : ''
      }`}
    >
      <h2 className="hidden items-baseline justify-between px-3 pt-4 pb-2 lg:flex">
        <span className={`font-display text-sm font-semibold ${HEADER_TONE[status] ?? 'text-ink'}`}>
          {STATUS_LABELS[status]}
        </span>
        <span className="font-mono text-xs text-graphite">{cards.length}</span>
      </h2>
      <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 pt-3 pb-4 lg:pt-0">
        {cards.map((card) => (
          <BoardCard key={card.id} card={card} onOpen={onOpen} />
        ))}
        {cards.length === 0 && (
          <li className="rounded-md border border-dashed border-rule px-3 py-6 text-center text-xs text-graphite">
            {EMPTY_TEXT[status] ?? 'Nada aqui ainda.'}
          </li>
        )}
      </ul>
    </section>
  )
}
