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
  tags: string[]
  application_id: number | null
  application_status: ApplicationStatus | null
  /** AI fit score 0-100; null = not analyzed yet */
  score: number | null
}

export interface JobAnalysis {
  score: number
  summary: string
  matches: string[]
  gaps: string[]
  red_flags: string[]
  pitch: string
  /** Numbers/terms in the pitch that the resume doesn't have; empty = all good */
  pitch_warnings: string[]
  model: string
  analyzed_at: string
}

export interface JobDetail extends JobSummary {
  description: string
  analysis: JobAnalysis | null
}

export interface ScoringStatus {
  running: boolean
  analyzed: number
  pending: number
  batch_total: number
  batch_done: number
  batch_failed: number
  waiting_until: string | null
  stopped_reason: string | null
}

export interface JobPage {
  items: JobSummary[]
  total: number
  limit: number
  offset: number
}

export type WorkMode = 'remote' | 'hybrid' | 'onsite'
export type ContractType = 'clt' | 'pj'

/** Body of PUT /profile (backend ProfileData) */
export interface ProfileInput {
  resume: string
  work_modes: WorkMode[]
  accepted_cities: string[]
  seniority_levels: string[]
  contract_types: ContractType[]
  salary_expectation: string
  excluded_title_words: string[]
  preferred_stack: string[]
  strict_unknown_work_mode: boolean
}

export interface Profile extends ProfileInput {
  updated_at: string
}

export interface TagCount {
  tag: string
  count: number
}

export interface ApplicationRead {
  id: number
  status: ApplicationStatus
  notes: string
  created_at: string
  updated_at: string
  job: JobSummary
}

export interface StatusChange {
  /** null for the creation itself (the triage) */
  from_status: ApplicationStatus | null
  to_status: ApplicationStatus
  changed_at: string
}

export interface ApplicationDetail extends ApplicationRead {
  history: StatusChange[]
}

export interface TailoredResume {
  job_id: string
  content: string
  /** What the AI says it adjusted */
  changes: string[]
  /** Job requirements the resume doesn't show (not added to it) */
  missing: string[]
  /** What the automatic check found changed or invented; empty = all good */
  warnings: string[]
  model: string
  created_at: string
}

export interface LLMStatus {
  configured: boolean
  has_key: boolean
  model: string
  base_url: string
}

export type CompanyProvider = 'greenhouse' | 'lever'

export interface Company {
  id: number
  provider: CompanyProvider
  slug: string
  name: string
  active: boolean
  created_at: string
  job_count: number
  /** Untriaged jobs that pass the profile pre-filter */
  to_triage: number
  failed_last_collect: boolean
}

export interface CompanyCreated extends Company {
  found_jobs: number
  saved_jobs: number
}

/** Body of POST /companies. `slug` may be a pasted board link; then provider is optional. */
export interface CompanyInput {
  provider?: CompanyProvider
  slug: string
  name: string
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
