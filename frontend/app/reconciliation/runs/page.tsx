'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
import { toast } from 'sonner'; import { useState } from 'react'
export default function ReconЗапускиPage() {
  const [rid,setRid]=useState('')
  const {data,refetch}=useQuery({queryKey:['recon-runs'],queryFn:()=>api.get<any>(endpoints.reconciliationRuns+'?limit=50')})
  const {data:det}=useQuery({queryKey:['recon-run',rid],queryFn:()=>api.get<any>(endpoints.reconciliationRunDetail(rid)),enabled:!!rid})
  const items=(data as any)?.items||[]
  const runNow=async()=>{await api.post(endpoints.reconciliationRun,{company_id:'00000000-0000-0000-0000-000000000001',period_from:'2026-01-01',period_to:'2026-12-31'});toast.success('Run created');refetch()}
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <div className="flex items-center justify-between mb-6"><h1 className="text-2xl font-bold">Сверка данных</h1><button onClick={runNow} className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg">Новый запуск</button></div>
    <div className="grid grid-cols-3 gap-4 mb-6">
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.length}</p><p className="text-sm text-muted-foreground">Запуски</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.filter((r:any)=>r.status==='matched_full').length}</p><p className="text-sm text-muted-foreground">Полное совпадение</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.reduce((s:number,r:any)=>s+(r.gaps_count||0),0)}</p><p className="text-sm text-muted-foreground">Всего расхождений</p></div>
    </div>
    <div className="grid grid-cols-2 gap-6">
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-2 font-medium">Run</th><th className="text-left p-2 font-medium">Status</th><th className="text-left p-2 font-medium">Matches</th><th className="text-left p-2 font-medium">Gaps</th><th className="text-left p-2 font-medium">Hash</th></tr></thead>
        <tbody>{items.map((r:any)=>(<tr key={r.id} onClick={()=>setRid(r.id)} className={['border-b hover:bg-gray-50 cursor-pointer text-xs',rid===r.id?'bg-blue-50':''].join(' ')}>
          <td className="p-2 font-mono">{r.id?.slice(0,8)}</td>
          <td className="p-2"><span className={['px-1.5 py-0.5 rounded text-[10px]',r.status==='matched_full'?'bg-green-50 text-green-700':'bg-yellow-50'].join(' ')}>{r.status}</span></td>
          <td className="p-2 font-mono">{r.matches_count}</td>
          <td className="p-2 font-mono text-red-600">{r.gaps_count}</td>
          <td className="p-2 text-[10px] font-mono text-muted-foreground">{r.run_hash?.slice(0,12)}</td>
        </tr>))}</tbody></table>
      </div>
      <div className="bg-white rounded-xl border p-4">
        <h3 className="font-semibold mb-3">Детали запуска</h3>
        {det ? <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-auto max-h-80">{JSON.stringify(det,null,2)}</pre>
        : <p className="text-sm text-muted-foreground">Выберите запуск</p>}
      </div>
    </div>
  </main></div>)
}