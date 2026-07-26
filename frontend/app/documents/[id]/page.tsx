'use client'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'
import { useState } from 'react'

// ─── Formatters ────────────────────────────────────────────

function money(n: number | null | undefined): string {
  if (n == null) return '—'
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(n)
}

function pct(n: number | null | undefined): string {
  if (n == null) return '—'
  return (n * 100).toFixed(0) + '%'
}

// ─── Section Component ─────────────────────────────────────

function Section({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="border rounded-xl bg-white overflow-hidden">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 w-full p-4 text-left font-semibold text-sm hover:bg-gray-50 transition-colors">
        <span className="text-lg">{icon}</span>
        <span>{title}</span>
        <span className="ml-auto text-gray-400">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="px-4 pb-4 space-y-2 text-sm">{children}</div>}
    </div>
  )
}

function Field({ label, value, confidence }: { label: string; value: React.ReactNode; confidence?: number | null }) {
  return (
    <div className="flex items-start justify-between py-1 border-b border-gray-50 last:border-0">
      <span className="text-gray-500 shrink-0 min-w-[140px]">{label}</span>
      <span className="font-medium text-right">{value ?? <span className="text-red-400">—</span>}</span>
      {confidence != null && (
        <span className="text-xs text-gray-400 ml-2 shrink-0 w-8 text-right">{pct(confidence)}</span>
      )}
    </div>
  )
}

// ─── Main Page ─────────────────────────────────────────────

export default function DocumentProfilePage() {
  const params = useParams()
  const docId = params.id as string
  const [showOcr, setShowOcr] = useState(false)

  const { data: docData, isLoading, error } = useQuery({
    queryKey: ['document', docId],
    queryFn: () => api.get(endpoints.document(docId)),
  })
  const doc = docData as any

  // Fetch document lifecycle status from document_intake table
  const { data: lifecycleStatus } = useQuery<{status: string; allowed_transitions: string[]} | null>({
    queryKey: ['document-lifecycle', docId],
    queryFn: async (): Promise<{status: string; allowed_transitions: string[]} | null> => {
      try {
        const res = await api.get(endpoints.documentStatus(docId));
        return res as {status: string; allowed_transitions: string[]};
      } catch {
        return null;
      }
    },
    retry: 1,
  })

  if (isLoading) return (
    <div className="flex h-screen"><Sidebar /><main className="flex-1 p-6"><div className="animate-pulse space-y-4"><div className="h-8 bg-gray-200 rounded w-64"/><div className="h-40 bg-gray-100 rounded"/><div className="h-40 bg-gray-100 rounded"/></div></main></div>
  )

  if (error || !doc) return (
    <div className="flex h-screen"><Sidebar /><main className="flex-1 p-6"><p className="text-red-500">Документ не найден</p></main></div>
  )

  const d = doc as any
  const profile = d.profile?.profile || d.profile || {}
  const sections = profile.sections || {}
  const meta = profile.metadata || {}
  const warnings = meta.warnings || []
  const fieldConf = meta.confidence_per_field || {}

  const docTypeLabel = d.profile?.document_type || profile.document_type || '—'
  const getP = (s: string, f: string) => {
    return sections[s]?.[f] ?? null
  }
  const getS = (s: string, f: string) => {
    return (sections[s] && typeof sections[s] === 'object' && f in sections[s]) ? sections[s][f] : null
  }

  // ── Document type label ──
  const docTypeLabels: Record<string,string> = {
    contract: 'Договор купли-продажи недвижимости',
    invoice: 'Счёт на оплату',
    act: 'Акт выполненных работ',
    bank_statement: 'Выписка банка',
    receipt: 'Квитанция',
    passport: 'Паспорт',
    power_of_attorney: 'Доверенность',
  }

  const ident = sections.identification || {}
  const parties = sections.parties || {}
  const ft = sections.financial_terms || {}
  const prop = sections.property || {}
  const dates = sections.dates || {}
  const refs = sections.references || {}

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-6">

          {/* ── Header ── */}
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                <Link href="/documents" className="hover:text-brand-600">&larr; Документы</Link>
              </div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                📄 {docTypeLabels[docTypeLabel] || docTypeLabel}
              </h1>
              <div className="flex items-center gap-3 mt-1 text-sm">
                <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs font-medium">
                  {doc.status === 'ANALYZED' ? '✅ Проанализирован' : doc.status}
                </span>
                {lifecycleStatus && (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    lifecycleStatus.status === 'READY' ? 'bg-blue-100 text-blue-700' :
                    lifecycleStatus.status === 'ANALYZED' ? 'bg-purple-100 text-purple-700' :
                    lifecycleStatus.status === 'PROCESSING' ? 'bg-yellow-100 text-yellow-700' :
                    lifecycleStatus.status === 'ROUTED' ? 'bg-indigo-100 text-indigo-700' :
                    lifecycleStatus.status === 'ARCHIVED' ? 'bg-gray-100 text-gray-700' :
                    'bg-gray-100 text-gray-500'
                  }`}>
                    Lifecycle: {lifecycleStatus.status}
                    {lifecycleStatus.allowed_transitions?.length > 0 && (
                      <span className="ml-1 text-[10px] opacity-70">
                        → {lifecycleStatus.allowed_transitions.join(', ')}
                      </span>
                    )}
                  </span>
                )}
                <span className="text-gray-400">
                  Уверенность классификации: {pct(doc.profile?.classification_confidence || profile.confidence)}
                </span>
              </div>
            </div>
            <Link href={`/imports/documents`} className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700 transition-colors">
              Загрузить документ
            </Link>
          </div>

          {/* ── Что система поняла (Summary) ── */}
          <div className="bg-gradient-to-br from-brand-50 to-white border border-brand-100 rounded-xl p-4">
            <h2 className="text-sm font-semibold text-brand-700 mb-3">🔍 Что система поняла</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
              {parties?.buyer?.name && <div className="flex items-center gap-2"><span className="text-gray-500">👤</span> Покупатель: <strong>{parties.buyer.name}</strong></div>}
              {parties?.seller?.name && <div className="flex items-center gap-2"><span className="text-gray-500">🏛</span> Продавец: <strong>{parties.seller.name}</strong></div>}
              {prop?.cadastral_number && <div className="flex items-center gap-2"><span className="text-gray-500">📍</span> Кадастровый номер: <strong>{prop.cadastral_number}</strong></div>}
              {prop?.area_sqm && <div className="flex items-center gap-2"><span className="text-gray-500">📐</span> Площадь: <strong>{prop.area_sqm} м²</strong></div>}
              {ft?.total_price?.value != null && <div className="flex items-center gap-2"><span className="text-gray-500">💰</span> Стоимость: <strong>{money(ft.total_price.value)}</strong></div>}
            </div>
          </div>

          {/* ── Sections ── */}
          <div className="space-y-3">

            {/* Identification */}
            <Section title="Документ" icon="📋">
              <Field label="Номер договора" value={ident.contract_number} confidence={fieldConf.contract_number} />
              <Field label="Дата договора" value={ident.contract_date} confidence={fieldConf.contract_date} />
              <Field label="Место подписания" value={ident.place_of_signing} />
            </Section>

            {/* Parties */}
            <Section title="Стороны" icon="👥">
              {parties.seller && <>
                <div className="font-medium text-gray-700 text-xs uppercase tracking-wider mt-1 mb-1">Продавец</div>
                <Field label="Наименование" value={parties.seller.name} confidence={fieldConf['seller.name']} />
                <Field label="ИНН" value={parties.seller.inn} confidence={fieldConf['seller.inn']} />
                <Field label="КПП" value={parties.seller.kpp} confidence={fieldConf['seller.kpp']} />
                <Field label="Тип" value={parties.seller.type === 'legal' ? 'Юридическое лицо' : parties.seller.type} />
              </>}
              {parties.buyer && <>
                <div className="font-medium text-gray-700 text-xs uppercase tracking-wider mt-3 mb-1">Покупатель</div>
                <Field label="Наименование" value={parties.buyer.name} confidence={fieldConf['buyer.name']} />
                <Field label="ИНН" value={parties.buyer.inn} />
                <Field label="Тип" value={parties.buyer.type === 'individual' ? 'Физическое лицо' : parties.buyer.type} />
              </>}
            </Section>

            {/* Financial Terms */}
            {ft.total_price?.value != null && (
              <Section title="Финансовые условия" icon="💰">
                <Field label="Стоимость объекта" value={money(ft.total_price.value)} confidence={fieldConf['financial.total_price']} />
                <Field label="НДС" value={money(ft.vat_amount?.value)} confidence={fieldConf['financial.vat_amount']} />
                <Field label="Без НДС" value={money(ft.price_excluding_vat?.value)} />
                <Field label="Задаток" value={money(ft.deposit_amount?.value)} />
              </Section>
            )}

            {/* Property */}
            {prop.cadastral_number && (
              <Section title="Объект недвижимости" icon="🏢">
                <Field label="Кадастровый номер" value={prop.cadastral_number} confidence={fieldConf['property.cadastral_number']} />
                <Field label="Адрес" value={prop.address ? prop.address.replace(/, площадь.*/, '') : null} confidence={fieldConf['property.address']} />
                <Field label="Площадь" value={prop.area_sqm != null ? `${prop.area_sqm} м²` : null} confidence={fieldConf['property.area']} />
                <Field label="Этаж" value={prop.floor} />
                <Field label="Тип" value={prop.property_type ? prop.property_type.replace(/,.*/, '') : null} />
              </Section>
            )}

            {/* Dates */}
            {dates.signing_date && (
              <Section title="Даты" icon="📅">
                <Field label="Дата подписания" value={dates.signing_date} />
                <Field label="Срок оплаты" value={dates.payment_deadline} />
                <Field label="Срок передачи" value={dates.transfer_deadline} />
              </Section>
            )}

            {/* References */}
            {refs.tender_number && (
              <Section title="Ссылки" icon="🔗">
                <Field label="Номер извещения" value={refs.tender_number} />
                <Field label="Дата протокола" value={refs.protocol_date} />
              </Section>
            )}
          </div>

          {/* ── Warnings ── */}
          {warnings.length > 0 && (
            <div className="border border-amber-200 bg-amber-50 rounded-xl p-4">
              <h2 className="text-sm font-semibold text-amber-800 mb-2">⚠️ Требует внимания</h2>
              <ul className="space-y-1 text-sm text-amber-700">
                {warnings.map((w: any, i: number) => (
                  <li key={i}>{w.message || `${w.field}: ${w.code}`}</li>
                ))}
              </ul>
            </div>
          )}

          {/* ── Related Objects ── */}
          <div className="border rounded-xl bg-white p-4">
            <h2 className="text-sm font-semibold mb-3">🔗 Связанные объекты</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              <div className="p-3 bg-gray-50 rounded-lg">
                <div className="text-gray-500 text-xs">Сделка</div>
                <div className="font-medium">Создана</div>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <div className="text-gray-500 text-xs">Knowledge</div>
                <div className="font-medium">Revision доступна</div>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <div className="text-gray-500 text-xs">Routing</div>
                <div className="font-medium">{doc.pipeline_stage?.replace('_', ' ') || '—'}</div>
              </div>
            </div>
          </div>

          {/* ── OCR / JSON — under spoiler ── */}
          <div className="space-y-2">
            <button onClick={() => setShowOcr(!showOcr)} className="text-sm text-gray-500 hover:text-gray-700 transition-colors flex items-center gap-1">
              {showOcr ? '▼' : '▶'} Исходный текст
            </button>
            {showOcr && (
              <pre className="text-xs bg-gray-50 border rounded-lg p-4 overflow-auto max-h-96 text-gray-600 whitespace-pre-wrap break-all">
                {JSON.stringify(profile, null, 2)}
              </pre>
            )}
          </div>

        </div>
      </main>
    </div>
  )
}
