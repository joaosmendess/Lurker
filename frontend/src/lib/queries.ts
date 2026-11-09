// Data hooks (TanStack Query). Query keys live here so cache updates and
// invalidations always target the same keys.

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import {
  createApplication,
  createCompany,
  createTailoredResume,
  deleteApplication,
  deleteCompany,
  getApplication,
  getCollectStatus,
  getJob,
  getLLMStatus,
  getScoringStatus,
  getTailoredResume,
  getProfile,
  getStackOptions,
  getTagCounts,
  listApplications,
  listCompanies,
  listJobs,
  moveApplication,
  saveProfile,
  startCollection,
  startScoring,
  updateApplicationNotes,
  updateCompany,
  type JobFilters,
} from './api'
import type { ApplicationRead, ApplicationStatus, JobDetail, JobPage } from './types'

export const PAGE_SIZE = 50

export const queryKeys = {
  jobs: ['jobs'] as const,
  jobList: (filters: JobFilters) => ['jobs', 'list', filters] as const,
  jobCount: (filters: JobFilters) => ['jobs', 'count', filters] as const,
  tagCounts: (filters: JobFilters) => ['jobs', 'tags', filters] as const,
  job: (id: string) => ['jobs', 'detail', id] as const,
  collect: ['collect'] as const,
  profile: ['profile'] as const,
  stackOptions: ['profile', 'stack-options'] as const,
  companies: ['companies'] as const,
  llmStatus: ['llm', 'status'] as const,
  scoring: ['scoring'] as const,
  tailoredResume: (jobId: string) => ['tailored-resume', jobId] as const,
  applications: ['applications'] as const,
  board: ['applications', 'board'] as const,
  application: (id: number) => ['applications', 'detail', id] as const,
}

/** What the sidebar counts and the "Para triar" tab shows. */
export const TRIAGE_FILTERS: JobFilters = { untriaged: true, prefiltered: true }

export function useJobList(filters: JobFilters) {
  return useInfiniteQuery({
    queryKey: queryKeys.jobList(filters),
    queryFn: ({ pageParam, signal }) => listJobs(filters, PAGE_SIZE, pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const nextOffset = lastPage.offset + lastPage.limit
      return nextOffset < lastPage.total ? nextOffset : undefined
    },
  })
}

export function useJobCount(filters: JobFilters) {
  return useQuery({
    queryKey: queryKeys.jobCount(filters),
    queryFn: ({ signal }) => listJobs(filters, 1, 0, signal),
    select: (page) => page.total,
  })
}

/** Stack chip counts. The stack selection itself is left out of the key and the
 * request, so chips keep their counts while you pick several. */
export function useTagCounts(filters: JobFilters) {
  // stack: undefined is dropped by the query-key hash and by toSearchParams
  const withoutStack: JobFilters = { ...filters, stack: undefined }
  return useQuery({
    queryKey: queryKeys.tagCounts(withoutStack),
    queryFn: ({ signal }) => getTagCounts(withoutStack, signal),
  })
}

export function useJob(id: string | null) {
  return useQuery({
    queryKey: queryKeys.job(id ?? ''),
    queryFn: ({ signal }) => getJob(id!, signal),
    enabled: id !== null,
  })
}

// --- Triage ----------------------------------------------------------------------

type JobListData = InfiniteData<JobPage, number>

/**
 * Optimistic cache update: lists of untriaged jobs drop the job right away,
 * other lists just show its new status. The server confirms (or we refetch) after.
 */
function applyTriageToCache(
  queryClient: QueryClient,
  jobId: string,
  status: ApplicationStatus | null,
  applicationId: number | null,
): void {
  const lists = queryClient.getQueriesData<JobListData>({ queryKey: ['jobs', 'list'] })
  for (const [key, data] of lists) {
    if (!data) continue
    const filters = key[2] as JobFilters
    const pages = data.pages.map((page) => {
      if (filters.untriaged && status !== null) {
        const items = page.items.filter((job) => job.id !== jobId)
        const removed = page.items.length - items.length
        return { ...page, items, total: page.total - removed }
      }
      return {
        ...page,
        items: page.items.map((job) =>
          job.id === jobId
            ? { ...job, application_status: status, application_id: applicationId }
            : job,
        ),
      }
    })
    queryClient.setQueryData<JobListData>(key, { ...data, pages })
  }

  queryClient.setQueryData<JobDetail>(queryKeys.job(jobId), (job) =>
    job ? { ...job, application_status: status, application_id: applicationId } : job,
  )
}

export function useTriage() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: ApplicationStatus }) =>
      createApplication(jobId, status),
    onMutate: async ({ jobId, status }) => {
      // Stop in-flight fetches from overwriting the optimistic state
      await queryClient.cancelQueries({ queryKey: queryKeys.jobs })
      applyTriageToCache(queryClient, jobId, status, null)
    },
    onSuccess: (application, { jobId, status }) => {
      applyTriageToCache(queryClient, jobId, status, application.id)
    },
    onSettled: () => {
      // Counts, other lists and the kanban catch up with the server in the background
      invalidateApplicationsAndJobs(queryClient)
    },
  })
}

export function useUndoTriage() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ applicationId }: { applicationId: number; jobId: string }) =>
      deleteApplication(applicationId),
    onSuccess: (_, { jobId }) => {
      applyTriageToCache(queryClient, jobId, null, null)
    },
    onSettled: () => invalidateApplicationsAndJobs(queryClient),
  })
}

// --- AI score --------------------------------------------------------------------

export function useScoringStatus() {
  const queryClient = useQueryClient()
  const status = useQuery({
    queryKey: queryKeys.scoring,
    queryFn: ({ signal }) => getScoringStatus(signal),
    // While a batch runs, poll to show its progress
    refetchInterval: (query) => (query.state.data?.running ? 4000 : false),
  })

  // When a batch ends, the lists get their new scores (and order)
  const wasRunning = useRef(false)
  const running = status.data?.running ?? false
  useEffect(() => {
    if (wasRunning.current && !running) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
    }
    wasRunning.current = running
  }, [running, queryClient])

  return status
}

export function useStartScoring() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: startScoring,
    onSuccess: (status) => queryClient.setQueryData(queryKeys.scoring, status),
  })
}

/** Reload the job lists now (new scores arrived while a batch runs). */
export function useRefreshJobs() {
  const queryClient = useQueryClient()
  return () => void queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
}

// --- Tailored resume -------------------------------------------------------------

export function useLLMStatus() {
  return useQuery({
    queryKey: queryKeys.llmStatus,
    queryFn: ({ signal }) => getLLMStatus(signal),
  })
}

export function useTailoredResume(jobId: string) {
  return useQuery({
    queryKey: queryKeys.tailoredResume(jobId),
    queryFn: ({ signal }) => getTailoredResume(jobId, signal),
  })
}

export function useCreateTailoredResume(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => createTailoredResume(jobId),
    onSuccess: (tailored) => queryClient.setQueryData(queryKeys.tailoredResume(jobId), tailored),
  })
}

// --- Kanban ----------------------------------------------------------------------

/** Kanban columns, in the order of the process. "discarded" stays off the board. */
export const BOARD_STATUSES = [
  'interested',
  'applied',
  'in_process',
  'interview',
  'offer',
  'rejected',
] as const satisfies readonly ApplicationStatus[]

export function useBoard() {
  return useQuery({
    queryKey: queryKeys.board,
    queryFn: ({ signal }) => listApplications(BOARD_STATUSES, signal),
  })
}

export function useApplication(id: number | null) {
  return useQuery({
    queryKey: queryKeys.application(id ?? 0),
    queryFn: ({ signal }) => getApplication(id!, signal),
    enabled: id !== null,
  })
}

/** Cards and job lists both show the application status: refresh both. */
function invalidateApplicationsAndJobs(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.applications })
  void queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
}

export function useMoveApplication() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: ApplicationStatus }) =>
      moveApplication(id, status),
    // Optimistic: the card changes column the moment it's dropped
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.board })
      const previous = queryClient.getQueryData<ApplicationRead[]>(queryKeys.board)
      const now = new Date().toISOString()
      queryClient.setQueryData<ApplicationRead[]>(queryKeys.board, (cards) =>
        cards?.map((card) => (card.id === id ? { ...card, status, updated_at: now } : card)),
      )
      return { previous } // becomes "context" in onError
    },
    onError: (_error, _variables, context) => {
      // Server said no: put the card back where it was
      queryClient.setQueryData(queryKeys.board, context?.previous)
    },
    onSettled: () => invalidateApplicationsAndJobs(queryClient),
  })
}

export function useUpdateNotes() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, notes }: { id: number; notes: string }) => updateApplicationNotes(id, notes),
    onSuccess: (saved) => {
      queryClient.setQueryData<ApplicationRead[]>(queryKeys.board, (cards) =>
        cards?.map((card) => (card.id === saved.id ? saved : card)),
      )
      void queryClient.invalidateQueries({ queryKey: queryKeys.application(saved.id) })
    },
  })
}

/** "Voltar para a triagem": deletes the application, the job is untriaged again. */
export function useReturnToTriage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteApplication(id),
    onSettled: () => invalidateApplicationsAndJobs(queryClient),
  })
}

// --- Profile ---------------------------------------------------------------------

export function useProfile() {
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: ({ signal }) => getProfile(signal),
    retry: false, // 404 = no profile yet; retrying won't change that
  })
}

export function useStackOptions() {
  return useQuery({
    queryKey: queryKeys.stackOptions,
    queryFn: ({ signal }) => getStackOptions(signal),
    staleTime: Infinity, // the list only changes when the backend code changes
  })
}

export function useSaveProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: saveProfile,
    onSuccess: (profile) => {
      queryClient.setQueryData(queryKeys.profile, profile)
      // The pre-filter depends on the profile: every job list and count is stale now
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
    },
  })
}

// --- Watched companies -----------------------------------------------------------

export function useCompanies() {
  return useQuery({
    queryKey: queryKeys.companies,
    queryFn: ({ signal }) => listCompanies(signal),
  })
}

/** After any company change: its numbers and the job lists may both have changed. */
function useRefreshCompaniesAndJobs() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.companies })
    void queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
  }
}

export function useCreateCompany() {
  const refresh = useRefreshCompaniesAndJobs()
  return useMutation({ mutationFn: createCompany, onSuccess: refresh })
}

export function useUpdateCompany() {
  const refresh = useRefreshCompaniesAndJobs()
  return useMutation({
    mutationFn: ({ id, ...changes }: { id: number; name?: string; active?: boolean }) =>
      updateCompany(id, changes),
    onSuccess: refresh,
  })
}

export function useDeleteCompany() {
  const refresh = useRefreshCompaniesAndJobs()
  return useMutation({ mutationFn: deleteCompany, onSuccess: refresh })
}

// --- Collection ------------------------------------------------------------------

export function useCollectStatus() {
  const queryClient = useQueryClient()
  const status = useQuery({
    queryKey: queryKeys.collect,
    queryFn: ({ signal }) => getCollectStatus(signal),
    // While a collection runs, poll every 3s to notice when it finishes
    refetchInterval: (query) => (query.state.data?.running ? 3000 : false),
  })

  // When a run finishes, the job lists are stale: refresh them
  const wasRunning = useRef(false)
  const running = status.data?.running ?? false
  useEffect(() => {
    if (wasRunning.current && !running) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
    }
    wasRunning.current = running
  }, [running, queryClient])

  return status
}

export function useStartCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: startCollection,
    onSuccess: (status) => queryClient.setQueryData(queryKeys.collect, status),
  })
}
