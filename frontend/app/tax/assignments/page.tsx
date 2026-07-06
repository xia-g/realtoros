'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
export default function TaxAssignmentsPage() {
  const {data} = useQuery({queryKey:['tax-assignments'],queryFn:()=>api.get<any>(endpoints.taxAssignments+'?limit=100')})
  const items=(data as any)?.items||[]
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Налоговые назначения</h1>
    <div className="grid grid-cols-3 gap-4 mb-6">
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.length}</p><p className="text-sm text-muted-foreground">Всего</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.filter((a:any)=>a.is_current).length}</p><p className="text-sm text-muted-foreground">Current</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.filter((a:any)=>a.excluded).length}</p><p className="text-sm text-muted-foreground">Исключено</p></div>
    </div>
    <div className="bg-white rounded-xl border overflow-hidden">
      <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-2 font-medium">Строка</th><th className="text-left p-2 font-medium">Регистр</th><th className="text-left p-2 font-medium">Тип</th><th className="text-left p-2 font-medium">Искл.</th><th className="text-left p-2 font-medium">Причина</th><th className="text-left p-2 font-medium">Current</th><th className="text-left p-2 font-medium">Вер.</th></tr></thead>
      <tbody>{items.map((a:any) => (
        <tr key={a.id} className="border-b hover:bg-gray-50 text-xs">
          <td className="p-2 font-mono">{a.ledger_line_id?.slice(0,8)}</td>
          <td className="p-2"><span className="px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 text-[10px]">{a.register_type}</span></td>
          <td className="p-2">{a.tax_treatment}</td>
          <td className="p-2">{a.excluded?<span className="text-red-600">×</span>:'✓'}</td>
          <td className="p-2 text-muted-foreground">{a.reason_code||'—'}</td>
          <td className="p-2">{a.is_current?<span className="text-green-600">✓</span>:<span className="text-xs text-muted-foreground">superseded</span>}</td>
          <td className="p-2 font-mono">{a.version}</td>
        </tr>
      ))}</tbody></table>
    </div>
  </main></div>)
}