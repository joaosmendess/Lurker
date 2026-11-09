import { useState } from 'react'

import { TagInput } from '../../components/TagInput'
import { ThemeSwitch } from '../../components/ThemeSwitch'
import { useToast } from '../../components/toast-context'
import { ApiError } from '../../lib/api'
import { useProfile, useSaveProfile, useStackOptions } from '../../lib/queries'
import type { ContractType, Profile, ProfileInput, WorkMode } from '../../lib/types'
import { Checkbox, FormSection } from './FormSection'

const WORK_MODES: { value: WorkMode; label: string }[] = [
  { value: 'remote', label: 'Remoto' },
  { value: 'hybrid', label: 'Híbrido' },
  { value: 'onsite', label: 'Presencial' },
]

const CONTRACT_TYPES: { value: ContractType; label: string }[] = [
  { value: 'clt', label: 'CLT' },
  { value: 'pj', label: 'PJ' },
]

const EMPTY_PROFILE: ProfileInput = {
  resume: '',
  work_modes: ['remote'],
  accepted_cities: [],
  seniority_levels: [],
  contract_types: ['clt', 'pj'],
  salary_expectation: '',
  excluded_title_words: [],
  preferred_stack: [],
  strict_unknown_work_mode: false,
}

/** Only what PUT /profile accepts (no updated_at), so "dirty" compares like with like. */
function toInput(profile: Profile): ProfileInput {
  return {
    resume: profile.resume,
    work_modes: profile.work_modes,
    accepted_cities: profile.accepted_cities,
    seniority_levels: profile.seniority_levels,
    contract_types: profile.contract_types,
    salary_expectation: profile.salary_expectation,
    excluded_title_words: profile.excluded_title_words,
    preferred_stack: profile.preferred_stack,
    strict_unknown_work_mode: profile.strict_unknown_work_mode,
  }
}

/** Adds or removes `value` from a list, keeping the original order of the rest. */
function toggled<T>(list: T[], value: T, on: boolean): T[] {
  return on ? [...list, value] : list.filter((item) => item !== value)
}

export function ProfilePage() {
  const profile = useProfile()

  if (profile.isPending) {
    return <p className="p-6 text-sm text-graphite">Carregando perfil…</p>
  }

  const noProfileYet = profile.isError && profile.error instanceof ApiError && profile.error.status === 404
  if (profile.isError && !noProfileYet) {
    return (
      <p role="alert" className="p-6 text-sm text-signal">
        Não foi possível carregar o perfil: {profile.error.message}
      </p>
    )
  }

  const initial = profile.data ? toInput(profile.data) : EMPTY_PROFILE
  // key: after a save, updated_at changes and the form restarts from the saved data
  return <ProfileForm key={profile.data?.updated_at ?? 'new'} initial={initial} />
}

function ProfileForm({ initial }: { initial: ProfileInput }) {
  const [draft, setDraft] = useState<ProfileInput>(initial)
  const save = useSaveProfile()
  const stackOptions = useStackOptions()
  const showToast = useToast()

  const dirty = JSON.stringify(draft) !== JSON.stringify(initial)
  const canSave = dirty && draft.resume.trim() !== '' && draft.work_modes.length > 0

  // Partial<T>: every field of T becomes optional, like a "patch" object
  function update(changes: Partial<ProfileInput>) {
    setDraft((current) => ({ ...current, ...changes }))
  }

  function handleSave() {
    save.mutate(draft, {
      onSuccess: () => showToast({ message: 'Perfil salvo. A lista de vagas já usa o novo foco.' }),
      onError: (error) => showToast({ message: `Não foi possível salvar: ${error.message}`, tone: 'error' }),
    })
  }

  const acceptsInPerson = draft.work_modes.includes('hybrid') || draft.work_modes.includes('onsite')

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-5 pb-10 lg:px-8">
          <header className="space-y-1 border-b border-rule py-6">
            <h1 className="font-display text-2xl font-bold tracking-tight">Foco e perfil</h1>
            <p className="text-graphite">
              O que você define aqui decide quais vagas aparecem em “Para triar”.
            </p>
          </header>

          <FormSection
            title="Modalidade"
            help="Vagas híbridas e presenciais só aparecem nas cidades aceitas."
          >
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {WORK_MODES.map((mode) => (
                <Checkbox
                  key={mode.value}
                  label={mode.label}
                  checked={draft.work_modes.includes(mode.value)}
                  onChange={(on) => update({ work_modes: toggled(draft.work_modes, mode.value, on) })}
                />
              ))}
            </div>
            {draft.work_modes.length === 0 && (
              <p className="mt-2 text-sm text-signal">Escolha pelo menos uma modalidade.</p>
            )}
          </FormSection>

          <FormSection
            title="Cidades aceitas"
            help={
              acceptsInPerson
                ? 'Para vagas híbridas e presenciais.'
                : 'Só valem se você aceitar vagas híbridas ou presenciais.'
            }
          >
            <TagInput
              label="Cidades aceitas"
              values={draft.accepted_cities}
              onChange={(accepted_cities) => update({ accepted_cities })}
              placeholder="Adicionar cidade e Enter"
            />
          </FormSection>

          <FormSection
            title="Vagas sem modalidade informada"
            help="Algumas fontes, como o Greenhouse, não dizem se a vaga é remota."
          >
            <fieldset className="space-y-2 text-sm">
              <legend className="sr-only">Vagas sem modalidade informada</legend>
              <label className="flex cursor-pointer items-start gap-2">
                <input
                  type="radio"
                  name="unknown-mode"
                  checked={!draft.strict_unknown_work_mode}
                  onChange={() => update({ strict_unknown_work_mode: false })}
                  className="mt-0.5 size-4 accent-signal"
                />
                <span>
                  Mostrar todas
                  <span className="block text-graphite">A IA lê a descrição e decide. Traz mais vagas.</span>
                </span>
              </label>
              <label className="flex cursor-pointer items-start gap-2">
                <input
                  type="radio"
                  name="unknown-mode"
                  checked={draft.strict_unknown_work_mode}
                  onChange={() => update({ strict_unknown_work_mode: true })}
                  className="mt-0.5 size-4 accent-signal"
                />
                <span>
                  Esconder as que citam outra cidade
                  <span className="block text-graphite">
                    Locais amplos, como “Brasil” ou “LATAM”, continuam aparecendo.
                  </span>
                </span>
              </label>
            </fieldset>
          </FormSection>

          <FormSection
            title="Stacks preferidas"
            help="Já vêm marcadas na lista de vagas. É só um filtro de visualização: nenhuma vaga é descartada."
          >
            <div role="group" aria-label="Stacks preferidas" className="flex flex-wrap gap-1.5">
              {(stackOptions.data ?? []).map((tag) => {
                const active = draft.preferred_stack.includes(tag)
                return (
                  <button
                    key={tag}
                    type="button"
                    aria-pressed={active}
                    onClick={() => update({ preferred_stack: toggled(draft.preferred_stack, tag, !active) })}
                    className={`rounded border px-1.5 py-0.5 font-mono text-xs ${
                      active
                        ? 'border-signal bg-surface text-ink'
                        : 'border-rule text-graphite hover:border-graphite hover:text-ink'
                    }`}
                  >
                    {tag}
                  </button>
                )
              })}
            </div>
          </FormSection>

          <FormSection
            title="Palavras que excluem a vaga"
            help="Se o título tiver uma delas, a vaga nem chega à triagem. Maiúsculas e acentos não importam."
          >
            <TagInput
              label="Palavras que excluem a vaga"
              values={draft.excluded_title_words}
              onChange={(excluded_title_words) => update({ excluded_title_words })}
              placeholder="Ex.: estágio, staff"
            />
          </FormSection>

          <FormSection title="Senioridade" help="A IA usa para avaliar se o nível da vaga combina com você.">
            <TagInput
              label="Senioridade"
              values={draft.seniority_levels}
              onChange={(seniority_levels) => update({ seniority_levels })}
              placeholder="Ex.: júnior, pleno"
            />
          </FormSection>

          <FormSection title="Regime">
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {CONTRACT_TYPES.map((type) => (
                <Checkbox
                  key={type.value}
                  label={type.label}
                  checked={draft.contract_types.includes(type.value)}
                  onChange={(on) => update({ contract_types: toggled(draft.contract_types, type.value, on) })}
                />
              ))}
            </div>
          </FormSection>

          <FormSection title="Pretensão salarial" help="Texto livre, lido pela IA.">
            <input
              value={draft.salary_expectation}
              onChange={(event) => update({ salary_expectation: event.target.value })}
              placeholder="Ex.: CLT R$ 5.000 / PJ R$ 4.000 a 6.000"
              className="w-full max-w-md rounded-md border border-rule bg-paper px-2.5 py-1.5 text-sm placeholder:text-graphite hover:border-graphite"
            />
          </FormSection>

          <FormSection
            title="Currículo"
            help="Texto puro. Vai para a IA na pontuação, então deixe sem telefone e e-mail."
          >
            <textarea
              value={draft.resume}
              onChange={(event) => update({ resume: event.target.value })}
              rows={16}
              aria-label="Currículo"
              className="w-full rounded-md border border-rule bg-paper px-3 py-2 text-sm leading-relaxed hover:border-graphite"
            />
            <p className="mt-1 font-mono text-xs text-graphite">{draft.resume.length} caracteres</p>
            {draft.resume.trim() === '' && (
              <p className="mt-1 text-sm text-signal">O currículo não pode ficar vazio.</p>
            )}
          </FormSection>

          <section className="py-6 lg:hidden">
            <h2 className="mb-2 font-display text-base font-semibold">Aparência</h2>
            <ThemeSwitch />
          </section>
        </div>
      </div>

      {/* Save bar: always visible, so changes are never lost by scrolling away */}
      <footer className="flex items-center justify-end gap-3 border-t border-rule bg-paper px-5 py-3 lg:px-8">
        {dirty && <p className="mr-auto text-sm text-graphite">Alterações não salvas</p>}
        <button
          type="button"
          onClick={() => setDraft(initial)}
          disabled={!dirty || save.isPending}
          className="rounded-md px-3 py-1.5 text-sm text-graphite hover:text-ink disabled:invisible"
        >
          Descartar alterações
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={!canSave || save.isPending}
          className="rounded-md bg-signal px-4 py-1.5 text-sm font-medium text-on-signal hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {save.isPending ? 'Salvando…' : 'Salvar'}
        </button>
      </footer>
    </div>
  )
}
