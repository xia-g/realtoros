'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'
import { toast } from 'sonner'

const REGIME_OPTIONS = [
  { value: 'usn_income', label: 'УСН «Доходы»' },
  { value: 'usn_income_expense', label: 'УСН «Доходы минус Расходы»' },
  { value: 'osno', label: 'ОСНО (общая система)' },
  { value: 'psn', label: 'Патент (ПСН)' },
]

// Совместимые режимы (какие можно выбирать вместе)
const COMPATIBLE: Record<string, string[]> = {
  usn_income: ['psn'],
  usn_income_expense: ['psn'],
  psn: ['usn_income', 'usn_income_expense'],
  osno: [],
}

const defaultCompany = {
  name: '', inn: '', kpp: '', ogrn: '', legal_address: '', actual_address: '',
  okved: '', bank_name: '', bank_bik: '', bank_account: '',
  phone: '', email: '', ceo_name: '', ceo_position: '',
  tax_regime: 'usn_income',
  tax_regime_extra: '',
}

export default function CompaniesPage() {
  const queryClient = useQueryClient()
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({ ...defaultCompany })

  const { data, isLoading } = useQuery({
    queryKey: ['companies'],
    queryFn: () => api.get<any>(endpoints.companies),
  })
  const companies = (data as any)?.companies || []

  const saveMutation = useMutation({
    mutationFn: async (body: any) => {
      if (editId) {
        return api.put('/api/v1/companies/' + editId, body)
      } else {
        return api.post('/api/v1/companies', body)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['companies'] })
      toast.success(editId ? 'Компания обновлена' : 'Компания создана')
      setEditId(null); setForm({ ...defaultCompany })
    },
    onError: (e: any) => toast.error(e.message),
  })

  const loadCompany = async (id: string) => {
    try {
      const r = await api.get<any>(endpoints.companies + '/' + id)
      let regime = r.tax_regime || r.regime_type || 'usn_income'
      // Parse combined regimes (e.g. "usn_income+psn")
      let main = regime
      let extra = ''
      if (regime.includes('+')) {
        const parts = regime.split('+')
        main = parts[0]
        extra = parts.slice(1).join('+')
      }
      setForm({
        name: r.name || '', inn: r.inn || '', kpp: r.kpp || '', ogrn: r.ogrn || '',
        legal_address: r.legal_address || '', actual_address: r.actual_address || '',
        okved: r.okved || '', bank_name: r.bank_name || '', bank_bik: r.bank_bik || '',
        bank_account: r.bank_account || '', phone: r.phone || '', email: r.email || '',
        ceo_name: r.ceo_name || '', ceo_position: r.ceo_position || '',
        tax_regime: main,
        tax_regime_extra: extra,
      })
      setEditId(id)
    } catch (e: any) { toast.error(e.message) }
  }

  const newCompany = () => { setEditId(null); setForm({ ...defaultCompany }) }

  const set = (k: string) => (e: any) => setForm(f => ({ ...f, [k]: e.target.value }))

  // Get label for regime value (handles combined like "usn_income+psn")
  const regimeLabel = (v: string) => {
    if (!v) return '—'
    const parts = v.split('+')
    return parts.map(p => REGIME_OPTIONS.find(r => r.value === p)?.label || p).join(' + ')
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Компании</h1>
          <button onClick={newCompany} className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm">+ Новая</button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Список компаний */}
          <div className="bg-white rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="border-b bg-gray-50">
                <th className="text-left p-3 font-medium">Наименование</th>
                <th className="text-left p-3 font-medium">ИНН</th>
                <th className="text-left p-3 font-medium">Режим</th>
                <th className="text-left p-3 font-medium">Руководитель</th>
              </tr></thead>
              <tbody>
                {companies.map((c: any) => (
                  <tr key={c.id} onClick={() => loadCompany(c.id)}
                    className={['border-b hover:bg-gray-50 cursor-pointer text-sm',
                      editId === c.id ? 'bg-blue-50' : ''].join(' ')}>
                    <td className="p-3 font-medium">{c.name || '—'}</td>
                    <td className="p-3 font-mono text-xs">{c.inn || '—'}</td>
                    <td className="p-3 text-xs">
                      <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-[10px]">
                        {regimeLabel(c.tax_regime || c.regime_type) || '—'}
                      </span>
                    </td>
                    <td className="p-3 text-xs">{c.ceo_name || '—'}</td>
                  </tr>
                ))}
                {companies.length === 0 && !isLoading && (
                  <tr><td colSpan={4} className="p-6 text-center text-sm text-muted-foreground">Нет компаний</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Форма редактирования */}
          <div className="bg-white rounded-xl border p-6">
            <h3 className="font-semibold mb-4">{editId ? 'Редактировать компанию' : 'Новая компания'}</h3>
            <div className="grid grid-cols-2 gap-4">
              <Input label="Наименование" value={form.name} onChange={set('name')} />

              {/* Режим налогообложения — выпадающий список + доп. режим */}
              <RegimeSelect
                label="Режим налогообложения"
                value={form.tax_regime}
                extra={form.tax_regime_extra}
                onMain={(v) => {
                  setForm(f => ({ ...f, tax_regime: v }))
                  // Clear extra if new main doesn't support it
                  if (!COMPATIBLE[v]?.includes(form.tax_regime_extra)) {
                    setForm(f => ({ ...f, tax_regime: v, tax_regime_extra: '' }))
                  }
                }}
                onExtra={(v) => setForm(f => ({ ...f, tax_regime_extra: v }))}
              />

              <Input label="ИНН" value={form.inn} onChange={set('inn')} maxLength={12} />
              <Input label="КПП" value={form.kpp} onChange={set('kpp')} maxLength={9} />
              <Input label="ОГРН" value={form.ogrn} onChange={set('ogrn')} maxLength={15} />
              <Input label="ОКВЭД" value={form.okved} onChange={set('okved')} />
              <div className="col-span-2">
                <Input label="Юридический адрес" value={form.legal_address} onChange={set('legal_address')} />
              </div>
              <div className="col-span-2">
                <Input label="Фактический адрес" value={form.actual_address} onChange={set('actual_address')} />
              </div>
              <h4 className="col-span-2 font-medium text-sm text-muted-foreground border-t pt-3 mt-1">Банковские реквизиты</h4>
              <Input label="Банк" value={form.bank_name} onChange={set('bank_name')} />
              <Input label="БИК" value={form.bank_bik} onChange={set('bank_bik')} maxLength={9} />
              <div className="col-span-2">
                <Input label="Расчётный счёт" value={form.bank_account} onChange={set('bank_account')} />
              </div>
              <h4 className="col-span-2 font-medium text-sm text-muted-foreground border-t pt-3 mt-1">Контакты</h4>
              <Input label="Телефон" value={form.phone} onChange={set('phone')} />
              <Input label="Email" value={form.email} onChange={set('email')} />
              <h4 className="col-span-2 font-medium text-sm text-muted-foreground border-t pt-3 mt-1">Руководитель</h4>
              <Input label="ФИО" value={form.ceo_name} onChange={set('ceo_name')} />
              <Input label="Должность" value={form.ceo_position} onChange={set('ceo_position')} />
            </div>
            <div className="flex gap-2 mt-6">
              <button onClick={() => saveMutation.mutate(form)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">
                {editId ? 'Сохранить' : 'Создать'}
              </button>
              {editId && (
                <button onClick={newCompany} className="px-4 py-2 border rounded-lg text-sm">Отмена</button>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

// ── Input ──
function Input({ label, value, onChange, maxLength }: { label: string; value: string; onChange: (e: any) => void; maxLength?: number }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-muted-foreground">{label}</label>
      <input value={value} onChange={onChange} maxLength={maxLength}
        className="border rounded-lg px-3 py-2 text-sm w-full" />
    </div>
  )
}

// ── RegimeSelect — выпадающий список + дополнительный режим ──
function RegimeSelect({
  label, value, extra, onMain, onExtra
}: {
  label: string
  value: string
  extra: string
  onMain: (v: string) => void
  onExtra: (v: string) => void
}) {
  const compatOptions = COMPATIBLE[value] || []

  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-muted-foreground">{label}</label>

      {/* Основной режим */}
      <select value={value} onChange={(e) => onMain(e.target.value)}
        className="border rounded-lg px-3 py-2 text-sm w-full bg-white">
        {REGIME_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>

      {/* Дополнительный режим (если совместим) */}
      {compatOptions.length > 0 && (
        <div className="mt-1">
          <label className="text-[10px] text-muted-foreground">+ совмещённый режим (необязательно)</label>
          <select value={extra} onChange={(e) => onExtra(e.target.value)}
            className="border rounded-lg px-3 py-1.5 text-xs w-full bg-white mt-0.5">
            <option value="">— не выбран</option>
            {compatOptions.map((v) => {
              const opt = REGIME_OPTIONS.find(r => r.value === v)
              return opt ? <option key={v} value={v}>{opt.label}</option> : null
            })}
          </select>
          {extra && (
            <p className="text-[10px] text-green-600 mt-0.5">
              + {REGIME_OPTIONS.find(r => r.value === extra)?.label}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
