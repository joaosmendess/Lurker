// Display helpers: every user-facing label for API values lives here.

import type { ApplicationStatus, JobSummary } from './types'

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  interested: 'Interesse',
  applied: 'Aplicada',
  in_process: 'Em processo',
  interview: 'Entrevista',
  offer: 'Oferta',
  rejected: 'Recusada',
  discarded: 'Descartada',
}

const SOURCE_LABELS: Record<string, string> = {
  gupy: 'Gupy',
  remotive: 'Remotive',
  greenhouse: 'Greenhouse',
  lever: 'Lever',
  github: 'GitHub',
}

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source
}

/** "Remoto", "Maceió - Alagoas · presencial/híbrido", or the raw location if unknown. */
export function workModeLabel(job: Pick<JobSummary, 'remote' | 'location'>): string {
  if (job.remote === true) return job.location ? `Remoto · ${job.location}` : 'Remoto'
  if (job.remote === false) {
    return job.location ? `${job.location} · presencial/híbrido` : 'Presencial/híbrido'
  }
  return job.location ?? 'Modalidade não informada'
}

const DAY_MS = 24 * 60 * 60 * 1000

/** Compact age for lists: "hoje", "3d", "2m". */
export function compactAge(isoDate: string, now: Date = new Date()): string {
  const days = Math.floor((now.getTime() - new Date(isoDate).getTime()) / DAY_MS)
  if (days <= 0) return 'hoje'
  if (days < 60) return `${days}d`
  return `${Math.floor(days / 30)}m`
}

const relativeFormat = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' })

/** Readable age for details: "hoje", "ontem", "há 5 dias". */
export function relativeAge(isoDate: string, now: Date = new Date()): string {
  const days = Math.floor((now.getTime() - new Date(isoDate).getTime()) / DAY_MS)
  return relativeFormat.format(-days, 'day')
}

const dateTimeFormat = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
const timeFormat = new Intl.DateTimeFormat('pt-BR', { timeStyle: 'short' })

export function formatDateTime(isoDate: string): string {
  return dateTimeFormat.format(new Date(isoDate))
}

export function formatTime(isoDate: string): string {
  return timeFormat.format(new Date(isoDate))
}

/** The date a job is sorted and aged by: publication, or collection when unknown. */
export function jobDate(job: Pick<JobSummary, 'published_at' | 'collected_at'>): string {
  return job.published_at ?? job.collected_at
}
