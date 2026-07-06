'use client'
import { useQuery } from '@tanstack/react-query'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'
import { toast } from 'sonner'
export default function PeriodsPage() {
  const { data, refetch } = useQuery({ queryKey: ['tax-periods'], queryFn: () => api.get<any>(endpoints.taxPeriods) })
  const periods = (data as any)?.items || []
  const closePeriod = async (id: string) => {
    try {
      await api.post<any>(endpoints.taxPeriodClose, { tax_period_id: id })
      toast.success('Period closed'); refetch()
    } catch (e: any) { toast.error(e.message) }
  }
  return (
    <div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
      <h1 className="text-2xl font-bold mb-6">Налоговые периоды</h1>
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-3 font-medium">Period</th><th className="text-left p-3 font-medium">Диапазон</th><th className="text-left p-3 font-medium">Type</th><th className="text-left p-3 font-medium">Status</th><th className="text-left p-3 font-medium">Действия</th></tr></thead>
        <tbody>{periods.map((p:any) => (
          <tr key={p.id} className="border-b hover:bg-gray-50">
            <td className="p-3 font-mono text-xs">{p.id?.slice(0,8)}</td>
            <td className="p-3 text-xs">{p.date_from?.slice(0,10)} → {p.date_to?.slice(0,10)}</td>
            <td className="p-3 text-xs">{p.period_type||p.resolution}</td>
            <td className="p-3"><span className={['px-2 py-0.5 rounded text-xs', p.status==='open'?'bg-green-50 text-green-700':p.status==='closed'?'bg-gray-100 text-gray-600':'bg-yellow-50 text-yellow-700'].join(' ')}>{p.status}</span></td>
            <td className="p-3">{p.status==='open' && <button onClick={()=>closePeriod(p.id)} className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200">Закрыть</button>}</td>
          </tr>
        ))}</tbody></table>
      </div>
    </main></div>
  )
}