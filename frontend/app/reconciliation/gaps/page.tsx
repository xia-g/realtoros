'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'
export default function ReconGapsPage() {
  const [rid,setRid]=useState('')
  const {data:runs}=useQuery({queryKey:['recon-runs-list2'],queryFn:()=>api.get<any>(endpoints.reconciliationRuns+'?limit=5')})
  const runId=rid||((runs as any)?.items?.[0]?.id||'')
  const {data:gaps}=useQuery({queryKey:['recon-gaps',runId],queryFn:()=>api.get<any>(endpoints.reconciliationGaps(runId)),enabled:!!runId})
  const items=(gaps as any)?.items||[]
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Расхождения</h1>
    <div className="flex gap-2 mb-4">{(runs as any)?.items?.slice(0,5).map((r:any)=>(
      <button key={r.id} onClick={()=>setRid(r.id)} className={['text-xs px-3 py-1.5 rounded-lg border',runId===r.id?'bg-blue-50 border-blue-300':'bg-white'].join(' ')}>{r.id?.slice(0,8)}</button>
    ))}</div>
    <div className="bg-white rounded-xl border overflow-hidden">
      <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-2 font-medium">Важность</th><th className="text-left p-2 font-medium">Type</th><th className="text-left p-2 font-medium">Источник</th><th className="text-right p-2 font-medium">Amount</th><th className="text-left p-2 font-medium">Описание</th></tr></thead>
      <tbody>{items.map((g:any)=>(<tr key={g.id} className="border-b hover:bg-gray-50 text-xs">
        <td className="p-2"><span className={['px-1.5 py-0.5 rounded text-[10px]',g.severity==='critical'?'bg-red-100 text-red-700':g.severity==='warning'?'bg-yellow-100':'bg-blue-100'].join(' ')}>{g.severity}</span></td>
        <td className="p-2 text-muted-foreground">{g.gap_type}</td>
        <td className="p-2">{g.source_system}</td>
        <td className="p-2 font-mono text-right">{Number(g.amount).toLocaleString()}</td>
        <td className="p-2 max-w-xs truncate">{g.description}</td>
      </tr>))}</tbody></table>
    </div>
  </main></div>)
}