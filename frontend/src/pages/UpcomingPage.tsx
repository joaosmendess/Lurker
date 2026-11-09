/** Temporary page for screens built in the next phase-4 steps. */
export function UpcomingPage({ title, description }: { title: string; description: string }) {
  return (
    <div className="mx-auto max-w-xl space-y-3 px-5 py-8">
      <h1 className="font-display text-2xl font-bold tracking-tight">{title}</h1>
      <p className="text-graphite">{description}</p>
    </div>
  )
}
