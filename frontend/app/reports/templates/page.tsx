'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
import { toast } from 'sonner'
export default function TemplatesPage() {
  const {data,refetch}=useQuery({queryKey:['report-templates'],queryFn:()=>api.get<any>(endpoints.reportTemplates)})
  const items=(data as any)?.items||[]
  const seed=async()=>{await api.post(endpoints.reportTemplatesSeed,{});toast.success('Seeded');refetch()}
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <div className="flex items-center justify-between mb-6">
      <h1 className="text-2xl font-bold">Шаблоны отчётов</h1>
      <button onClick={seed} className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg">Загрузить шаблоны</button>
    </div>
    {items.map((t:any)=>(<div key={t.id} className="bg-white rounded-xl border p-4 mb-4">
      <div className="flex items-center gap-3 mb-3">
        <h3 className="font-semibold">{t.name}</h3>
        <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-xs">{t.tax_regime}</span>
        <span className="text-xs text-muted-foreground">{t.code}</span>
      </div>
      <div className="space-y-1">{t.versions?.map((v:any)=>(<div key={v.id} className="flex items-center gap-3 text-sm py-1 border-b last:border-0">
        <span className="font-mono text-xs">v{v.version}</span>
        <span className={['px-1.5 py-0.5 rounded text-[10px]',v.status==='active'?'bg-green-50 text-green-700':v.status==='deprecated'?'bg-yellow-50':'bg-gray-100'].join(' ')}>{v.status}</span>
        <span className="text-xs text-muted-foreground">{v.effective_from}→{v.effective_to||'∞'}</span>
        <span className="text-[10px] text-muted-foreground">origin:{v.origin}</span>
      </div>))}</div>
    </div>))}
  </main></div>)
}