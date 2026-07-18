'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
export default function SystemStatePage() {
  const {data}=useQuery({queryKey:['ctrl-state'],queryFn:()=>api.get<any>(endpoints.controlState)})
  const items=(data as any)?.items||[]
  const color=(s:string)=>({'healthy':'bg-green-100 text-green-700','degraded':'bg-yellow-100','replaying':'bg-blue-100','locked':'bg-red-100 text-red-700','error':'bg-red-100 text-red-700'})[s]||'bg-gray-100'
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Состояние системы</h1>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {['ledger','tax','reports','reconciliation','global'].map(sys=>{
        const st=items.find((s:any)=>s.subsystem===sys);
        return (<div key={sys} className="bg-white rounded-xl border p-4">
          <h3 className="font-semibold capitalize mb-2">{sys}</h3>
          {st?<div><span className={['px-2 py-1 rounded text-xs font-medium',color(st.status)].join(' ')}>{st.status}</span><p className="text-xs text-muted-foreground mt-2 font-mono">hash: {st.state_hash?.slice(0,16)}...</p></div>
          :<span className="text-xs text-muted-foreground">Не отслеживается</span>}
        </div>)
      })}
    </div>
  </main></div>)
}