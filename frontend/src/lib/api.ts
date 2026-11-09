// Thin typed wrapper around fetch for the Lurker API.

import type {
  ApplicationDetail,
  ApplicationRead,
  ApplicationStatus,
  CollectStatus,
  Company,
  CompanyCreated,
  CompanyInput,
  JobDetail,
  JobPage,
  LLMStatus,
  ScoringStatus,
  TailoredResume,
  Profile,
  ProfileInput,
  TagCount,
} from './types'

const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** An HTTP error from the API, with the status and FastAPI's "detail" message. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface ValidationIssue {
  loc?: (string | number)[]
  msg?: string
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      if (typeof body.detail === 'string') return body.detail
      // 422 from FastAPI: detail is a list like [{ loc: ["body", "resume"], msg: "..." }]
      if (Array.isArray(body.detail)) {
        return (body.detail as ValidationIssue[])
          .map((issue) => `${issue.loc?.at(-1) ?? 'campo'}: ${issue.msg ?? 'inválido'}`)
          .join('; ')
      }
    }
  } catch {
    // Not JSON; fall through to the status text
  }
  return `${response.status} ${response.statusText}`
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }
  // 204 No Content has no body to parse
  return (response.status === 204 ? undefined : await response.json()) as T
}

// --- Jobs ----------------------------------------------------------------------

export interface JobFilters {
  untriaged?: boolean
  prefiltered?: boolean
  q?: string
  source?: string
  remote?: boolean
  /** Jobs with ANY of these stack tags */
  stack?: string[]
}

function toSearchParams(filters: JobFilters): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.untriaged) params.set('untriaged', 'true')
  if (filters.prefiltered) params.set('prefiltered', 'true')
  if (filters.q) params.set('q', filters.q)
  if (filters.source) params.set('source', filters.source)
  if (filters.remote !== undefined) params.set('remote', String(filters.remote))
  // Repeated key: ?stack=React&stack=.NET (URLSearchParams encodes "#" in "C#")
  for (const tag of filters.stack ?? []) params.append('stack', tag)
  return params
}

export function listJobs(
  filters: JobFilters,
  limit: number,
  offset: number,
  signal?: AbortSignal,
): Promise<JobPage> {
  const params = toSearchParams(filters)
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  return apiRequest<JobPage>(`/jobs?${params}`, { signal })
}

export function getTagCounts(filters: JobFilters, signal?: AbortSignal): Promise<TagCount[]> {
  return apiRequest<TagCount[]>(`/jobs/tags?${toSearchParams(filters)}`, { signal })
}

export function getJob(id: string, signal?: AbortSignal): Promise<JobDetail> {
  return apiRequest<JobDetail>(`/jobs/${encodeURIComponent(id)}`, { signal })
}

// --- Tailored resume -------------------------------------------------------------

/** The saved version for this job, or null if it was never generated. */
export async function getTailoredResume(
  jobId: string,
  signal?: AbortSignal,
): Promise<TailoredResume | null> {
  try {
    return await apiRequest<TailoredResume>(`/jobs/${encodeURIComponent(jobId)}/resume`, { signal })
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

/** Asks the AI for a new version. Can take up to a minute on free tiers. */
export function createTailoredResume(jobId: string): Promise<TailoredResume> {
  return apiRequest<TailoredResume>(`/jobs/${encodeURIComponent(jobId)}/resume`, { method: 'POST' })
}

export function getScoringStatus(signal?: AbortSignal): Promise<ScoringStatus> {
  return apiRequest<ScoringStatus>('/scoring', { signal })
}

/** Starts a batch in the background (202); follow it with getScoringStatus. */
export function startScoring(): Promise<ScoringStatus> {
  return apiRequest<ScoringStatus>('/scoring', { method: 'POST' })
}

export function getLLMStatus(signal?: AbortSignal): Promise<LLMStatus> {
  return apiRequest<LLMStatus>('/llm/status', { signal })
}

// --- Applications ----------------------------------------------------------------

export function createApplication(
  jobId: string,
  status: ApplicationStatus,
): Promise<ApplicationRead> {
  return apiRequest<ApplicationRead>('/applications', {
    method: 'POST',
    body: JSON.stringify({ job_id: jobId, status }),
  })
}

export function deleteApplication(id: number): Promise<void> {
  return apiRequest<void>(`/applications/${id}`, { method: 'DELETE' })
}

export function listApplications(
  statuses: readonly ApplicationStatus[],
  signal?: AbortSignal,
): Promise<ApplicationRead[]> {
  const params = new URLSearchParams()
  for (const status of statuses) params.append('status', status)
  return apiRequest<ApplicationRead[]>(`/applications?${params}`, { signal })
}

export function getApplication(id: number, signal?: AbortSignal): Promise<ApplicationDetail> {
  return apiRequest<ApplicationDetail>(`/applications/${id}`, { signal })
}

export function moveApplication(id: number, status: ApplicationStatus): Promise<ApplicationRead> {
  return apiRequest<ApplicationRead>(`/applications/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

export function updateApplicationNotes(id: number, notes: string): Promise<ApplicationRead> {
  return apiRequest<ApplicationRead>(`/applications/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ notes }),
  })
}

// --- Profile ---------------------------------------------------------------------

export function getProfile(signal?: AbortSignal): Promise<Profile> {
  return apiRequest<Profile>('/profile', { signal })
}

export function saveProfile(profile: ProfileInput): Promise<Profile> {
  return apiRequest<Profile>('/profile', { method: 'PUT', body: JSON.stringify(profile) })
}

export function getStackOptions(signal?: AbortSignal): Promise<string[]> {
  return apiRequest<string[]>('/profile/stack-options', { signal })
}

// --- Watched companies -----------------------------------------------------------

export function listCompanies(signal?: AbortSignal): Promise<Company[]> {
  return apiRequest<Company[]>('/companies', { signal })
}

/** Checks the board on the provider's site before saving, so it can take a few seconds. */
export function createCompany(company: CompanyInput): Promise<CompanyCreated> {
  return apiRequest<CompanyCreated>('/companies', { method: 'POST', body: JSON.stringify(company) })
}

export function updateCompany(
  id: number,
  changes: { name?: string; active?: boolean },
): Promise<Company> {
  return apiRequest<Company>(`/companies/${id}`, { method: 'PATCH', body: JSON.stringify(changes) })
}

export function deleteCompany(id: number): Promise<void> {
  return apiRequest<void>(`/companies/${id}`, { method: 'DELETE' })
}

// --- Collection ------------------------------------------------------------------

export function getCollectStatus(signal?: AbortSignal): Promise<CollectStatus> {
  return apiRequest<CollectStatus>('/collect', { signal })
}

export function startCollection(): Promise<CollectStatus> {
  return apiRequest<CollectStatus>('/collect', { method: 'POST' })
}
