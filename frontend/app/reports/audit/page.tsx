'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'
export default function AuditPage() {
  const [rid,setRid]=useState(''); const {data}=useQuery({queryKey:['reports'],queryFn:()=>api.get<any>(endpoints.reports+'?limit=50')})
  const {data:audit}=useQuery({queryKey:['audit-log',rid],queryFn:()=>api.get<any>(endpoints.reportAuditLog(rid)),enabled:!!rid})
  const items=(data as any)?.items||[]
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Аудит отчётов</h1>
    <div className="grid grid-cols-2 gap-6">
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-2 font-medium">Отчёт</th><th className="text-left p-2 font-medium">Status</th><th className="text-left p-2 font-medium">Hash</th></tr></thead>
        <tbody>{items.map((r:any)=>(<tr key={r.id} onClick={()=>setRid(r.id)} className={['border-b hover:bg-gray-50 cursor-pointer text-xs',rid===r.id?'bg-blue-50':''].join(' ')}>
          <td className="p-2 font-mono">{r.id?.slice(0,8)}</td>
          <td className="p-2"><span className="px-1.5 py-0.5 rounded text-[10px] bg-gray-100">{r.status}</span></td>
          <td className="p-2 text-[10px] font-mono text-muted-foreground">{r.report_hash?.slice(0,12)}</td>
        </tr>))}</tbody></table>
      </div>
      <div className="bg-white rounded-xl border p-4">
        <h3 className="font-semibold mb-3">Результаты аудита</h3>
        {audit?.items ? audit.items.map((a:any)=>(<div key={a.id} className="mb-3 p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center gap-2 mb-2 text-xs"><span className="font-mono">model:{a.audit_model_version}</span><span className={['px-1.5 py-0.5 rounded text-[10px]',a.approved?'bg-green-50 text-green-700':'bg-yellow-50'].join(' ')}>risk={a.risk_score}</span></div>
          {a.findings?.map((f:any,i:number)=>(<div key={i} className="text-xs py-1 border-b last:border-0 flex items-start gap-2"><span className={['px-1 rounded text-[10px] font-medium',f.severity==='critical'?'bg-red-100 text-red-700':f.severity==='warning'?'bg-yellow-100':'bg-blue-100'].join(' ')}>{f.severity}</span><span>{f.description}</span></div>))}
        </div>)): <p className="text-sm text-muted-foreground">Выберите отчёт</p>}
      </div>
    </div>
  </main></div>)
}