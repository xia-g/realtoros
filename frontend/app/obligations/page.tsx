'use client'
import { useState, useEffect } from 'react'
import { Sidebar } from '@/components/layout/sidebar'
import { toast } from 'sonner'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.spcnn.ru'
const OBLIGATION_TYPES: Record<string, string> = {
  vat_payable: 'НДС к уплате',
  vat_deduction: 'НДС к вычету',
  tax_usn: 'УСН налог',
  tax_property: 'Налог на имущество',
  tax_land: 'Земельный налог',
  insurance: 'Страховые взносы',
  salary_tax: 'НДФЛ',
  loan_payment: 'Платеж по кредиту',
  rent: 'Аренда',
  utility: 'Коммунальные',
  counterparty: 'Контрагенту',
  other: 'Прочее',
}
const STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: 'Ожидает', color: 'bg-yellow-100 text-yellow-800' },
  paid: { label: 'Оплачено', color: 'bg-green-100 text-green-800' },
  overdue: { label: 'Просрочено', color: 'bg-red-100 text-red-800' },
  cancelled: { label: 'Отменено', color: 'bg-gray-100 text-gray-500' },
}
const RECURRENCE: Record<string, string> = {
  one_time: 'Разовый',
  monthly: 'Ежемесячно',
  quarterly: 'Ежеквартально',
  yearly: 'Ежегодно',
}

export default function ObligationsPage() {
  const [obligations, setObligations] = useState<any[]>([])
  const [companies, setCompanies] = useState<any[]>([])
  const [filterType, setFilterType] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)

  // Form state
  const [form, setForm] = useState({
    company_id: '',
    obligation_type: 'vat_payable',
    title: '',
    description: '',
    amount: '',
    due_date: '',
    recurrence: 'one_time',
    reminder_days: 7,
    notes: '',
  })

  const token = typeof window !== 'undefined'
    ? JSON.parse(localStorage.getItem('realtor-auth') || '{}')?.state?.token
    : null
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}

  useEffect(() => { load(); fetchCompanies() }, [])

  const load = async () => {
    setLoading(true)
    try {
      let url = `${API_URL}/api/v1/obligations?limit=100`
      if (filterType) url += `&obligation_type=${filterType}`
      if (filterStatus) url += `&status=${filterStatus}`
      const r = await fetch(url, { headers })
      setObligations(await r.json())
    } catch { setObligations([]) }
    finally { setLoading(false) }
  }

  const fetchCompanies = async () => {
    try {
      const r = await fetch(`${API_URL}/api/v1/companies`, { headers })
      setCompanies(await r.json())
    } catch {}
  }

  useEffect(() => { load() }, [filterType, filterStatus])

  const createObligation = async () => {
    if (!form.company_id || !form.title || !form.amount || !form.due_date) {
      toast.error('Заполните обязательные поля')
      return
    }
    try {
      const r = await fetch(`${API_URL}/api/v1/obligations`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, amount: parseFloat(form.amount) }),
      })
      if (!r.ok) throw new Error(await r.text())
      toast.success('✅ Обязательство создано')
      setShowForm(false)
      setForm({ company_id: form.company_id, obligation_type: 'vat_payable', title: '', description: '', amount: '', due_date: '', recurrence: 'one_time', reminder_days: 7, notes: '' })
      load()
    } catch (e: any) { toast.error(e.message) }
  }

  const markPaid = async (id: string) => {
    try {
      const r = await fetch(`${API_URL}/api/v1/obligations/${id}`, {
        method: 'PATCH',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'paid', paid_date: new Date().toISOString().split('T')[0] }),
      })
      if (!r.ok) throw new Error(await r.text())
      toast.success('✅ Оплачено')
      load()
    } catch (e: any) { toast.error(e.message) }
  }

  const deleteObligation = async (id: string) => {
    try {
      await fetch(`${API_URL}/api/v1/obligations/${id}`, { method: 'DELETE', headers })
      toast.success('Удалено')
      load()
    } catch {}
  }

  // Group by month
  const grouped = obligations.reduce((acc: any, o: any) => {
    const month = o.due_date?.substring(0, 7) || 'unknown'
    if (!acc[month]) acc[month] = []
    acc[month].push(o)
    return acc
  }, {} as Record<string, any[]>)

  const months = Object.keys(grouped).sort()

  const totalPending = obligations.filter(o => o.status === 'pending').length
  const totalOverdue = obligations.filter(o => o.due_date < new Date().toISOString().split('T')[0] && o.status === 'pending').length
  const totalAmount = obligations
    .filter(o => o.status === 'pending')
    .reduce((s, o) => s + parseFloat(o.amount || 0), 0)

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto bg-gray-50">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">📅 Календарь обязательств</h1>
          <button onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
            + Добавить
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl border p-4">
            <p className="text-sm text-gray-500">Ожидают оплаты</p>
            <p className="text-2xl font-bold mt-1">{totalPending}</p>
          </div>
          <div className="bg-white rounded-xl border p-4">
            <p className="text-sm text-gray-500">Просрочено</p>
            <p className="text-2xl font-bold text-red-600 mt-1">{totalOverdue}</p>
          </div>
          <div className="bg-white rounded-xl border p-4">
            <p className="text-sm text-gray-500">Сумма к уплате</p>
            <p className="text-2xl font-bold mt-1">{totalAmount.toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 0 })}</p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mb-4">
          <select value={filterType} onChange={e => setFilterType(e.target.value)}
            className="border rounded-lg px-3 py-2 text-sm bg-white">
            <option value="">Все типы</option>
            {Object.entries(OBLIGATION_TYPES).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
            className="border rounded-lg px-3 py-2 text-sm bg-white">
            <option value="">Все статусы</option>
            <option value="pending">Ожидает</option>
            <option value="paid">Оплачено</option>
            <option value="overdue">Просрочено</option>
          </select>
        </div>

        {/* New Obligation Form */}
        {showForm && (
          <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={() => setShowForm(false)}>
            <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-auto" onClick={e => e.stopPropagation()}>
              <h2 className="text-lg font-semibold mb-4">Новое обязательство</h2>
              <div className="space-y-3">
                <select value={form.company_id} onChange={e => setForm({...form, company_id: e.target.value})}
                  className="w-full border rounded-lg px-3 py-2 text-sm">
                  <option value="">Выберите компанию</option>
                  {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <select value={form.obligation_type} onChange={e => setForm({...form, obligation_type: e.target.value})}
                  className="w-full border rounded-lg px-3 py-2 text-sm">
                  {Object.entries(OBLIGATION_TYPES).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <input value={form.title} onChange={e => setForm({...form, title: e.target.value})}
                  placeholder="Название (обязательно)" className="w-full border rounded-lg px-3 py-2 text-sm" />
                <input value={form.amount} onChange={e => setForm({...form, amount: e.target.value})}
                  type="number" placeholder="Сумма (обязательно)" className="w-full border rounded-lg px-3 py-2 text-sm" />
                <input value={form.due_date} onChange={e => setForm({...form, due_date: e.target.value})}
                  type="date" className="w-full border rounded-lg px-3 py-2 text-sm" />
                <select value={form.recurrence} onChange={e => setForm({...form, recurrence: e.target.value})}
                  className="w-full border rounded-lg px-3 py-2 text-sm">
                  {Object.entries(RECURRENCE).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <textarea value={form.notes} onChange={e => setForm({...form, notes: e.target.value})}
                  placeholder="Примечания" className="w-full border rounded-lg px-3 py-2 text-sm" rows={2} />
              </div>
              <div className="flex gap-3 mt-4">
                <button onClick={createObligation}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">Создать</button>
                <button onClick={() => setShowForm(false)}
                  className="px-4 py-2 border rounded-lg text-sm">Отмена</button>
              </div>
            </div>
          </div>
        )}

        {/* Obligations List */}
        {loading ? (
          <p className="text-center text-gray-400 py-12">Загрузка...</p>
        ) : obligations.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p className="text-4xl mb-3">📭</p>
            <p>Нет обязательств</p>
            <p className="text-sm mt-1">Нажмите «+ Добавить» чтобы создать первое</p>
          </div>
        ) : (
          <div className="space-y-4">
            {months.map(month => (
              <div key={month}>
                <h3 className="text-sm font-semibold text-gray-500 uppercase mb-2">
                  {new Date(month + '-01').toLocaleDateString('ru-RU', { year: 'numeric', month: 'long' })}
                </h3>
                <div className="space-y-2">
                  {grouped[month].map((o: any) => {
                    const st = o.status === 'pending' && o.due_date < new Date().toISOString().split('T')[0]
                      ? STATUS_MAP.overdue : STATUS_MAP[o.status] || STATUS_MAP.pending
                    return (
                      <div key={o.id} className="bg-white rounded-xl border p-4 flex items-center gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${st.color}`}>{st.label}</span>
                            <span className="text-xs text-gray-400">{OBLIGATION_TYPES[o.obligation_type] || o.obligation_type}</span>
                          </div>
                          <p className="font-medium mt-1">{o.title}</p>
                          <p className="text-xs text-gray-400 mt-0.5">
                            {o.company_name} · {RECURRENCE[o.recurrence] || o.recurrence}
                          </p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="text-lg font-bold">{parseFloat(o.amount).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 0 })}</p>
                          <p className="text-xs text-gray-400">до {new Date(o.due_date + 'T00:00:00').toLocaleDateString('ru-RU')}</p>
                        </div>
                        <div className="flex gap-1">
                          {o.status === 'pending' && (
                            <button onClick={() => markPaid(o.id)}
                              className="px-3 py-1.5 bg-green-600 text-white rounded text-xs hover:bg-green-700">✅ Опл.</button>
                          )}
                          <button onClick={() => deleteObligation(o.id)}
                            className="px-3 py-1.5 border rounded text-xs text-red-500 hover:bg-red-50">✕</button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
