import { ScoreStamp } from '../../components/ScoreStamp'
import { useToast } from '../../components/toast-context'
import type { JobAnalysis } from '../../lib/types'

function ListBlock({ title, items, marker }: { title: string; items: string[]; marker: string }) {
  if (items.length === 0) return null
  return (
    <div className="space-y-1">
      <h3 className="text-sm font-semibold">{title}</h3>
      <ul className="space-y-0.5 text-sm">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span aria-hidden="true" className="font-mono text-graphite">
              {marker}
            </span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** The AI's view of the job: score, why, what I have and lack, alerts and a pitch. */
export function AnalysisSection({ analysis }: { analysis: JobAnalysis | null | undefined }) {
  const showToast = useToast()

  async function copyPitch(pitch: string) {
    try {
      await navigator.clipboard.writeText(pitch)
      showToast({ message: 'Pitch copiado' })
    } catch {
      showToast({ message: 'O navegador não deixou copiar. Selecione o texto e copie.', tone: 'error' })
    }
  }

  return (
    <section aria-labelledby="analysis-heading" className="space-y-4 border-t border-rule pt-4">
      <h2 id="analysis-heading" className="font-display text-sm font-semibold">
        Análise
      </h2>

      {!analysis ? (
        <p className="text-sm text-graphite">
          Ainda sem nota. Use “Analisar vagas” no menu: as vagas são analisadas em lotes, as mais
          promissoras primeiro.
        </p>
      ) : (
        <>
          <div className="flex items-start gap-3">
            <ScoreStamp score={analysis.score} size="lg" />
            <p className="text-sm leading-relaxed">{analysis.summary}</p>
          </div>

          {analysis.red_flags.length > 0 && (
            <div className="space-y-1 rounded-md border border-fit-mid px-3 py-2">
              <h3 className="text-sm font-semibold text-fit-mid">Atenção</h3>
              <ul className="list-disc space-y-0.5 pl-5 text-sm">
                {analysis.red_flags.map((flag) => (
                  <li key={flag}>{flag}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <ListBlock title="O que você tem" items={analysis.matches} marker="+" />
            <ListBlock title="O que falta" items={analysis.gaps} marker="−" />
          </div>

          {analysis.pitch && (
            <div className="space-y-2">
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="text-sm font-semibold">Pitch</h3>
                <button
                  type="button"
                  onClick={() => void copyPitch(analysis.pitch)}
                  className="rounded-md border border-rule px-2.5 py-1 text-sm hover:border-graphite"
                >
                  Copiar pitch
                </button>
              </div>
              <p className="rounded-md border border-rule bg-surface px-3 py-2 text-sm leading-relaxed">
                {analysis.pitch}
              </p>
              {analysis.pitch_warnings.length > 0 && (
                <p role="alert" className="text-sm text-fit-mid">
                  Confira antes de usar: {analysis.pitch_warnings.join(' · ')}
                </p>
              )}
            </div>
          )}

          <p className="font-mono text-xs text-graphite">{analysis.model}</p>
        </>
      )}
    </section>
  )
}
