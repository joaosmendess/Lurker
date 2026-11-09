import { useToast } from '../../components/toast-context'
import { ApiError } from '../../lib/api'
import { relativeAge } from '../../lib/format'
import { useCreateTailoredResume, useLLMStatus, useTailoredResume } from '../../lib/queries'
import type { LLMStatus } from '../../lib/types'

function errorMessage(error: Error): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return 'A cota gratuita da IA acabou por agora. Tente de novo em alguns minutos.'
    if (error.status === 409) return 'Coloque seu currículo na tela Foco antes de ajustar.'
    if (error.status === 503) return 'A IA ainda não está configurada no backend/.env.'
    if (error.status === 502) return `A IA não respondeu direito: ${error.message}`
  }
  return `Não foi possível ajustar: ${error.message}`
}

/** What's missing in the .env, in the order you'd fix it. */
function SetupSteps({ status }: { status: LLMStatus }) {
  const code = 'rounded bg-surface px-1 font-mono text-xs text-ink'
  return (
    <div className="space-y-1 text-sm text-graphite">
      <p>Para usar, configure uma IA de texto no backend:</p>
      <ol className="list-decimal space-y-0.5 pl-5">
        {!status.has_key && (
          <li>
            Crie uma chave gratuita em console.groq.com e coloque em{' '}
            <code className={code}>LLM_API_KEY</code> no <code className={code}>backend/.env</code>.
          </li>
        )}
        <li>
          Liste os modelos com <code className={code}>python -m app.llm</code> e escolha um em{' '}
          <code className={code}>LLM_MODEL</code>.
        </li>
        <li>Reinicie o backend.</li>
      </ol>
    </div>
  )
}

/** "Currículo para esta vaga": my resume rewritten for how this company's ATS reads. */
export function TailoredResumeSection({ jobId }: { jobId: string }) {
  const status = useLLMStatus()
  const tailored = useTailoredResume(jobId)
  const create = useCreateTailoredResume(jobId)
  const showToast = useToast()

  const result = tailored.data
  const configured = status.data?.configured ?? false

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      showToast({ message: 'Currículo copiado' })
    } catch {
      showToast({ message: 'O navegador não deixou copiar. Selecione o texto e copie.', tone: 'error' })
    }
  }

  const buttonClass =
    'rounded-md border border-rule px-3 py-1.5 text-sm hover:border-graphite disabled:cursor-wait disabled:opacity-60'

  return (
    <section aria-labelledby="resume-heading" className="space-y-3 border-b border-rule pb-5">
      <div className="space-y-1">
        <h2 id="resume-heading" className="font-display text-sm font-semibold">
          Currículo para esta vaga
        </h2>
        <p className="text-sm text-graphite">
          Suas experiências entram exatamente como estão. A IA só reescreve o resumo, reordena as
          habilidades e deixa o formato fácil de ler para sistemas como o da Gupy.
        </p>
      </div>

      {status.data && !configured && <SetupSteps status={status.data} />}

      {configured && !result && (
        <button type="button" onClick={() => create.mutate()} disabled={create.isPending} className={buttonClass}>
          {create.isPending ? 'Ajustando… pode levar até um minuto' : 'Ajustar meu currículo para esta vaga'}
        </button>
      )}

      {create.isError && (
        <p role="alert" className="text-sm text-signal">
          {errorMessage(create.error)}
        </p>
      )}

      {result && (
        <div className="space-y-4">
          {/* The automatic check, never hidden: the reason to trust (or not) this text */}
          {result.warnings.length > 0 ? (
            <div role="alert" className="space-y-1 rounded-md border border-signal px-3 py-2 text-sm">
              <p className="font-medium text-signal">Confira antes de usar: a verificação achou mudanças</p>
              <ul className="list-disc space-y-0.5 pl-5">
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-sm">
              <span className="text-fit-high">Verificação sem alertas:</span> experiências e datas
              iguais às do original, nenhuma habilidade removida e nenhum número ou termo técnico novo.{' '}
              <span className="text-graphite">Mesmo assim, leia o resumo antes de enviar.</span>
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => void copy(result.content)} className={buttonClass}>
              Copiar currículo
            </button>
            {configured && (
              <button type="button" onClick={() => create.mutate()} disabled={create.isPending} className={buttonClass}>
                {create.isPending ? 'Gerando…' : 'Gerar outra versão'}
              </button>
            )}
            <span className="font-mono text-xs text-graphite">
              {relativeAge(result.created_at)} · {result.model}
            </span>
          </div>

          <pre className="max-h-[28rem] overflow-y-auto rounded-md border border-rule bg-surface px-4 py-3 font-sans text-sm leading-relaxed whitespace-pre-wrap">
            {result.content}
          </pre>

          {result.changes.length > 0 && (
            <div className="space-y-1">
              <h3 className="text-sm font-semibold">O que a IA ajustou</h3>
              <ul className="list-disc space-y-0.5 pl-5 text-sm marker:text-graphite">
                {result.changes.map((change) => (
                  <li key={change}>{change}</li>
                ))}
              </ul>
            </div>
          )}

          {result.missing.length > 0 && (
            <div className="space-y-1">
              <h3 className="text-sm font-semibold">A vaga pede e seu currículo não mostra</h3>
              <p className="text-sm text-graphite">
                Não foi colocado no currículo. Vale se preparar para falar disso na entrevista.
              </p>
              <ul className="list-disc space-y-0.5 pl-5 text-sm marker:text-graphite">
                {result.missing.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
