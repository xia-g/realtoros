'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'; import { toast } from 'sonner'
export default function ApprovalPage() {
  const [actId,setActId]=useState('')
  const {data,refetch}=useQuery({queryKey:['ctrl-pending'],queryFn:()=>api.get<any>(endpoints.controlActions+'?status=pending&limit=50')})
  const items=(data as any)?.items||[]
  const approve=async(id:string)=>{try{await api.post(endpoints.controlApprove(id),{approved_by:'ui_user',role:'admin',reason:'Утвердитьd via UI'});toast.success('Утвердитьd');refetch()}catch(e:any){toast.error(e.message)}}
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Очередь согласования</h1>
    <div className="bg-white rounded-xl border overflow-hidden">
      <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-3 font-medium">Action</th><th className="text-left p-3 font-medium">System</th><th className="text-left p-3 font-medium">Actor</th><th className="text-left p-3 font-medium">When</th><th className="text-left p-3 font-medium">Утвердить</th></tr></thead>
      <tbody>{items.length===0?<tr><td colSpan={5} className="p-6 text-center text-sm text-muted-foreground">Нет ожидающих согласования</td></tr>
        :items.map((a:any)=>(<tr key={a.id} className="border-b hover:bg-gray-50 text-xs">
          <td className="p-3 font-medium">{a.action_type}</td>
          <td className="p-3"><span className="px-1.5 py-0.5 rounded text-[10px] bg-gray-100">{a.target_system}</span></td>
          <td className="p-3 font-mono">{a.actor_id?.slice(0,12)||'system'}</td>
          <td className="p-3 text-muted-foreground">{a.created_at?.slice(0,16).replace('T',' ')}</td>
          <td className="p-3"><button onClick={()=>approve(a.id)} className="px-3 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700">✓ Утвердить</button></td>
        </tr>))}</tbody></table>
    </div>
  </main></div>)
}