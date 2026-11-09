import { describe, expect, it } from 'vitest'

import { readBoardInput } from './boards'

describe('readBoardInput', () => {
  it.each([
    ['https://job-boards.greenhouse.io/stone/jobs/123', 'greenhouse'],
    ['boards.greenhouse.io/embed/job_board?for=vtex', 'greenhouse'],
    ['https://jobs.lever.co/netflix', 'lever'],
    ['JOBS.LEVER.CO/netflix', 'lever'],
  ] as const)('detects the provider of %s', (text, provider) => {
    expect(readBoardInput(text)).toEqual({ kind: 'link', provider })
  })

  it('treats a bare name as a slug', () => {
    expect(readBoardInput('  stone ')).toEqual({ kind: 'slug' })
  })

  it('flags links to other sites', () => {
    expect(readBoardInput('https://stone.com.br/carreiras')).toEqual({ kind: 'unsupported' })
    // a look-alike domain must not pass as Greenhouse
    expect(readBoardInput('https://fakegreenhouse.io/stone')).toEqual({ kind: 'unsupported' })
  })

  it('is empty for blank input', () => {
    expect(readBoardInput('   ')).toEqual({ kind: 'empty' })
  })
})
