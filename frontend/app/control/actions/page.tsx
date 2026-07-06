'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
export default function ControlДействиеsPage() {
  const {data}=useQuery({queryKey:['ctrl-actions'],queryFn:()=>api.get<any>(endpoints.controlActions+'?limit=100')})
  const items=(data as any)?.items||[]
  const color=(s:string)=>({'completed':'bg-green-50 text-green-700','failed':'bg-red-50 text-red-700','pending':'bg-yellow-50','running':'bg-blue-50'})[s]||'bg-gray-100'
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Журнал действий</h1>
    <div className="grid grid-cols-4 gap-4 mb-6">
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.length}</p><p className="text-sm text-muted-foreground">Всего</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold text-green-600">{items.filter((a:any)=>a.status==='completed').length}</p><p className="text-sm text-muted-foreground">Выполнено</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold text-red-600">{items.filter((a:any)=>a.status==='failed').length}</p><p className="text-sm text-muted-foreground">Ошибок</p></div>
      <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold text-yellow-600">{items.filter((a:any)=>a.status==='pending').length}</p><p className="text-sm text-muted-foreground">Ожидают</p></div>
    </div>
    <div className="bg-white rounded-xl border overflow-hidden">
      <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-2 font-medium">Действие</th><th className="text-left p-2 font-medium">Система</th><th className="text-left p-2 font-medium">Исполнитель</th><th className="text-left p-2 font-medium">Роль</th><th className="text-left p-2 font-medium">Status</th><th className="text-left p-2 font-medium">Хеш Δ</th><th className="text-left p-2 font-medium">Когда</th></tr></thead>
      <tbody>{items.map((a:any)=>(<tr key={a.id} className="border-b hover:bg-gray-50 text-xs">
        <td className="p-2 font-medium">{a.action_type}</td>
        <td className="p-2"><span className="px-1.5 py-0.5 rounded text-[10px] bg-gray-100">{a.target_system}</span></td>
        <td className="p-2 font-mono">{a.actor_id?.slice(0,8)||'system'}</td>
        <td className="p-2 text-muted-foreground">{a.actor_role}</td>
        <td className="p-2"><span className={['px-1.5 py-0.5 rounded text-[10px]',color(a.status)].join(' ')}>{a.status}</span></td>
        <td className="p-2 font-mono text-[10px] text-muted-foreground">{a.state_before_hash?.slice(0,8)}→{a.state_after_hash?.slice(0,8)}</td>
        <td className="p-2 text-muted-foreground">{a.created_at?.slice(0,16).replace('T',' ')}</td>
      </tr>))}</tbody></table>
    </div>
  </main></div>)
}