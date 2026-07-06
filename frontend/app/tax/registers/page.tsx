'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'
export default function TaxРегистрыPage() {
  const [selId, setSelId] = useState('')
  const { data } = useQuery({queryKey:['tax-registers'],queryFn:()=>api.get<any>(endpoints.taxRegisters+'?limit=50')})
  const {data:det} = useQuery({queryKey:['tax-register',selId],queryFn:()=>api.get<any>(endpoints.taxRegister(selId)),enabled:!!selId})
  const items=(data as any)?.items||[]
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Налоговые регистры</h1>
    <div className="grid grid-cols-4 gap-4 mb-6">
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.length}</p><p className="text-sm text-muted-foreground">Регистры</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.filter((r:any)=>r.is_current).length}</p><p className="text-sm text-muted-foreground">Текущие</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{det?.entries?.length||'—'}</p><p className="text-sm text-muted-foreground">Выбрано записей</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.reduce((s:number,r:any)=>s+Number(r.total_amount||0),0).toLocaleString()}</p><p className="text-sm text-muted-foreground">Общая сумма</p></div>
    </div>
    <div className="grid grid-cols-2 gap-6">
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-2 font-medium">Type</th><th className="text-left p-2 font-medium">Вер.</th><th className="text-left p-2 font-medium">Записи</th><th className="text-right p-2 font-medium">Сумма</th><th className="text-left p-2 font-medium">Текущие</th></tr></thead>
        <tbody>{items.map((r:any) => (
          <tr key={r.id} onClick={()=>setSelId(r.id)} className={['border-b hover:bg-gray-50 cursor-pointer',selId===r.id?'bg-blue-50':''].join(' ')}>
            <td className="p-2"><span className="px-2 py-0.5 rounded bg-purple-50 text-purple-700 text-xs">{r.register_type}</span></td>
            <td className="p-2 text-xs font-mono">v{r.register_version}</td>
            <td className="p-2 text-xs">{r.entry_count}</td>
            <td className="p-2 text-xs font-mono text-right">{Number(r.total_amount||0).toLocaleString()}</td>
            <td className="p-2">{r.is_current?<span className="text-green-600 text-xs">✓</span>:<span className="text-xs text-muted-foreground">—</span>}</td>
          </tr>
        ))}</tbody></table>
      </div>
      <div className="bg-white rounded-xl border p-4">
        <h3 className="font-semibold mb-3">Записи</h3>
        {det?.entries ? <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-auto max-h-80">{JSON.stringify(det.entries,null,2)}</pre>
        : <p className="text-sm text-muted-foreground">Выберите регистр</p>}
      </div>
    </div>
  </main></div>)
}