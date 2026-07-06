'use client'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'

export default function DocumentsPage() {
  const { data } = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.get(endpoints.documents),
  })
  const docs = Array.isArray(data) ? data : (data as any)?.items || []

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Documents</h1>
          <Link href="/documents/upload" className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm">Upload</Link>
        </div>
        <div className="grid grid-cols-1 gap-4">
          {docs.map((doc: any) => (
            <div key={doc.id} className="p-4 bg-white rounded-xl border flex items-center justify-between">
              <div>
                <Link href={'/documents/' + doc.id} className="font-medium text-brand-600 hover:underline">
                  {doc.title || doc.filename || 'Document #' + doc.id.slice(0, 8)}
                </Link>
                <p className="text-sm text-muted-foreground">{doc.document_type || '—'} — {doc.status || '—'}</p>
              </div>
              <div className="flex items-center gap-2 text-xs">
                {doc.validation_status && (
                  <span className={'px-2 py-1 rounded-full ' + (
                    doc.validation_status === 'valid' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  )}>{doc.validation_status}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}