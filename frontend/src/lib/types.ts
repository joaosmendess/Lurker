// Mirrors backend/app/schemas.py. Keep both in sync when the API changes.

export type ApplicationStatus =
  | 'interested'
  | 'applied'
  | 'in_process'
  | 'interview'
  | 'offer'
  | 'rejected'
  | 'discarded'

export interface JobSummary {
  id: string
  source: string
  title: string
  company: string
  url: string
  location: string | null
  remote: boolean | null
  published_at: string | null
  collected_at: string
  description_preview: string
  application_id: number | null
  application_status: ApplicationStatus | null
}

export interface JobDetail extends JobSummary {
  description: string
}

export interface JobPage {
  items: JobSummary[]
  total: number
  limit: number
  offset: number
}

export interface ApplicationRead {
  id: number
  status: ApplicationStatus
  notes: string
  created_at: string
  updated_at: string
  job: JobSummary
}

export interface CollectRun {
  id: number
  started_at: string
  finished_at: string | null
  fetched: number
  saved: number
  failed_sources: string[]
  error: string | null
}

export interface CollectStatus {
  running: boolean
  cooldown_until: string | null
  last_run: CollectRun | null
}
