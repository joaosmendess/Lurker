// Company job boards (Greenhouse, Lever): which provider a pasted link belongs to,
// and the public page of a board. The backend does the real parsing; this only
// decides what the form shows while you type.

import type { CompanyProvider } from './types'

export const PROVIDER_LABELS: Record<CompanyProvider, string> = {
  greenhouse: 'Greenhouse',
  lever: 'Lever',
}

const PROVIDER_DOMAINS: [domain: string, provider: CompanyProvider][] = [
  ['greenhouse.io', 'greenhouse'],
  ['lever.co', 'lever'],
]

export type BoardInput =
  | { kind: 'empty' }
  | { kind: 'slug' } // a bare name like "stone": the provider must be chosen
  | { kind: 'link'; provider: CompanyProvider }
  | { kind: 'unsupported' } // a link, but not to a supported board

/** What the user typed in the board field. */
export function readBoardInput(text: string): BoardInput {
  const value = text.trim().toLowerCase()
  if (value === '') return { kind: 'empty' }
  if (!value.includes('.') && !value.includes('/')) return { kind: 'slug' }

  let hostname: string
  try {
    hostname = new URL(value.includes('://') ? value : `https://${value}`).hostname
  } catch {
    return { kind: 'unsupported' }
  }
  const match = PROVIDER_DOMAINS.find(
    ([domain]) => hostname === domain || hostname.endsWith(`.${domain}`),
  )
  return match ? { kind: 'link', provider: match[1] } : { kind: 'unsupported' }
}

/** The board's public page, where the user can check what the Lurker reads. */
export function boardUrl(provider: CompanyProvider, slug: string): string {
  return provider === 'greenhouse'
    ? `https://job-boards.greenhouse.io/${slug}`
    : `https://jobs.lever.co/${slug}`
}

/** The job-list "fonte" value for one company's board: "greenhouse:stone". */
export function boardSource(company: { provider: CompanyProvider; slug: string }): string {
  return `${company.provider}:${company.slug}`
}
