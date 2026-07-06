'use client'
import { useQuery } from '@tanstack/react-query'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'
export default function LedgerПроводкиPage() {
  const [entryId, setEntryId] = useState('')
  const { data, isLoading } = useQuery({ queryKey: ['ledger-entries'], queryFn: () => api.get<any>(endpoints.ledgerEntries+'?limit=50') })
  const { data: detail } = useQuery({ queryKey: ['ledger-entry', entryId], queryFn: () => api.get<any>(endpoints.ledgerEntry(entryId)), enabled: !!entryId })
  const items = (data as any)?.items || []
  return (
    <div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
      <h1 className="text-2xl font-bold mb-6">Главная книга</h1>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{isLoading ? '...' : (data as any)?.total || items.length}</p><p className="text-sm text-muted-foreground">Проводки</p></div>
        <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{items.reduce((s:number,i:any)=>s+(i.is_reversal?1:0),0)}</p><p className="text-sm text-muted-foreground">Сторно</p></div>
        <div className="p-4 bg-white rounded-xl border"><p className="text-2xl font-bold">{entryId ? '1' : '—'}</p><p className="text-sm text-muted-foreground">Выбрано</p></div>
      </div>
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-2 font-medium">ID</th><th className="text-left p-2 font-medium">Date</th><th className="text-left p-2 font-medium">Reversal</th><th className="text-left p-2 font-medium">Hash</th></tr></thead>
          <tbody>{items.map((e:any) => (
            <tr key={e.id} onClick={()=>setEntryId(e.id)} className={['border-b hover:bg-gray-50 cursor-pointer', entryId===e.id?'bg-blue-50':''].join(' ')}>
              <td className="p-2 font-mono text-xs">{e.id?.slice(0,8)}</td>
              <td className="p-2 text-xs">{e.entry_date?.slice(0,10)}</td>
              <td className="p-2">{e.is_reversal ? <span className="text-red-600 text-xs">YES</span> : <span className="text-xs text-muted-foreground">—</span>}</td>
              <td className="p-2 font-mono text-[10px] text-muted-foreground">{e.posting_hash?.slice(0,12)}</td>
            </tr>
          ))}</tbody></table>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <h3 className="font-semibold mb-3">Детали проводки</h3>
          {detail ? (
            <div>
              <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-auto max-h-80">{JSON.stringify(detail, null, 2)}</pre>
            </div>
          ) : <p className="text-sm text-muted-foreground">Нажмите проводку для просмотра + lines</p>}
        </div>
      </div>
    </main></div>
  )
}