'use client'
import { useQuery } from '@tanstack/react-query'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'
export default function DecisionsPage() {
  const { data } = useQuery({ queryKey: ['accounting-events'], queryFn: () => api.get<any>(endpoints.accountingEvents+'?limit=50') })
  const decisions = ((data as any)?.items||[]).filter((e:any)=>e.current_decision_id)
  return (
    <div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
      <h1 className="text-2xl font-bold mb-6">Журнал решений</h1>
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-3 font-medium">Событие</th><th className="text-left p-3 font-medium">Type</th><th className="text-left p-3 font-medium">Decision</th><th className="text-left p-3 font-medium">Причина</th><th className="text-left p-3 font-medium">Версия</th></tr></thead>
        <tbody>{decisions.map((e:any) => (
          <tr key={e.id} className="border-b hover:bg-gray-50">
            <td className="p-3 font-mono text-xs">{e.id?.slice(0,8)}</td>
            <td className="p-3">{e.event_type}</td>
            <td className="p-3"><span className={['px-2 py-0.5 rounded text-xs', e.decision_state==='included'?'bg-green-50 text-green-700':'bg-yellow-50 text-yellow-700'].join(' ')}>{e.decision_state}</span></td>
            <td className="p-3 text-xs text-muted-foreground max-w-xs truncate">{e.reason||'—'}</td>
            <td className="p-3 text-xs font-mono">{e.version||1}</td>
          </tr>
        ))}</tbody></table>
      </div>
    </main></div>
  )
}