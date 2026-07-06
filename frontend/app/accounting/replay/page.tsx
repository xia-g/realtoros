'use client'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'
import { toast } from 'sonner'
export default function ReplayPage() {
  const [eventId, setEventId] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setРезультат] = useState<any>(null)
  const runReplay = async () => {
    if (!eventId) return; setRunning(true)
    try {
      const r = await api.post<any>(endpoints.accountingReplay, { event_id: eventId })
      setРезультат(r); toast.success('Replay completed')
    } catch (e: any) { toast.error(e.message) }
    finally { setRunning(false) }
  }
  return (
    <div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
      <h1 className="text-2xl font-bold mb-6">Консоль пересчёта</h1>
      <div className="bg-white rounded-xl border p-6 mb-6">
        <label className="block text-sm font-medium mb-2">Event ID</label>
        <div className="flex gap-2">
          <input value={eventId} onChange={e=>setEventId(e.target.value)} placeholder="UUID..." className="flex-1 border rounded-lg px-3 py-2 text-sm" />
          <button onClick={runReplay} disabled={running} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">{running ? 'Выполняется...' : 'Запустить пересчёт'}</button>
        </div>
      </div>
      {result && (
        <div className="bg-white rounded-xl border p-6">
          <h3 className="font-semibold mb-3">Результат</h3>
          <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-auto max-h-60">{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </main></div>
  )
}