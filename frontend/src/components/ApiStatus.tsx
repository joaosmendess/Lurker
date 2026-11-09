import { useQuery } from '@tanstack/react-query'

import { getHealth } from '../lib/api'

export function ApiStatus() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => getHealth(signal),
    retry: false,
  })

  if (health.isPending) {
    return <p className="text-sm text-graphite">Conectando à API…</p>
  }

  if (health.isError) {
    return (
      <div className="space-y-1 text-sm" role="alert">
        <p className="font-medium text-signal">A API não respondeu.</p>
        <p className="text-graphite">
          Suba o backend em <code className="font-mono text-ink">backend/</code> com{' '}
          <code className="font-mono text-ink">uvicorn app.main:app --reload</code> e recarregue.
        </p>
      </div>
    )
  }

  return <p className="text-sm text-fit-high">API conectada.</p>
}
