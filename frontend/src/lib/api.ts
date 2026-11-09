// Thin typed wrapper around fetch for the Lurker API.

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

export interface HealthResponse {
  status: 'ok'
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health', { signal })
}
