import { useCallback, useEffect, useState, type ReactNode } from 'react'

import { ToastContext, type ToastOptions } from './toast-context'

const VISIBLE_MS = 6000

interface ActiveToast extends ToastOptions {
  id: number
}

// One toast at a time: a new one replaces the previous (like Gmail's "Undo" bar).
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ActiveToast | null>(null)

  const showToast = useCallback((options: ToastOptions) => {
    setToast({ ...options, id: Date.now() })
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), VISIBLE_MS)
    return () => window.clearTimeout(timer)
  }, [toast])

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      {/* aria-live: screen readers announce the message without moving focus */}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex justify-center px-4 lg:bottom-6"
      >
        {toast && (
          <div
            key={toast.id}
            className="pointer-events-auto flex items-center gap-4 rounded-md border border-rule bg-ink px-4 py-2.5 text-sm text-paper shadow-lg"
          >
            <span className={toast.tone === 'error' ? 'font-medium' : undefined}>
              {toast.message}
            </span>
            {toast.action && (
              <button
                type="button"
                onClick={() => {
                  toast.action?.onClick()
                  setToast(null)
                }}
                // Same color as the message: the accent on an inverted (ink) background
                // would fall below AA contrast, so the underline marks it as an action
                className="font-semibold underline underline-offset-2 hover:no-underline"
              >
                {toast.action.label}
              </button>
            )}
          </div>
        )}
      </div>
    </ToastContext.Provider>
  )
}
