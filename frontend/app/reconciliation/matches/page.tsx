'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'
export default function ReconMatchesPage() {
  const [rid,setRid]=useState('')
  const {data:runs}=useQuery({queryKey:['recon-runs-list'],queryFn:()=>api.get<any>(endpoints.reconciliationRuns+'?limit=5')})
  const runId=rid||((runs as any)?.items?.[0]?.id||'')
  const {data:matches}=useQuery({queryKey:['recon-matches',runId],queryFn:()=>api.get<any>(endpoints.reconciliationMatches(runId)),enabled:!!runId})
  const items=(matches as any)?.items||[]
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Сопоставления</h1>
    <div className="flex gap-2 mb-4">{(runs as any)?.items?.slice(0,5).map((r:any)=>(
      <button key={r.id} onClick={()=>setRid(r.id)} className={['text-xs px-3 py-1.5 rounded-lg border',runId===r.id?'bg-blue-50 border-blue-300':'bg-white'].join(' ')}>{r.id?.slice(0,8)}</button>
    ))}</div>
    <div className="bg-white rounded-xl border overflow-hidden">
      <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-2 font-medium">Тип</th><th className="text-left p-2 font-medium">Уверенность</th><th className="text-left p-2 font-medium">Разница</th><th className="text-left p-2 font-medium">Правило</th><th className="text-left p-2 font-medium">Источник</th><th className="text-left p-2 font-medium">Цель</th></tr></thead>
      <tbody>{items.map((m:any)=>(<tr key={m.id} className="border-b hover:bg-gray-50 text-xs">
        <td className="p-2"><span className={['px-1.5 py-0.5 rounded text-[10px]',m.match_type==='exact'?'bg-green-50 text-green-700':m.match_type==='fuzzy'?'bg-yellow-50':'bg-gray-100'].join(' ')}>{m.match_type}</span></td>
        <td className="p-2 font-mono">{(Number(m.confidence_score)*100).toFixed(0)}%</td>
        <td className="p-2 font-mono">{Number(m.amount_delta).toFixed(2)}</td>
        <td className="p-2 text-muted-foreground">{m.matching_rule}</td>
        <td className="p-2 text-[10px] font-mono">{m.source_item_id?.slice(0,8)}</td>
        <td className="p-2 text-[10px] font-mono">{m.target_item_id?.slice(0,8)||'—'}</td>
      </tr>))}</tbody></table>
    </div>
  </main></div>)
}