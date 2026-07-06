'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
export default function ImportHistoryPage() {
  const {data}=useQuery({queryKey:['events-imports'],queryFn:()=>api.get<any>(endpoints.accountingEvents+'?limit=100&source_system=bank_import')})
  const items=(data as any)?.items||[]
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">История импорта</h1>
    <div className="bg-white rounded-xl border overflow-hidden">
      <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-2 font-medium">Event</th><th className="text-left p-2 font-medium">Type</th><th className="text-left p-2 font-medium">Amount</th><th className="text-left p-2 font-medium">Date</th><th className="text-left p-2 font-medium">Источник</th></tr></thead>
      <tbody>{items.slice(0,50).map((e:any)=>(<tr key={e.id} className="border-b hover:bg-gray-50 text-xs">
        <td className="p-2 font-mono">{e.id?.slice(0,8)}</td>
        <td className="p-2">{e.event_type}</td>
        <td className="p-2 font-mono">{Number(e.amount||0).toLocaleString()}</td>
        <td className="p-2 text-muted-foreground">{e.event_date?.slice(0,10)}</td>
        <td className="p-2">{e.source_system||'—'}</td>
      </tr>))}</tbody></table>
    </div>
  </main></div>)
}