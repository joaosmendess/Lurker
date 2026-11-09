// Turns a job description (plain text from the backend, one paragraph or "- item"
// per line) into blocks the UI can render as headings, lists and paragraphs.

export type DescriptionBlock =
  | { type: 'heading'; text: string }
  | { type: 'list'; items: string[] }
  | { type: 'paragraph'; text: string }

const MAX_HEADING_LENGTH = 70
// "Short line followed by a long paragraph" is a heading only if it's this short
// and the paragraph at least this long (checked against the real collected jobs)
const MAX_IMPLICIT_HEADING_LENGTH = 60
const MIN_PARAGRAPH_AFTER_HEADING = 80
const KNOWN_HEADINGS = new Set([
  'responsabilidades e atribuições',
  'requisitos e qualificações',
  'informações adicionais',
])

function isListItem(line: string): boolean {
  return line.startsWith('- ')
}

function isAllCaps(line: string): boolean {
  const letters = line.replace(/[^\p{L}]/gu, '')
  return letters.length >= 4 && letters === letters.toUpperCase()
}

/**
 * Conservative on purpose: a paragraph shown as a heading hurts reading more than
 * a heading shown as a paragraph, so a line needs a clear signal to become one.
 */
function isHeading(line: string, next: string | undefined): boolean {
  if (next === undefined || isListItem(line) || line.length > MAX_HEADING_LENGTH) return false
  if (/[.;,!?]$/.test(line)) return false
  return (
    line.endsWith(':') ||
    isListItem(next) ||
    KNOWN_HEADINGS.has(line.toLowerCase()) ||
    isAllCaps(line) ||
    isImplicitHeading(line, next)
  )
}

/**
 * "About the Role" followed by a paragraph: common in Greenhouse/Remotive, where
 * the HTML <h2> was flattened to a plain line. A line starting in lowercase is a
 * sentence broken in the middle ("estrutura da Empresa em..."), not a title.
 */
function isImplicitHeading(line: string, next: string): boolean {
  return (
    line.length <= MAX_IMPLICIT_HEADING_LENGTH &&
    !/^\p{Ll}/u.test(line) &&
    next.length >= MIN_PARAGRAPH_AFTER_HEADING &&
    !isListItem(next)
  )
}

export function parseDescription(text: string): DescriptionBlock[] {
  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

  const blocks: DescriptionBlock[] = []
  lines.forEach((line, index) => {
    if (isListItem(line)) {
      const item = line.slice(2)
      const last = blocks.at(-1)
      if (last?.type === 'list') last.items.push(item)
      else blocks.push({ type: 'list', items: [item] })
    } else if (isHeading(line, lines[index + 1])) {
      blocks.push({ type: 'heading', text: line.replace(/:$/, '') })
    } else {
      blocks.push({ type: 'paragraph', text: line })
    }
  })
  return blocks
}
