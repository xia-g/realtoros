'use client'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'

export default function ClientsPage() {
  const { data } = useQuery({
    queryKey: ['clients'],
    queryFn: () => api.get(endpoints.clients),
  })
  const clients = Array.isArray(data) ? data : (data as any)?.items || []

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Clients</h1>
          <Link href="/clients/new" className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm">New Client</Link>
        </div>
        <div className="bg-white rounded-xl border">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50">
              <tr><th className="text-left p-3 font-medium">Name</th><th className="text-left p-3 font-medium">Phone</th><th className="text-left p-3 font-medium">Email</th><th className="text-left p-3 font-medium">Status</th></tr>
            </thead>
            <tbody>
              {clients.map((c: any) => (
                <tr key={c.id} className="border-b hover:bg-gray-50">
                  <td className="p-3"><Link href={'/clients/' + c.id} className="text-brand-600 hover:underline font-medium">{c.full_name || '—'}</Link></td>
                  <td className="p-3">{c.phone || '—'}</td>
                  <td className="p-3">{c.email || '—'}</td>
                  <td className="p-3">{c.status || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  )
}
