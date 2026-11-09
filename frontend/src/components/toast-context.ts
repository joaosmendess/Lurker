import { createContext, useContext } from 'react'

export interface ToastOptions {
  message: string
  /** Optional action, e.g. { label: 'Desfazer', onClick } */
  action?: { label: string; onClick: () => void }
  tone?: 'neutral' | 'error'
}

export const ToastContext = createContext<((toast: ToastOptions) => void) | null>(null)

export function useToast(): (toast: ToastOptions) => void {
  const showToast = useContext(ToastContext)
  if (!showToast) throw new Error('useToast must be used inside <ToastProvider>')
  return showToast
}
