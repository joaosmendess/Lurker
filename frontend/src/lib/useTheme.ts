import { useEffect, useState } from 'react'

import {
  applyTheme,
  readPreference,
  resolveTheme,
  savePreference,
  systemPrefersDark,
  watchSystemTheme,
  type ResolvedTheme,
  type ThemePreference,
} from './theme'

export function useTheme(): {
  preference: ThemePreference
  resolved: ResolvedTheme
  setPreference: (preference: ThemePreference) => void
} {
  const [preference, setPreferenceState] = useState<ThemePreference>(readPreference)
  const [prefersDark, setPrefersDark] = useState<boolean>(systemPrefersDark)

  // Follow OS changes live (only matters while preference is "system")
  useEffect(() => watchSystemTheme(setPrefersDark), [])

  const resolved = resolveTheme(preference, prefersDark)

  useEffect(() => {
    applyTheme(resolved)
  }, [resolved])

  function setPreference(next: ThemePreference): void {
    savePreference(next)
    setPreferenceState(next)
  }

  return { preference, resolved, setPreference }
}
