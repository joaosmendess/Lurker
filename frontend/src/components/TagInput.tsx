import { useId, useState, type KeyboardEvent } from 'react'

interface TagInputProps {
  label: string
  values: string[]
  onChange: (values: string[]) => void
  placeholder?: string
}

/** A list of short values edited as chips: type, press Enter (or comma) to add. */
export function TagInput({ label, values, onChange, placeholder }: TagInputProps) {
  const [draft, setDraft] = useState('')
  const inputId = useId()

  function add() {
    const value = draft.trim()
    const alreadyThere = values.some((item) => item.toLowerCase() === value.toLowerCase())
    if (value && !alreadyThere) onChange([...values, value])
    setDraft('')
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      add()
    } else if (event.key === 'Backspace' && draft === '' && values.length > 0) {
      onChange(values.slice(0, -1)) // backspace on an empty field removes the last chip
    }
  }

  return (
    <div className="space-y-2">
      <label htmlFor={inputId} className="sr-only">
        {label}
      </label>
      {values.length > 0 && (
        <ul aria-label={label} className="flex flex-wrap gap-1.5">
          {values.map((value) => (
            <li
              key={value}
              className="flex items-center gap-1 rounded border border-rule bg-surface py-0.5 pr-1 pl-2 text-sm"
            >
              {value}
              <button
                type="button"
                onClick={() => onChange(values.filter((item) => item !== value))}
                aria-label={`Remover ${value}`}
                className="rounded px-1 text-graphite hover:text-ink"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        id={inputId}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={add}
        placeholder={placeholder}
        className="w-full max-w-sm rounded-md border border-rule bg-paper px-2.5 py-1.5 text-sm placeholder:text-graphite hover:border-graphite"
      />
    </div>
  )
}
