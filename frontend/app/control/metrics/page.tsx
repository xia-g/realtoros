'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
export default function MetricsPage() {
  const {data}=useQuery({queryKey:['ctrl-metrics'],queryFn:()=>api.get<any>(endpoints.controlMetrics+'?limit=50')})
  const items=(data as any)?.items||[]
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Метрики системы</h1>
    <div className="bg-white rounded-xl border overflow-hidden">
      <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-3 font-medium">Time</th><th className="text-left p-3 font-medium">Health</th><th className="text-left p-3 font-medium">Failed Jobs</th><th className="text-left p-3 font-medium">Locks</th><th className="text-left p-3 font-medium">Total Actions</th></tr></thead>
      <tbody>{items.map((m:any)=>(<tr key={m.id} className="border-b hover:bg-gray-50 text-xs">
        <td className="p-3 text-muted-foreground">{m.snapshot_time?.slice(0,19).replace('T',' ')}</td>
        <td className="p-3"><span className={['px-1.5 py-0.5 rounded text-[10px]',m.health_state==='healthy'?'bg-green-50 text-green-700':'bg-red-50 text-red-700'].join(' ')}>{m.health_state}</span></td>
        <td className="p-3 font-mono">{m.failed_jobs_count}</td>
        <td className="p-3 font-mono">{m.lock_count}</td>
        <td className="p-3 font-mono">{m.total_actions}</td>
      </tr>))}</tbody></table>
    </div>
  </main></div>)
}