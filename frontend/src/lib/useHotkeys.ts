import { useEffect, useRef } from 'react'

export type HotkeyMap = Record<string, () => void>

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return (
    target.isContentEditable ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  )
}

/**
 * Single-key shortcuts (j, k, x, /...). Ignored while typing in a field or when
 * a modifier is held, so Ctrl+C or typing "x" in the search box never triggers them.
 */
export function useHotkeys(hotkeys: HotkeyMap): void {
  // A ref keeps the latest handlers without re-subscribing on every render
  const hotkeysRef = useRef(hotkeys)
  useEffect(() => {
    hotkeysRef.current = hotkeys
  })

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey) return
      if (isTyping(event.target)) return
      const handler = hotkeysRef.current[event.key.toLowerCase()]
      if (handler) {
        event.preventDefault()
        handler()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])
}
