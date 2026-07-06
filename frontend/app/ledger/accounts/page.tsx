'use client'
import { useQuery } from '@tanstack/react-query'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'
export default function AccountsPage() {
  const { data } = useQuery({ queryKey: ['ledger-accounts'], queryFn: () => api.get<any>(endpoints.ledgerAccounts) })
  const accounts = (data as any)?.accounts || []
  return (
    <div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
      <h1 className="text-2xl font-bold mb-6">План счетов</h1>
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm"><thead><tr className="border-b bg-gray-50"><th className="text-left p-3 font-medium">Код</th><th className="text-left p-3 font-medium">Наименование</th><th className="text-left p-3 font-medium">Тип</th></tr></thead>
        <tbody>{accounts.map((a:any) => (
          <tr key={a.code} className="border-b hover:bg-gray-50">
            <td className="p-3 font-mono font-medium">{a.code}</td>
            <td className="p-3">{a.name}</td>
            <td className="p-3"><span className="px-2 py-0.5 rounded bg-gray-100 text-xs">{a.type}</span></td>
          </tr>
        ))}</tbody></table>
      </div>
    </main></div>
  )
}