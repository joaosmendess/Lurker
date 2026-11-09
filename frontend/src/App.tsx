import { ApiStatus } from './components/ApiStatus'
import { ThemeSwitch } from './components/ThemeSwitch'

// Temporary screen for the setup step: checks fonts, tokens, themes and the API
// connection. The real screens (job list, kanban, profile) replace it next.

const SWATCHES = ['paper', 'surface', 'ink', 'graphite', 'rule', 'signal'] as const

const SAMPLE_ROWS = [
  { score: 82, fit: 'text-fit-high', title: 'Desenvolvedor .NET Pleno', company: 'Empresa exemplo', meta: 'Remoto · Gupy', age: '2d' },
  { score: 64, fit: 'text-fit-mid', title: 'Full Stack React / Node', company: 'Outra empresa', meta: 'Maceió · híbrido · Gupy', age: '3d' },
  { score: 41, fit: 'text-fit-low', title: 'Backend Engineer (Go)', company: 'Mais uma', meta: 'Remoto · Greenhouse', age: '5d' },
]

export default function App() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <header className="flex items-center justify-between gap-4 border-b border-rule pb-4">
        <h1 className="font-display text-xl font-bold tracking-tight">Lurker</h1>
        <ThemeSwitch />
      </header>

      <main className="space-y-10 pt-8">
        <section aria-labelledby="api-heading" className="space-y-2">
          <h2 id="api-heading" className="font-display text-sm font-semibold uppercase tracking-wide text-graphite">
            Conexão
          </h2>
          <ApiStatus />
        </section>

        <section aria-labelledby="rows-heading" className="space-y-2">
          <h2 id="rows-heading" className="font-display text-sm font-semibold uppercase tracking-wide text-graphite">
            Exemplo de lista de vagas
          </h2>
          <ul className="divide-y divide-rule rounded-md border border-rule bg-surface">
            {SAMPLE_ROWS.map((row) => (
              <li key={row.title} className="flex items-baseline gap-4 px-4 py-2.5">
                <span className={`w-7 shrink-0 text-right font-mono text-sm font-semibold ${row.fit}`}>
                  {row.score}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{row.title}</span>
                  <span className="block truncate text-sm text-graphite">
                    {row.company} · {row.meta}
                  </span>
                </span>
                <span className="shrink-0 font-mono text-xs text-graphite">{row.age}</span>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="tokens-heading" className="space-y-2">
          <h2 id="tokens-heading" className="font-display text-sm font-semibold uppercase tracking-wide text-graphite">
            Tokens
          </h2>
          <ul className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {SWATCHES.map((name) => (
              <li key={name} className="space-y-1">
                <span
                  className="block h-10 rounded-md border border-rule"
                  style={{ background: `var(--${name})` }}
                />
                <span className="font-mono text-xs text-graphite">{name}</span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="mt-4 rounded-md bg-signal px-3 py-1.5 text-sm font-medium text-on-signal hover:opacity-90"
          >
            Ação principal
          </button>
        </section>
      </main>
    </div>
  )
}
