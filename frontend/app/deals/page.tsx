'use client'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'

export default function DealsPage() {
  const { data } = useQuery({
    queryKey: ['deals'],
    queryFn: () => api.get(endpoints.deals),
  })

  const deals = Array.isArray(data) ? data : (data as any)?.items || []

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Deals</h1>
          <Link href="/deals/new" className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm">
            New Deal
          </Link>
        </div>
        <div className="bg-white rounded-xl border">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50">
              <tr>
                <th className="text-left p-3 font-medium">ID</th>
                <th className="text-left p-3 font-medium">Type</th>
                <th className="text-left p-3 font-medium">Stage</th>
                <th className="text-left p-3 font-medium">Status</th>
                <th className="text-left p-3 font-medium">Client</th>
              </tr>
            </thead>
            <tbody>
              {deals.map((deal: any) => (
                <tr key={deal.id} className="border-b hover:bg-gray-50">
                  <td className="p-3">
                    <Link href={'/deals/' + deal.id} className="text-brand-600 hover:underline font-medium">
                      {deal.id?.slice(0, 8) || '—'}
                    </Link>
                  </td>
                  <td className="p-3">{deal.deal_type || deal.type || '—'}</td>
                  <td className="p-3">{deal.stage || '—'}</td>
                  <td className="p-3">{deal.status || '—'}</td>
                  <td className="p-3">{deal.client?.full_name || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  )
}
