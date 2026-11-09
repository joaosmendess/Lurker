import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { useToast } from '../../components/toast-context'
import { ApiError } from '../../lib/api'
import { boardSource, boardUrl, PROVIDER_LABELS, readBoardInput } from '../../lib/boards'
import {
  useCompanies,
  useCreateCompany,
  useDeleteCompany,
  useUpdateCompany,
} from '../../lib/queries'
import type { Company, CompanyProvider } from '../../lib/types'
import { FormSection } from '../profile/FormSection'

const PROVIDERS = Object.entries(PROVIDER_LABELS) as [CompanyProvider, string][]

/** Above this share of the triage queue, one company is worth a second look. */
const DOMINANT_SHARE = 0.5

export function CompaniesPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl px-5 pb-10 lg:px-8">
        <header className="space-y-1 border-b border-rule py-6">
          <h1 className="font-display text-2xl font-bold tracking-tight">Empresas</h1>
          <p className="text-graphite">
            O Lurker lê a página de vagas destas empresas a cada coleta, além das fontes gerais.
          </p>
        </header>
        <AddCompanyForm />
        <CompanyList />
      </div>
    </div>
  )
}

// --- Add ---------------------------------------------------------------------------

function errorMessage(error: Error, provider: string): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return 'Essa empresa já está na lista.'
    if (error.status === 422) return 'Não encontramos essa página de vagas. Confira o link ou o nome.'
    if (error.status === 502) return `O ${provider} não respondeu. Tente de novo em instantes.`
  }
  return `Não foi possível adicionar: ${error.message}`
}

function AddCompanyForm() {
  const [board, setBoard] = useState('')
  const [name, setName] = useState('')
  const [provider, setProvider] = useState<CompanyProvider>('greenhouse')
  const [error, setError] = useState<string | null>(null)
  const create = useCreateCompany()
  const showToast = useToast()

  const input = readBoardInput(board)
  const effectiveProvider = input.kind === 'link' ? input.provider : provider
  const canSubmit =
    (input.kind === 'link' || input.kind === 'slug') && name.trim() !== '' && !create.isPending

  function handleSubmit(event: FormEvent) {
    event.preventDefault() // a <form> would reload the page, like in plain HTML
    if (!canSubmit) return
    setError(null)
    create.mutate(
      {
        slug: board.trim(),
        name: name.trim(),
        // A link already says its provider; only a bare name needs the choice
        ...(input.kind === 'slug' ? { provider } : {}),
      },
      {
        onSuccess: (company) => {
          setBoard('')
          setName('')
          const jobs = company.found_jobs === 1 ? 'vaga aberta' : 'vagas abertas'
          showToast({
            message: `${company.name} adicionada: ${company.found_jobs} ${jobs}, ${company.saved_jobs} novas.`,
          })
        },
        onError: (failure) => setError(errorMessage(failure, PROVIDER_LABELS[effectiveProvider])),
      },
    )
  }

  const fieldClass =
    'w-full rounded-md border border-rule bg-paper px-2.5 py-1.5 text-sm placeholder:text-graphite hover:border-graphite'

  return (
    <FormSection
      title="Adicionar empresa"
      help="No site de carreiras da empresa, abra uma vaga. Se o endereço tiver greenhouse.io ou lever.co, cole aqui."
    >
      <form onSubmit={handleSubmit} className="space-y-3">
        <label className="block space-y-1">
          <span className="text-sm font-medium">Link da página de vagas</span>
          <input
            value={board}
            onChange={(event) => {
              setBoard(event.target.value)
              setError(null)
            }}
            placeholder="https://job-boards.greenhouse.io/empresa"
            spellCheck={false}
            autoComplete="off"
            className={`${fieldClass} font-mono`}
          />
        </label>

        {input.kind === 'link' && (
          <p className="text-sm text-graphite">Página do {PROVIDER_LABELS[input.provider]}.</p>
        )}
        {input.kind === 'unsupported' && (
          <p className="text-sm text-signal">
            Esse link não é do Greenhouse nem do Lever, os dois sites que o Lurker sabe ler.
          </p>
        )}
        {input.kind === 'slug' && (
          <fieldset className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
            <legend className="sr-only">Site da página de vagas</legend>
            <span className="text-graphite">Nome do board no</span>
            {PROVIDERS.map(([value, label]) => (
              <label key={value} className="flex cursor-pointer items-center gap-2">
                <input
                  type="radio"
                  name="provider"
                  checked={provider === value}
                  onChange={() => setProvider(value)}
                  className="size-4 accent-signal"
                />
                {label}
              </label>
            ))}
          </fieldset>
        )}

        <div className="flex flex-wrap items-end gap-3">
          <label className="block min-w-48 flex-1 space-y-1">
            <span className="text-sm font-medium">Nome da empresa</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Ex.: Nubank"
              className={fieldClass}
            />
          </label>
          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded-md bg-signal px-4 py-1.5 text-sm font-medium text-on-signal hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {create.isPending ? 'Verificando a página…' : 'Adicionar'}
          </button>
        </div>

        {error && (
          <p role="alert" className="text-sm text-signal">
            {error}
          </p>
        )}
      </form>
    </FormSection>
  )
}

// --- List --------------------------------------------------------------------------

/** Active first; then the ones that bring the most jobs to triage. */
function byRelevance(a: Company, b: Company): number {
  if (a.active !== b.active) return a.active ? -1 : 1
  return b.to_triage - a.to_triage || a.name.localeCompare(b.name, 'pt-BR')
}

function CompanyList() {
  const companies = useCompanies()

  if (companies.isPending) return <p className="py-6 text-sm text-graphite">Carregando empresas…</p>
  if (companies.isError) {
    return (
      <p role="alert" className="py-6 text-sm text-signal">
        Não foi possível carregar as empresas: {companies.error.message}
      </p>
    )
  }

  const sorted = [...companies.data].sort(byRelevance)
  const active = sorted.filter((company) => company.active)
  const queue = active.reduce((sum, company) => sum + company.to_triage, 0)

  if (sorted.length === 0) {
    return (
      <p className="py-6 text-sm text-graphite">
        Nenhuma empresa ainda. As vagas vêm só das fontes gerais (Gupy, Remotive, GitHub).
      </p>
    )
  }

  return (
    <section aria-labelledby="companies-heading" className="pt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-2">
        <h2 id="companies-heading" className="font-display text-base font-semibold">
          Monitoradas
        </h2>
        <p className="font-mono text-xs text-graphite">
          {active.length} de {sorted.length} ativas · {queue} para triar
        </p>
      </div>
      <ul className="divide-y divide-rule">
        {sorted.map((company) => (
          <CompanyRow
            key={company.id}
            company={company}
            share={company.active && queue > 0 ? company.to_triage / queue : 0}
          />
        ))}
      </ul>
    </section>
  )
}

function CompanyRow({ company, share }: { company: Company; share: number }) {
  const [confirmingRemoval, setConfirmingRemoval] = useState(false)
  const update = useUpdateCompany()
  const remove = useDeleteCompany()
  const showToast = useToast()
  const busy = update.isPending || remove.isPending

  function togglePaused() {
    update.mutate(
      { id: company.id, active: !company.active },
      {
        onSuccess: (saved) =>
          showToast({
            message: saved.active
              ? `${saved.name} volta a entrar na coleta.`
              : `${saved.name} pausada. Fica fora das próximas coletas.`,
          }),
        onError: (error) => showToast({ message: `Não deu para salvar: ${error.message}`, tone: 'error' }),
      },
    )
  }

  function handleRemove() {
    remove.mutate(company.id, {
      onSuccess: () => showToast({ message: `${company.name} removida. As vagas já coletadas continuam.` }),
      onError: (error) => showToast({ message: `Não deu para remover: ${error.message}`, tone: 'error' }),
    })
  }

  const percent = Math.round(share * 100)
  const jobsLink = `/vagas?${new URLSearchParams({ fonte: boardSource(company) })}`
  const actionClass = 'rounded-md px-2.5 py-1 text-sm text-graphite hover:bg-surface hover:text-ink disabled:opacity-40'

  return (
    <li className={`grid gap-3 py-4 sm:grid-cols-[1fr_auto] sm:items-center ${company.active ? '' : 'opacity-70'}`}>
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="font-display text-base font-semibold">{company.name}</h3>
          <a
            href={boardUrl(company.provider, company.slug)}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-xs text-graphite underline-offset-2 hover:text-ink hover:underline"
          >
            {company.provider}/{company.slug}
          </a>
          {!company.active && <span className="text-xs font-medium text-graphite">Pausada</span>}
          {company.failed_last_collect && (
            <span className="text-xs font-medium text-signal">Falhou na última coleta</span>
          )}
        </div>

        <p className="font-mono text-xs text-graphite">
          <span className="text-ink">{company.to_triage}</span> para triar · {company.job_count} coletadas
        </p>

        {/* Share of the triage queue: the reason to pause a company, made visible */}
        {percent > 0 && (
          <div className="flex items-center gap-2">
            <div aria-hidden="true" className="h-1 w-full max-w-56 overflow-hidden rounded-full bg-rule">
              <div
                className={`h-full rounded-full ${share > DOMINANT_SHARE ? 'bg-signal' : 'bg-graphite'}`}
                style={{ width: `${percent}%` }}
              />
            </div>
            <span className={`font-mono text-xs ${share > DOMINANT_SHARE ? 'text-signal' : 'text-graphite'}`}>
              {percent}% da fila
            </span>
          </div>
        )}
      </div>

      {confirmingRemoval ? (
        <div className="flex flex-wrap items-center gap-2 text-sm sm:justify-end">
          <span className="text-graphite">Parar de monitorar? As vagas coletadas ficam.</span>
          <button
            type="button"
            onClick={handleRemove}
            disabled={busy}
            className="rounded-md bg-signal px-2.5 py-1 font-medium text-on-signal hover:opacity-90 disabled:opacity-40"
          >
            Remover
          </button>
          <button type="button" onClick={() => setConfirmingRemoval(false)} className={actionClass}>
            Cancelar
          </button>
        </div>
      ) : (
        <div className="-ml-2.5 flex flex-wrap items-center gap-1 sm:ml-0 sm:justify-end">
          <Link to={jobsLink} className={actionClass}>
            Ver vagas
          </Link>
          <button type="button" onClick={togglePaused} disabled={busy} className={actionClass}>
            {company.active ? 'Pausar' : 'Retomar'}
          </button>
          <button type="button" onClick={() => setConfirmingRemoval(true)} disabled={busy} className={actionClass}>
            Remover
          </button>
        </div>
      )}
    </li>
  )
}
