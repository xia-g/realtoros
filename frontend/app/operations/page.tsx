'use client'
import { useQuery } from '@tanstack/react-query'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'

export default function OperationsPage() {
  const { data: sla } = useQuery({ queryKey: ['sla'], queryFn: () => api.get(endpoints.operationsSla) })
  const { data: actions } = useQuery({ queryKey: ['actions'], queryFn: () => api.get(endpoints.operationsActions) })
  const { data: escalations } = useQuery({ queryKey: ['escalations'], queryFn: () => api.get(endpoints.operationsEscalations) })

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <h1 className="text-2xl font-bold mb-6">Operations Center</h1>
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="p-4 bg-white rounded-xl border">
            <h3 className="font-semibold mb-2">SLA Breaches</h3>
            <p className="text-2xl font-bold">{(Array.isArray(sla) ? sla : (sla as any)?.items || []).length}</p>
          </div>
          <div className="p-4 bg-white rounded-xl border">
            <h3 className="font-semibold mb-2">Pending Actions</h3>
            <p className="text-2xl font-bold">{(Array.isArray(actions) ? actions : (actions as any)?.items || []).length}</p>
          </div>
          <div className="p-4 bg-white rounded-xl border">
            <h3 className="font-semibold mb-2">Escalations</h3>
            <p className="text-2xl font-bold">{(Array.isArray(escalations) ? escalations : (escalations as any)?.items || []).length}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-white rounded-xl border">
            <h3 className="font-semibold mb-3">Recent Actions</h3>
            {(Array.isArray(actions) ? actions : []).slice(0, 5).map((a: any) => (
              <div key={a.id} className="flex justify-between py-1 text-sm border-b last:border-0">
                <span>{a.title || a.action || '—'}</span>
                <span className="text-muted-foreground">{a.status || '—'}</span>
              </div>
            ))}
          </div>
          <div className="p-4 bg-white rounded-xl border">
            <h3 className="font-semibold mb-3">Active Escalations</h3>
            {(Array.isArray(escalations) ? escalations : []).slice(0, 5).map((e: any) => (
              <div key={e.id} className="flex justify-between py-1 text-sm border-b last:border-0">
                <span>{e.reason || e.title || '—'}</span>
                <span className="text-red-600">{e.level ? 'Lvl ' + e.level : '—'}</span>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}