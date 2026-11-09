import type { ThemePreference } from '../lib/theme'
import { useTheme } from '../lib/useTheme'

const OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: 'system', label: 'Sistema' },
  { value: 'light', label: 'Claro' },
  { value: 'dark', label: 'Escuro' },
]

// Real radio inputs (visually styled as a segmented control): arrow keys,
// screen readers and form semantics work for free.
export function ThemeSwitch() {
  const { preference, setPreference } = useTheme()

  return (
    <fieldset className="flex rounded-md border border-rule p-0.5 text-xs">
      <legend className="sr-only">Tema</legend>
      {OPTIONS.map((option) => (
        <label
          key={option.value}
          className="cursor-pointer rounded px-2 py-1 text-graphite has-checked:bg-surface has-checked:text-ink has-focus-visible:outline-2 has-focus-visible:outline-signal"
        >
          <input
            type="radio"
            name="theme"
            value={option.value}
            checked={preference === option.value}
            onChange={() => setPreference(option.value)}
            className="sr-only"
          />
          {option.label}
        </label>
      ))}
    </fieldset>
  )
}
