import { NavLink, Outlet } from 'react-router'

import { ThemeSwitch } from '../components/ThemeSwitch'
import { TRIAGE_FILTERS, useJobCount } from '../lib/queries'
import { CollectPanel } from './CollectPanel'
import { ScoringPanel } from './ScoringPanel'

const NAV_ITEMS = [
  { to: '/vagas', label: 'Vagas' },
  { to: '/kanban', label: 'Kanban' },
  { to: '/empresas', label: 'Empresas' },
  { to: '/perfil', label: 'Foco' },
] as const

function TriageCount() {
  const count = useJobCount(TRIAGE_FILTERS)
  if (!count.data) return null
  return (
    <span className="font-mono text-xs text-graphite" aria-label={`${count.data} para triar`}>
      {count.data}
    </span>
  )
}

export function AppShell() {
  return (
    <div className="flex h-dvh flex-col lg:flex-row">
      {/* Desktop sidebar */}
      <aside className="hidden w-56 shrink-0 flex-col justify-between border-r border-rule px-4 py-5 lg:flex">
        <div className="space-y-6">
          <p className="px-2 font-display text-lg font-bold tracking-tight">Lurker</p>
          <nav aria-label="Principal">
            <ul className="space-y-0.5">
              {NAV_ITEMS.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      `flex items-center justify-between rounded-md px-2 py-1.5 text-sm ${
                        isActive ? 'bg-surface font-semibold text-ink' : 'text-graphite hover:text-ink'
                      }`
                    }
                  >
                    {item.label}
                    {item.to === '/vagas' && <TriageCount />}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <div className="space-y-5">
          <ScoringPanel />
          <CollectPanel />
          <ThemeSwitch />
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="flex items-center justify-between border-b border-rule px-4 py-2.5 lg:hidden">
        <p className="font-display text-base font-bold tracking-tight">Lurker</p>
        <CollectPanel compact />
      </header>

      <main className="min-h-0 min-w-0 flex-1">
        <Outlet />
      </main>

      {/* Mobile bottom navigation: within thumb reach */}
      <nav aria-label="Principal" className="border-t border-rule lg:hidden">
        <ul className="grid grid-cols-4">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  `flex min-h-12 items-center justify-center text-sm ${
                    isActive ? 'font-semibold text-ink' : 'text-graphite'
                  }`
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
