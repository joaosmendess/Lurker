import type { ReactNode } from 'react'

/** A keyboard key hint, e.g. <Kbd>J</Kbd>. Hidden on touch-first small screens. */
export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="hidden rounded border border-current/30 px-1 font-mono text-[0.7rem] leading-4 opacity-80 lg:inline-block">
      {children}
    </kbd>
  )
}
