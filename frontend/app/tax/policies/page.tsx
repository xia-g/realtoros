'use client'
import { useQuery } from '@tanstack/react-query'; import { api, endpoints } from '@lib/api-client'; import { Sidebar } from '@/components/layout/sidebar'
export default function TaxPoliciesPage() {
  const {data} = useQuery({queryKey:['tax-policies'],queryFn:()=>api.get<any>(endpoints.taxPolicies)})
  const items=(data as any)?.items||[]
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">Налоговые политики</h1>
    {items.map((p:any) => (
      <div key={p.id} className="bg-white rounded-xl border p-4 mb-4">
        <div className="flex items-center gap-3 mb-3">
          <h3 className="font-semibold">{p.name}</h3>
          <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-xs">{p.tax_regime}</span>
          {p.is_active && <span className="px-2 py-0.5 rounded bg-green-50 text-green-700 text-xs">active</span>}
        </div>
        <div className="space-y-1">{p.versions?.map((v:any) => (
          <div key={v.id} className="flex items-center gap-3 text-sm py-1 border-b last:border-0">
            <span className="font-mono text-xs">v{v.version}</span>
            <span className="text-xs text-muted-foreground">{v.effective_from} → {v.effective_to||'∞'}</span>
            <span className={['px-1.5 py-0.5 rounded text-[10px]', v.is_active?'bg-green-50 text-green-700':'bg-gray-100'].join(' ')}>{v.status||(v.is_active?'active':'archive')}</span>
          </div>
        ))}</div>
      </div>
    ))}
  </main></div>)
}