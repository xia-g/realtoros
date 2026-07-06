'use client'
import { useQuery } from '@tanstack/react-query'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'
export default function СобытиеsPage() {
  const [limit] = useState(25)
  const { data, isLoading } = useQuery({ queryKey: ['accounting-events', limit], queryFn: () => api.get<any>(endpoints.accountingEvents + '?limit=' + limit) })
  const items = (data as any)?.items || []
  const total = (data as any)?.total || 0
  return (
    <div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
      <h1 className="text-2xl font-bold mb-6">Журнал событий</h1>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{isLoading ? '...' : total}</p><p className="text-sm text-muted-foreground">Всего событий</p></div>
        <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.filter((e:any)=>e?.decision_state==='included').length}</p><p className="text-sm text-muted-foreground">Включено</p></div>
        <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.filter((e:any)=>e?.decision_state==='review_required').length}</p><p className="text-sm text-muted-foreground">Требуют проверки</p></div>
        <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.filter((e:any)=>e?.processing_state==='done').length}</p><p className="text-sm text-muted-foreground">Обработано</p></div>
      </div>
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-3 font-medium">Событие</th><th className="text-left p-3 font-medium">Тип</th><th className="text-left p-3 font-medium">Сумма</th><th className="text-left p-3 font-medium">Решение</th><th className="text-left p-3 font-medium">Статус</th><th className="text-left p-3 font-medium">Дата</th></tr></thead>
        <tbody>{items.map((e: any) => (
          <tr key={e.id} className="border-b hover:bg-gray-50"><td className="p-3 font-mono text-xs">{e.id?.slice(0,8)}</td>
          <td className="p-3"><span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-xs">{e.event_type}</span></td>
          <td className="p-3 font-mono">{Number(e.amount||0).toLocaleString()}</td>
          <td className="p-3"><span className={['px-2 py-0.5 rounded text-xs', e.decision_state==='included'?'bg-green-50 text-green-700':e.decision_state==='excluded'?'bg-red-50 text-red-700':'bg-yellow-50 text-yellow-700'].join(' ')}>{e.decision_state||'pending'}</span></td>
          <td className="p-3 text-xs">{e.processing_state}</td>
          <td className="p-3 text-xs text-muted-foreground">{e.event_date?.slice(0,10)}</td></tr>
        ))}</tbody></table>
      </div>
    </main></div>
  )
}