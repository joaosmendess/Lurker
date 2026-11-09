import type { ReactNode } from 'react'

interface FormSectionProps {
  title: string
  /** What this setting changes, in one or two plain sentences */
  help?: string
  children: ReactNode
}

/** One setting: title and explanation on the left (desktop) or on top (mobile). */
export function FormSection({ title, help, children }: FormSectionProps) {
  return (
    <section className="grid gap-3 border-b border-rule py-6 lg:grid-cols-[16rem_1fr] lg:gap-8">
      <div className="space-y-1">
        <h2 className="font-display text-base font-semibold">{title}</h2>
        {help && <p className="text-sm text-graphite">{help}</p>}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  )
}

interface CheckboxProps {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
}

export function Checkbox({ label, checked, onChange }: CheckboxProps) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-4 accent-signal"
      />
      {label}
    </label>
  )
}
