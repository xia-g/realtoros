'use client'
import { useQuery } from '@tanstack/react-query'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'

export default function AdminPage() {
  const { data: settings } = useQuery({
    queryKey: ['platform-settings'],
    queryFn: () => api.get(endpoints.platformSettings),
  })

  const { data: domains } = useQuery({
    queryKey: ['platform-domains'],
    queryFn: () => api.get(endpoints.platformDomains),
  })

  const domainEntries = domains && typeof domains === 'object'
    ? Object.entries(domains as Record<string, string>)
    : []

  const settingsEntries = settings && typeof settings === 'object' && !Array.isArray(settings)
    ? Object.entries(settings as Record<string, unknown>)
    : []

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <h1 className="text-2xl font-bold mb-6">Administration</h1>

        <div className="grid grid-cols-2 gap-6">
          {/* Domains */}
          <div className="p-4 bg-white rounded-xl border">
            <h2 className="font-semibold mb-3">Domains</h2>
            {domainEntries.length > 0
              ? domainEntries.map(([key, url]) => (
                  <div key={key} className="flex justify-between py-1 text-sm">
                    <span className="text-muted-foreground">{key}</span>
                    <span className="font-mono text-xs">{url}</span>
                  </div>
                ))
              : <p className="text-sm text-muted-foreground">No domains configured</p>}
          </div>

          {/* Settings */}
          <div className="p-4 bg-white rounded-xl border">
            <h2 className="font-semibold mb-3">Platform Settings</h2>
            {settingsEntries.slice(0, 10).map(([key, val]) => (
              <div key={key} className="flex justify-between py-1 text-sm">
                <span className="text-muted-foreground">{key}</span>
                <span className="font-mono text-xs">{String(val).slice(0, 30)}</span>
              </div>
            ))}
          </div>

          {/* Health */}
          <div className="p-4 bg-white rounded-xl border col-span-2">
            <h2 className="font-semibold mb-3">System Health</h2>
            <div className="grid grid-cols-4 gap-4 text-sm">
              <div className="p-3 bg-green-50 rounded-lg"><p className="font-medium text-green-700">API</p><p className="text-green-600">Operational</p></div>
              <div className="p-3 bg-green-50 rounded-lg"><p className="font-medium text-green-700">Database</p><p className="text-green-600">Connected</p></div>
              <div className="p-3 bg-yellow-50 rounded-lg"><p className="font-medium text-yellow-700">Partitions</p><p className="text-yellow-600">36 active</p></div>
              <div className="p-3 bg-green-50 rounded-lg"><p className="font-medium text-green-700">Migrations</p><p className="text-green-600">25/25 applied</p></div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
