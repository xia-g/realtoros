'use client'
import { useState, useEffect } from 'react'
import { Sidebar } from '@/components/layout/sidebar'
import { toast } from 'sonner'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.spcnn.ru'

const REGIME_LABELS: Record<string, string> = {
  usn_income: 'УСН Доходы 6%',
  usn_income_expense: 'УСН Доходы-Расходы 15%',
  osno: 'ОСНО (общая система)',
  psn: 'Патент (ПСН)',
  'usn_income_expense+psn': 'УСН Д-Р + Патент',
  'usn_income+psn': 'УСН Доходы + Патент',
}

const RISK_COLORS: Record<string, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  high: 'bg-red-100 text-red-800',
}

export default function TaxOptimizationPage() {
  const [companies, setCompanies] = useState<any[]>([])
  const [companyId, setCompanyId] = useState('')
  const [tips, setTips] = useState<any>(null)
  const [optimizing, setOptimizing] = useState(false)
  const [result, setResult] = useState<any>(null)

  // Property form
  const [form, setForm] = useState({
    property_price: '5000000',
    cadastral_value: '3000000',
    annual_income: '5000000',
    annual_expenses: '3500000',
    is_municipal: true,
  })

  const token = typeof window !== 'undefined'
    ? JSON.parse(localStorage.getItem('realtor-auth') || '{}')?.state?.token
    : null
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}

  useEffect(() => {
    fetch(`${API_URL}/api/v1/companies`, { headers })
      .then(r => r.json())
      .then(data => {
        setCompanies(data)
        if (data.length > 0) {
          setCompanyId(data[0].id)
          loadTips(data[0].id)
        }
      })
      .catch(() => {})
  }, [])

  const loadTips = async (cid: string) => {
    try {
      const r = await fetch(`${API_URL}/api/v1/tax/optimize/tips?company_id=${cid}`, { headers })
      setTips(await r.json())
    } catch {}
  }

  const analyzeProperty = async () => {
    if (!companyId) return
    setOptimizing(true)
    setResult(null)
    try {
      const r = await fetch(`${API_URL}/api/v1/tax/optimize/property`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          property_price: parseFloat(form.property_price),
          cadastral_value: parseFloat(form.cadastral_value),
          annual_income: parseFloat(form.annual_income),
          annual_expenses: parseFloat(form.annual_expenses),
          is_municipal: form.is_municipal,
        }),
      })
      if (!r.ok) throw new Error(await r.text())
      setResult(await r.json())
    } catch (e: any) {
      toast.error(e.message)
    } finally {
      setOptimizing(false)
    }
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto bg-gray-50">
        <h1 className="text-2xl font-bold mb-6">🧮 Налоговая оптимизация</h1>

        {/* Company Selector */}
        <div className="mb-6">
          <label className="block text-sm font-medium mb-1">Компания</label>
          <select
            value={companyId}
            onChange={e => { setCompanyId(e.target.value); loadTips(e.target.value) }}
            className="w-full max-w-md border rounded-lg px-3 py-2 text-sm bg-white"
          >
            {companies.map(c => (
              <option key={c.id} value={c.id}>{c.name} ({REGIME_LABELS[c.tax_regime] || c.tax_regime})</option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ── Property Purchase Analyzer ── */}
          <div className="space-y-6">
            <div className="bg-white rounded-xl border p-6">
              <h2 className="text-lg font-semibold mb-4">🏢 Анализ покупки помещения</h2>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Цена покупки (₽)</label>
                  <input type="number" value={form.property_price}
                    onChange={e => setForm({...form, property_price: e.target.value})}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Кадастровая стоимость (₽)</label>
                  <input type="number" value={form.cadastral_value}
                    onChange={e => setForm({...form, cadastral_value: e.target.value})}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Годовой доход (₽)</label>
                  <input type="number" value={form.annual_income}
                    onChange={e => setForm({...form, annual_income: e.target.value})}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Годовые расходы (₽)</label>
                  <input type="number" value={form.annual_expenses}
                    onChange={e => setForm({...form, annual_expenses: e.target.value})}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={form.is_municipal}
                    onChange={e => setForm({...form, is_municipal: e.target.checked})}
                    className="rounded" />
                  Покупка у муниципалитета (налоговый агент по НДС)
                </label>
                <button onClick={analyzeProperty} disabled={optimizing}
                  className="w-full px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium
                    disabled:opacity-50 hover:bg-blue-700 transition-colors">
                  {optimizing ? '⏳ Анализ...' : '🔍 Рассчитать сценарии'}
                </button>
              </div>
            </div>

            {/* Tips */}
            {tips && (
              <div className="bg-green-50 rounded-xl border border-green-200 p-6">
                <h2 className="text-lg font-semibold mb-3">💡 Советы по оптимизации</h2>
                <p className="text-xs text-green-700 mb-3">
                  {tips.company_name} · {REGIME_LABELS[tips.tax_regime] || tips.tax_regime}
                </p>
                <ul className="space-y-2">
                  {tips.tips?.map((tip: string, i: number) => (
                    <li key={i} className="text-sm text-green-800 bg-white/50 rounded-lg p-2">{tip}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* ── Results ── */}
          <div className="space-y-6">
            {result && (
              <>
                {/* Warnings */}
                {result.warnings?.length > 0 && (
                  <div className="bg-red-50 rounded-xl border border-red-200 p-4">
                    <h3 className="text-sm font-semibold text-red-800 mb-2">⚠️ Внимание</h3>
                    {result.warnings.map((w: string, i: number) => (
                      <p key={i} className="text-sm text-red-700">{w}</p>
                    ))}
                  </div>
                )}

                {/* Scenarios */}
                {result.scenarios?.map((s: any, i: number) => (
                  <div key={i} className={`bg-white rounded-xl border p-5 ${
                    result.recommended?.name === s.name ? 'ring-2 ring-green-400' : ''
                  }`}>
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-semibold text-sm flex-1">
                        {s.name}
                        {result.recommended?.name === s.name && (
                          <span className="ml-2 text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full">Рекомендуется</span>
                        )}
                      </h3>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${RISK_COLORS[s.risk_level] || 'bg-gray-100'}`}>
                        {s.risk_level === 'low' ? 'Низкий риск' : s.risk_level === 'medium' ? 'Средний риск' : 'Высокий риск'}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div className="bg-gray-50 p-2 rounded">
                        <p className="text-xs text-gray-500">Налог</p>
                        <p className="text-lg font-bold">{parseFloat(s.tax_amount).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 0 })}</p>
                      </div>
                      <div className="bg-gray-50 p-2 rounded">
                        <p className="text-xs text-gray-500">Эфф. ставка</p>
                        <p className="text-lg font-bold">{s.effective_rate}%</p>
                      </div>
                      {s.vat_impact && (
                        <div className="bg-gray-50 p-2 rounded">
                          <p className="text-xs text-gray-500">НДС</p>
                          <p className="text-lg font-bold">{parseFloat(s.vat_impact).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 0 })}</p>
                        </div>
                      )}
                    </div>

                    <p className="text-xs text-gray-500 mb-3 whitespace-pre-line">{s.description}</p>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <p className="text-green-600 font-medium mb-1">✅ Преимущества</p>
                        <ul className="space-y-1">
                          {s.pros?.map((p: string, j: number) => (
                            <li key={j} className="text-gray-600">{p}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <p className="text-red-600 font-medium mb-1">❌ Недостатки</p>
                        <ul className="space-y-1">
                          {s.cons?.map((c: string, j: number) => (
                            <li key={j} className="text-gray-600">{c}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                ))}

                {/* Recommendations */}
                <div className="bg-blue-50 rounded-xl border border-blue-200 p-5">
                  <h3 className="text-sm font-semibold text-blue-800 mb-3">📋 Рекомендации</h3>
                  <ul className="space-y-2">
                    {result.recommendations?.map((r: string, i: number) => (
                      <li key={i} className="text-sm text-blue-700 bg-white/50 rounded-lg p-2">{r}</li>
                    ))}
                  </ul>
                </div>

                {/* Deadlines */}
                <div className="bg-white rounded-xl border p-5">
                  <h3 className="text-sm font-semibold mb-3">📅 Ближайшие сроки</h3>
                  <div className="space-y-2">
                    {result.next_deadlines?.map((d: any, i: number) => (
                      <div key={i} className="flex items-center justify-between text-sm border-b pb-2 last:border-0">
                        <div>
                          <p className="font-medium">{d.title}</p>
                          <p className="text-xs text-gray-400">{d.description}</p>
                        </div>
                        <span className="text-xs font-medium text-red-600">
                          {new Date(d.deadline + 'T00:00:00').toLocaleDateString('ru-RU')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            {!result && !optimizing && (
              <div className="bg-gray-50 rounded-xl border border-dashed p-12 text-center">
                <p className="text-5xl mb-4">🧮</p>
                <p className="text-gray-500">Заполните параметры слева</p>
                <p className="text-sm text-gray-400 mt-1">и нажмите «Рассчитать сценарии»</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
