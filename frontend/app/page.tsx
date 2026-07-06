'use client'
import { useQuery } from '@tanstack/react-query'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'

export default function DashboardPage() {
  const { data: events } = useQuery({ queryKey: ['dash-events'], queryFn: () => api.get<any>(endpoints.accountingEvents + '?limit=5') })
  const { data: entries } = useQuery({ queryKey: ['dash-ledger'], queryFn: () => api.get<any>(endpoints.ledgerEntries + '?limit=5') })
  const { data: reports } = useQuery({ queryKey: ['dash-reports'], queryFn: () => api.get<any>(endpoints.reports + '?limit=5') })
  const { data: control } = useQuery({ queryKey: ['dash-control'], queryFn: () => api.get<any>(endpoints.controlActions + '?limit=5') })
  const { data: gaps } = useQuery({ queryKey: ['dash-gaps'], queryFn: () => api.get<any>(endpoints.reconciliationRuns + '?limit=1') })
  const { data: metrics } = useQuery({ queryKey: ['dash-metrics'], queryFn: () => api.get<any>(endpoints.controlMetrics + '?limit=5') })

  const eItems = (events as any)?.items || []
  const lItems = (entries as any)?.items || []
  const rItems = (reports as any)?.items || []
  const cItems = (control as any)?.items || []
  const mItems = (metrics as any)?.items || []
  const latestMetrics = mItems[0] || {}
  const totalEvents = (events as any)?.total || eItems.length
  const gItems = (gaps as any)?.items || []
  const totalGaps = gItems.reduce((s: number, r: any) => s + (r.gaps_count || 0), 0)

  const statusColor = (s: string) =>
    ({ draft: 'bg-gray-100', validated: 'bg-blue-50 text-blue-700', ai_reviewed: 'bg-purple-50 text-purple-700', accountant_approved: 'bg-green-50 text-green-700', submitted: 'bg-gray-200' })[s] || 'bg-gray-100'

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <h1 className="text-2xl font-bold mb-6">Бухгалтерия</h1>

        {/* Health cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="p-4 bg-white rounded-xl border">
            <div className="w-3 h-3 rounded-full bg-green-500 mb-2" />
            <p className="text-2xl font-bold">{latestMetrics?.health_state || '—'}</p>
            <p className="text-sm text-muted-foreground">Статус системы</p>
          </div>
          <div className="p-4 bg-white rounded-xl border">
            <div className="w-3 h-3 rounded-full bg-blue-500 mb-2" />
            <p className="text-2xl font-bold">{totalEvents}</p>
            <p className="text-sm text-muted-foreground">Событий сегодня</p>
          </div>
          <div className="p-4 bg-white rounded-xl border">
            <div className="w-3 h-3 rounded-full bg-yellow-500 mb-2" />
            <p className="text-2xl font-bold">{cItems.filter((a: any) => a.status === 'pending').length}</p>
            <p className="text-sm text-muted-foreground">Ожидают согласования</p>
          </div>
          <div className="p-4 bg-white rounded-xl border">
            <div className="w-3 h-3 rounded-full bg-red-500 mb-2" />
            <p className="text-2xl font-bold">{totalGaps}</p>
            <p className="text-sm text-muted-foreground">Открытых расхождений</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 mb-6">
          {/* Events */}
          <div className="bg-white rounded-xl border p-4">
            <h3 className="font-semibold mb-3">Последние события</h3>
            <div className="space-y-1">
              {eItems.slice(0, 5).map((e: any) => (
                <div key={e.id} className="flex justify-between text-xs py-1 border-b last:border-0">
                  <span className="font-mono">{e.id?.slice(0, 8)}</span>
                  <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-[10px]">{e.event_type}</span>
                  <span className="font-mono">{Number(e.amount || 0).toLocaleString()}</span>
                  <span className={['px-1.5 py-0.5 rounded text-[10px]',
                    e.decision_state === 'included' ? 'bg-green-50 text-green-700' :
                    e.decision_state === 'excluded' ? 'bg-red-50 text-red-700' : 'bg-yellow-50'
                  ].join(' ')}>{e.decision_state || 'pending'}</span>
                </div>
              ))}
              {eItems.length === 0 && <p className="text-xs text-muted-foreground">Нет событий</p>}
            </div>
          </div>

          {/* Reports */}
          <div className="bg-white rounded-xl border p-4">
            <h3 className="font-semibold mb-3">Отчёты к отправке</h3>
            <div className="space-y-1">
              {rItems.filter((r: any) => r.status !== 'submitted').slice(0, 5).map((r: any) => (
                <div key={r.id} className="flex justify-between text-xs py-1 border-b last:border-0">
                  <span className="font-mono">{r.id?.slice(0, 8)}</span>
                  <span className={['px-1.5 py-0.5 rounded text-[10px]', statusColor(r.status)].join(' ')}>{r.status}</span>
                  <span className="font-mono">{Number(r.total_tax || 0).toLocaleString()}</span>
                </div>
              ))}
              {rItems.filter((r: any) => r.status !== 'submitted').length === 0 &&
                <p className="text-xs text-muted-foreground">Всё отправлено</p>}
            </div>
          </div>
        </div>

        {/* Recent activity */}
        <div className="bg-white rounded-xl border p-4">
          <h3 className="font-semibold mb-3">Последние действия</h3>
          <div className="space-y-1">
            {cItems.slice(0, 8).map((a: any) => (
              <div key={a.id} className="flex justify-between text-xs py-1 border-b last:border-0">
                <span className="font-mono w-20">{a.action_type}</span>
                <span className="text-muted-foreground">{a.target_system}</span>
                <span className="font-mono text-muted-foreground">{a.actor_id?.slice(0, 8)}</span>
                <span className={['px-1.5 py-0.5 rounded text-[10px]',
                  a.status === 'completed' ? 'bg-green-50 text-green-700' :
                  a.status === 'failed' ? 'bg-red-50 text-red-700' : 'bg-yellow-50'
                ].join(' ')}>{a.status}</span>
                <span className="text-muted-foreground">{a.created_at?.slice(0, 16).replace('T', ' ')}</span>
              </div>
            ))}
            {cItems.length === 0 && <p className="text-xs text-muted-foreground">Нет действий</p>}
          </div>
        </div>

      </main>
    </div>
  )
}
