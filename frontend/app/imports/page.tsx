'use client'
import { useState } from 'react'; import { Sidebar } from '@/components/layout/sidebar'; import { toast } from 'sonner'
import { api, endpoints } from '@lib/api-client'
export default function ImportsPage() {
  const [file, setFile] = useState<File|null>(null); const [companyId, setCompanyId] = useState('00000000-0000-0000-0000-000000000001');
  const [importing, setImporting] = useState(false); const [result, setResult] = useState<any>(null)
  const doImport = async () => {
    if (!file) return; setImporting(true)
    try {
      const fd = new FormData(); fd.append('file', file); fd.append('company_id', companyId)
      // Use standard fetch for multipart
      const token = JSON.parse(localStorage.getItem('realtor-auth')||'{}')?.state?.token
      const r = await fetch('http://localhost:8000/upload/bank', { method:'POST', headers: token?{Authorization:'Bearer '+token}:{}, body:fd })
      const data = await r.json()
      setResult(data); toast.success(data.events_created + ' events created')
    } catch(e:any) { toast.error(e.message) }
    finally { setImporting(false) }
  }
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Импорт банка</h1>
    <div className="bg-white rounded-xl border p-6 mb-6">
      <label className="block text-sm font-medium mb-2">Bank File (CSV, XLSX, MT940, CAMT.053)</label>
      <input type="file" onChange={e=>setFile(e.target.files?.[0]||null)} className="block w-full text-sm border rounded-lg p-2 mb-4" />
      <label className="block text-sm font-medium mb-2">Company ID</label>
      <input value={companyId} onChange={e=>setCompanyId(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm mb-4" />
      <button onClick={doImport} disabled={importing} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">{importing?'Импорт...':'Импортировать файл'}</button>
    </div>
    {result && <div className="bg-white rounded-xl border p-6"><pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-auto">{JSON.stringify(result,null,2)}</pre></div>}
  </main></div>)
}