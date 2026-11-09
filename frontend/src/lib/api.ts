// Thin typed wrapper around fetch for the Lurker API.

import type {
  ApplicationRead,
  ApplicationStatus,
  CollectStatus,
  JobDetail,
  JobPage,
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

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
      return body.detail
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

// --- Collection ------------------------------------------------------------------

export function getCollectStatus(signal?: AbortSignal): Promise<CollectStatus> {
  return apiRequest<CollectStatus>('/collect', { signal })
}

export function startCollection(): Promise<CollectStatus> {
  return apiRequest<CollectStatus>('/collect', { method: 'POST' })
}
