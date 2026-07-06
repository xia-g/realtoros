'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'
export default function ReportsPage() {
  const [rid,setRid]=useState('')
  const {data}=useQuery({queryKey:['reports'],queryFn:()=>api.get<any>(endpoints.reports+'?limit=50')})
  const {data:det}=useQuery({queryKey:['report',rid],queryFn:()=>api.get<any>(endpoints.report(rid)),enabled:!!rid})
  const items=(data as any)?.items||[]
  const statusColor=(s:string)=>({'draft':'bg-gray-100','validated':'bg-blue-50 text-blue-700','ai_reviewed':'bg-purple-50 text-purple-700','accountant_approved':'bg-green-50 text-green-700','submitted':'bg-gray-200'})[s]||'bg-gray-100'
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Черновики отчётов</h1>
    <div className="grid grid-cols-4 gap-4 mb-6">
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.length}</p><p className="text-sm text-muted-foreground">Черновики</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.filter((r:any)=>r.status==='accountant_approved').length}</p><p className="text-sm text-muted-foreground">Утверждено</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.filter((r:any)=>r.status==='submitted').length}</p><p className="text-sm text-muted-foreground">Отправлено</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.reduce((s:number,r:any)=>s+Number(r.total_tax||0),0).toLocaleString()}</p><p className="text-sm text-muted-foreground">Всего налог</p></div>
    </div>
    <div className="grid grid-cols-2 gap-6">
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-2 font-medium">ID</th><th className="text-left p-2 font-medium">Status</th><th className="text-left p-2 font-medium">Доход</th><th className="text-left p-2 font-medium">Налог</th><th className="text-left p-2 font-medium">Hash</th></tr></thead>
        <tbody>{items.map((r:any)=>(<tr key={r.id} onClick={()=>setRid(r.id)} className={['border-b hover:bg-gray-50 cursor-pointer text-xs',rid===r.id?'bg-blue-50':''].join(' ')}>
          <td className="p-2 font-mono">{r.id?.slice(0,8)}</td>
          <td className="p-2"><span className={['px-1.5 py-0.5 rounded text-[10px]',statusColor(r.status)].join(' ')}>{r.status}</span></td>
          <td className="p-2 font-mono">{Number(r.total_income||0).toLocaleString()}</td>
          <td className="p-2 font-mono">{Number(r.total_tax||0).toLocaleString()}</td>
          <td className="p-2 text-[10px] font-mono text-muted-foreground">{r.report_hash?.slice(0,12)}</td>
        </tr>))}</tbody></table>
      </div>
      <div className="bg-white rounded-xl border p-4">
        <h3 className="font-semibold mb-3">Детали отчёта</h3>
        {det ? <div>
          <div className="flex gap-2 mb-3">{det.cells?.map((c:any)=><span key={c.cell_code} className="px-2 py-1 bg-gray-50 rounded text-xs">{c.cell_code}={c.value_numeric||c.value}</span>)}</div>
          <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-auto max-h-60">{JSON.stringify(det.report,null,2)}</pre>
        </div> : <p className="text-sm text-muted-foreground">Выберите отчёт</p>}
      </div>
    </div>
  </main></div>)
}