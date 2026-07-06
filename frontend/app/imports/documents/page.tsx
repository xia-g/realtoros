'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Sidebar } from '@/components/layout/sidebar'
import { toast } from 'sonner'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.spcnn.ru'
const OCR_NODE_URL = process.env.NEXT_PUBLIC_OCR_NODE_URL || ''
const SUPPORTED = ['PDF', 'JPG', 'JPEG', 'PNG', 'ZIP', 'DOC', 'DOCX', 'XLS', 'XLSX', 'XML', 'TXT']

type Step = 'select' | 'upload' | 'ocr' | 'analyze' | 'deal' | 'deal_created' | 'done'

const STEP_LABELS: Record<Step, string> = {
  select: 'Выбор файла',
  upload: 'Загрузка на сервер',
  ocr: 'Распознавание (OCR)',
  analyze: 'Анализ документа',
  deal: 'Контекст сделки',
  deal_created: 'Сделка создана',
  done: 'Готово',
}

const STEP_ICONS: Record<Step, string> = {
  select: '📁',
  upload: '📤',
  ocr: '🔍',
  analyze: '🧠',
  deal: '🤝',
  deal_created: '✅',
  done: '✅',
}

export default function DocumentsImportPage() {
  const router = useRouter()
  const [file, setFile] = useState<File | null>(null)
  const [companies, setCompanies] = useState<any[]>([])
  const [companyId, setCompanyId] = useState('')
  const [step, setStep] = useState<Step>('select')
  const [dragOver, setDragOver] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [dealResult, setDealResult] = useState<any>(null)
  const [uploading, setUploading] = useState(false)
  const [analysis, setAnalysis] = useState<any>(null)
  const [deals, setDeals] = useState<any[]>([])
  const [dealStep, setDealStep] = useState('')
  const [ocrJobId, setOcrJobId] = useState('')
  const [pendingDeal, setPendingDeal] = useState<string | null>(null)
  const pendingDealRef = useRef<string | null>(null)

  useEffect(() => { fetchCompanies() }, [])

  // Check URL params for pending deal context
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const dealParam = params.get('deal_id')
    if (dealParam) {
      setPendingDeal(dealParam)
    }
  }, [])

  const fetchCompanies = async () => {
    try {
      const r = await fetch(`${API_URL}/api/v1/companies`)
      const data = await r.json()
      setCompanies(data.companies || [])
      if ((data.companies || []).length > 0) setCompanyId(data.companies[0].id)
    } catch {}
  }

  const ext = file ? file.name.split('.').pop()?.toUpperCase() : ''
  const isSupported = ext ? SUPPORTED.includes(ext) : true

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) setFile(f)
  }, [])

  // ── MAIN UPLOAD FLOW ──

  const doUpload = async () => {
    if (!file || !companyId) return
    setStep('upload')
    setResult(null)
    setAnalysis(null)

    try {
      // Step 1: Upload file → returns job_id immediately
      const fd = new FormData()
      fd.append('file', file)
      fd.append('company_id', companyId)
      const token = localStorage.getItem('realtor-auth')
        ? JSON.parse(localStorage.getItem('realtor-auth') || '{}')?.state?.token : null

      const uploadResp = await fetch(`${API_URL}/api/v1/upload/document`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      })
      if (!uploadResp.ok) {
        const err = await uploadResp.text()
        throw new Error(err)
      }
      const uploadResult = await uploadResp.json()
      const jobId = uploadResult.job_id
      if (!jobId) throw new Error('No job_id returned')

      // Step 2: Poll for OCR completion
      setStep('ocr')
      const ocrResult = await pollJob(jobId)
      setResult(ocrResult)

      // Step 3: Analyze document
      setStep('analyze')
      const dealAnalysis = await analyzeDocument(
        ocrResult.classification || 'unknown',
        ocrResult.extracted_fields?.amounts || [],
        ocrResult.extracted_fields?.inn || '',
        ocrResult.extracted_fields?.counterparty || '',
        ocrResult.extracted_fields?.dates || [],
      )
      setAnalysis(dealAnalysis)

      // Step 4: Show deal context
      setStep('deal')
      toast.success(`📄 Распознан: ${ocrResult.classification}`)
    } catch (e: any) {
      toast.error(e.message || 'Ошибка при обработке документа')
      setStep('select')
    }
  }

  // ── JOB POLLING ──

  const pollJob = async (jobId: string, maxPolls = 120): Promise<any> => {
    for (let i = 0; i < maxPolls; i++) {
      await new Promise(r => setTimeout(r, 3000))
      try {
        const resp = await fetch(`${API_URL}/api/v1/upload/job/${jobId}`)
        if (!resp.ok) {
          if (i < 3) continue // retry first 3 failures
          throw new Error(`Ошибка сервера: ${resp.status}`)
        }
        const data = await resp.json()
        if (data.status === 'completed') {
          // Check resolution for auto-attach suggestion
          if (data.resolution?.decision === 'auto_attach' && !pendingDealRef.current) {
            pendingDealRef.current = data.resolution.matched_deal_id
            setPendingDeal(data.resolution.matched_deal_id)
          }
          return data
        }
        if (data.status === 'failed') {
          throw new Error(data.error || 'OCR не удалось распознать документ')
        }
        if (data.status === 'error') {
          throw new Error(data.error || 'Ошибка распознавания')
        }
        // Still pending — keep polling
      } catch (e: any) {
        if (i >= maxPolls - 1) throw e
        // else retry
      }
    }
    throw new Error('OCR не завершился за ' + (maxPolls * 3) + ' сек')
  }

  // ── DOCUMENT ANALYSIS ──

  const analyzeDocument = async (
    docType: string,
    amounts: number[],
    inn: string,
    counterparty: string,
    dates: string[],
  ): Promise<any> => {
    // Fetch existing deals for this company
    let existingDeals: any[] = []
    try {
      const r = await fetch(`${API_URL}/api/v1/deals?company_id=${companyId}`)
      if (r.ok) {
        const data = await r.json()
        existingDeals = data.items || data.deals || []
      }
    } catch {}

    setDeals(existingDeals)

    const mainAmount = amounts.length > 0 ? Math.max(...amounts) : 0

    // Determine if this is a new or existing deal
    const dealTypesForDoc: Record<string, string> = {
      contract: 'purchase',
      municipal_contract: 'purchase',
      invoice: 'payment',
      receipt: 'expense',
      act: 'acceptance',
      payment_order: 'payment',
      property_doc: 'registration',
      bank_statement: 'reconciliation',
    }

    const suggestedDealType = dealTypesForDoc[docType] || 'other'

    // Determine missing documents
    const missingDocsByType: Record<string, string[]> = {
      purchase: ['ДКП (договор купли-продажи)', 'Акт приема-передачи', 'Выписка ЕГРН', 'Платёжное поручение'],
      payment: ['Счёт на оплату', 'Платёжное поручение', 'Акт сверки'],
      expense: ['Кассовый чек', 'Авансовый отчёт', 'Товарный чек'],
      acceptance: ['Договор', 'Акт выполненных работ', 'Счёт-фактура'],
      registration: ['Свидетельство о праве', 'Кадастровый паспорт', 'Выписка ЕГРН'],
    }

    // Determine what's missing based on current doc type
    const allRequired = missingDocsByType[suggestedDealType] || []
    const currentDocLabel = docTypeLabel(docType).toLowerCase()
    const currentDocCode = docType.toLowerCase()
    const stillMissing = allRequired.filter(d => {
      const dl = d.toLowerCase()
      // Skip docs that match the uploaded document type
      if (dl.includes('дкп') && (currentDocCode === 'contract' || currentDocCode === 'municipal_contract')) return false
      if (dl.includes('счёт') && currentDocCode === 'invoice') return false
      if (dl.includes('акт') && currentDocCode === 'act') return false
      if (dl.includes('чек') && currentDocCode === 'receipt') return false
      if (dl.includes('платёж') && currentDocCode === 'payment_order') return false
      if (dl.includes('выписк') && currentDocCode === 'bank_statement') return false
      if (dl.includes('кадастр') && currentDocCode === 'property_doc') return false
      if (dl.includes('свидетельств') && currentDocCode === 'property_doc') return false
      if (currentDocLabel.includes(dl.slice(0, 8))) return false
      return true
    })

    // Suggested next stage
    const stages = ['Осмотр объекта', 'Оценка', 'Переговоры', 'Договор', 'Оплата', 'Регистрация', 'Закрытие']
    const suggestedStage = docType === 'contract' ? 'Договор'
      : docType === 'payment_order' ? 'Оплата'
      : docType === 'property_doc' ? 'Регистрация'
      : 'Осмотр объекта'

    return {
      isNewDeal: existingDeals.length === 0,
      existingDeals,
      suggestedDealType,
      currentDocLabel,
      mainAmount,
      inn,
      counterparty,
      dealTypeLabel: dealTypeLabel(suggestedDealType),
      stillMissing,
      suggestedStage,
      stages,
    }
  }

  const docTypeLabel = (t: string): string => {
    const labels: Record<string, string> = {
      contract: 'Договор / ДКП',
      invoice: 'Счёт-фактура',
      receipt: 'Чек / Квитанция',
      act: 'Акт выполненных работ',
      payment_order: 'Платёжное поручение',
      municipal_contract: 'Муниципальный контракт',
      property_doc: 'Выписка / Свидетельство',
      bank_statement: 'Банковская выписка',
    }
    return labels[t] || t
  }

  const dealTypeLabel = (t: string): string => {
    const labels: Record<string, string> = {
      purchase: 'Покупка недвижимости',
      payment: 'Платёж / Оплата',
      expense: 'Расход / Затраты',
      acceptance: 'Приёмка работ',
      registration: 'Регистрация прав',
      reconciliation: 'Сверка',
    }
    return labels[t] || t
  }

  // ── NAVIGATION ──

  const goToDeal = async () => {
    if (!result?.job_id) return
    setUploading(true)
    try {
      const currentPendingDeal = pendingDealRef.current
      const isBind = !!currentPendingDeal
      const url = isBind
        ? `${API_URL}/api/v1/documents/${result.job_id}/bind-to-deal/${currentPendingDeal}`
        : `${API_URL}/api/v1/documents/${result.job_id}/promote-to-deal`

      const resp = await fetch(url, { method: 'POST' })
      if (!resp.ok) {
        const err = await resp.text()
        if (resp.status === 400 && err.includes('low')) {
          toast.error('Уверенность распознавания слишком низкая')
          return
        }
        throw new Error(err)
      }
      const deal = await resp.json()

      if (deal.status === 'review_required') {
        toast.warning(`Требуется подтверждение (уверенность: ${Math.round(deal.confidence * 100)}%)`)
        return
      }

      if (deal.status === 'existing' || deal.status === 'already_bound') {
        toast.info(isBind ? 'Документ уже привязан к сделке' : 'Сделка уже существует')
        setStep('deal_created')
        setDealResult(deal)
        return
      }

      // Bind-to-deal succeeded
      if (deal.status === 'bound') {
        setStep('deal_created')
        setDealResult(deal)
        setPendingDeal(null)
        pendingDealRef.current = null
        if (deal.requirement_matched) {
          toast.success(`✅ Документ привязан к сделке: ${deal.requirement_label}`)
        } else {
          toast.info(`📎 Документ добавлен к сделке (требование не найдено)`)
        }
        return
      }

      // New deal created
      setStep('deal_created')
      setDealResult(deal)
      setPendingDeal(null)
      setAnalysis((prev: any) => ({
        ...prev,
        dealId: deal.deal_id,
        dealType: deal.deal_type,
        missingDocs: deal.document_requirements?.filter((r: any) => r.status !== 'verified') || [],
        accountingIntent: deal.accounting_intent,
      }))

      if (isBind) {
        if (deal.requirement_matched) {
          toast.success(`✅ Документ привязан к сделке: ${deal.requirement_label}`)
        } else {
          toast.info(`📎 Документ добавлен к сделке (требование не найдено)`)
        }
      } else {
        toast.success(deal.auto_promoted
          ? `✅ Сделка создана: ${deal.deal_title?.slice(0, 50)}...`
          : `✅ Сделка создана: ${deal.deal_title?.slice(0, 50)}...`)
      }
    } catch (e: any) {
      toast.error(e.message || 'Ошибка')
    } finally {
      setUploading(false)
    }
  }

  const goToMissingDoc = (req: any) => {
    toast.info(`Загрузите: ${req.label}`)
    setFile(null)
    setStep('select')
  }

  // ── RENDER ──

  const stepOrder: Step[] = ['select', 'upload', 'ocr', 'analyze', 'deal', 'deal_created', 'done']

  const renderStepIndicator = () => (
    <div className="flex items-center gap-0 mb-8 bg-white rounded-xl border p-3">
      {stepOrder.map((s, i) => {
        const currentIdx = stepOrder.indexOf(step)
        const isDone = stepOrder.indexOf(s) < currentIdx
        const isActive = s === step
        return (
          <div key={s} className="flex items-center flex-1">
            <div className={`flex items-center gap-1.5 text-xs ${
              isActive ? 'text-blue-700 font-semibold' : isDone ? 'text-green-600' : 'text-gray-400'
            }`}>
              <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold ${
                isDone ? 'bg-green-100 text-green-700' :
                isActive ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-400'
              }`}>
                {isDone ? '✓' : i + 1}
              </span>
              <span className="hidden sm:inline">{STEP_LABELS[s]}</span>
            </div>
            {i < stepOrder.length - 1 && (
              <div className={`flex-1 h-px mx-2 ${isDone ? 'bg-green-300' : 'bg-gray-200'}`} />
            )}
          </div>
        )
      })}
    </div>
  )

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto bg-gray-50">
        <h1 className="text-2xl font-bold mb-2">📄 Импорт документов</h1>
        <p className="text-sm text-gray-500 mb-6">Загрузите документ — OCR распознает, система определит контекст сделки</p>

        {renderStepIndicator()}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* ── Upload Panel ── */}
            {step === 'select' && (
              <div className="bg-white rounded-xl border p-6">
                <h2 className="text-lg font-semibold mb-4">Загрузить документ</h2>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Компания</label>
                  <select value={companyId} onChange={e => setCompanyId(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm bg-white">
                    {companies.map(c => (
                      <option key={c.id} value={c.id}>{c.name} ({c.inn})</option>
                    ))}
                  </select>
                </div>

                <div className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer
                  ${dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'}`}
                  onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  onClick={() => document.getElementById('file-input')?.click()}>
                  <input id="file-input" type="file"
                    accept=".pdf,.jpg,.jpeg,.png,.zip,.doc,.docx,.xls,.xlsx,.xml,.txt"
                    className="hidden"
                    onChange={e => setFile(e.target.files?.[0] || null)} />
                  <div className="text-4xl mb-2">📤</div>
                  <p className="text-gray-600 text-sm mb-2">
                    {file ? file.name : 'Перетащите файл или нажмите для выбора'}
                  </p>
                  {file && <p className="text-xs text-gray-400">{(file.size / 1024 / 1024).toFixed(2)} MB · {ext}</p>}
                  {!isSupported && file && <p className="text-xs text-red-500 mt-1">Формат не поддерживается</p>}
                </div>

                <button onClick={doUpload}
                  disabled={!file || !companyId || !isSupported}
                  className="mt-4 w-full px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium
                    disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors">
                  📤 Загрузить и распознать
                </button>
              </div>
            )}

            {/* ── Progress during processing ── */}
            {(step === 'upload' || step === 'ocr' || step === 'analyze') && (
              <div className="bg-white rounded-xl border p-12 text-center">
                <div className="text-5xl mb-4 animate-pulse">{STEP_ICONS[step]}</div>
                <h3 className="text-lg font-semibold mb-2">{STEP_LABELS[step]}</h3>
                <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
                  <span className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin inline-block" />
                  {step === 'upload' && 'Загрузка файла на сервер...'}
                  {step === 'ocr' && 'Распознавание текста через OCR (до 30 сек)...'}
                  {step === 'analyze' && 'Анализ документа и определение контекста...'}
                </div>
                {ocrJobId && step === 'ocr' && (
                  <p className="text-xs text-gray-400 mt-2">Job ID: {ocrJobId.slice(0, 8)}...</p>
                )}
              </div>
            )}

            {/* ── Deal Context ── */}
            {step === 'deal' && analysis && (
              <div className="space-y-4">
                {/* Recognition result card */}
                {result && (
                  <div className="bg-white rounded-xl border p-6">
                    <h2 className="text-lg font-semibold mb-4">✅ Распознано</h2>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                      <div className="bg-gray-50 p-3 rounded-lg">
                        <span className="text-xs text-gray-500">Тип</span>
                        <p className="font-semibold mt-0.5">{analysis.currentDocLabel}</p>
                      </div>
                      <div className="bg-gray-50 p-3 rounded-lg">
                        <span className="text-xs text-gray-500">Точность</span>
                        <p className="font-semibold mt-0.5">{Math.round((result.confidence || 0) * 100)}%</p>
                      </div>
                      {analysis.mainAmount > 0 && (
                        <div className="bg-gray-50 p-3 rounded-lg">
                          <span className="text-xs text-gray-500">Сумма</span>
                          <p className="font-semibold mt-0.5">{analysis.mainAmount.toLocaleString('ru-RU')} ₽</p>
                        </div>
                      )}
                      {analysis.inn && (
                        <div className="bg-gray-50 p-3 rounded-lg">
                          <span className="text-xs text-gray-500">ИНН</span>
                          <p className="font-semibold mt-0.5 font-mono">{analysis.inn}</p>
                        </div>
                      )}
                    </div>
                    {result.extracted_text_preview && (
                      <pre className="text-xs bg-gray-50 p-3 rounded-lg mt-4 overflow-auto max-h-28 whitespace-pre-wrap">
                        {result.extracted_text_preview}
                      </pre>
                    )}
                  </div>
                )}

                {/* Deal card */}
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-2xl">{pendingDeal ? '📎' : analysis.isNewDeal ? '🆕' : '📋'}</span>
                    <div>
                      <h2 className="text-lg font-semibold">
                        {pendingDeal ? 'Привязка к сделке' : analysis.isNewDeal ? 'Новая сделка' : 'Существующая сделка'}
                      </h2>
                      <p className="text-sm text-gray-600">
                        Тип: {analysis.dealTypeLabel} · Этап: {analysis.suggestedStage}
                      </p>
                    </div>
                  </div>

                  {analysis.counterparty && (
                    <div className="text-sm text-gray-700 mb-3">
                      Контрагент: <span className="font-medium">{analysis.counterparty}</span>
                    </div>
                  )}

                  {/* Missing documents — existing step */}
                  {analysis.stillMissing?.length > 0 && (
                    <div className="mt-4">
                      <h3 className="text-sm font-semibold text-gray-700 mb-2">Не хватает документов:</h3>
                      <div className="flex flex-wrap gap-2">
                        {analysis.stillMissing.map((doc: string, i: number) => (
                          <button key={i} onClick={() => goToMissingDoc({label: doc})}
                            className="px-3 py-1.5 bg-white border border-dashed border-gray-300 rounded-lg text-xs
                              hover:border-blue-400 hover:text-blue-600 transition-colors cursor-pointer">
                            + {doc}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Stage selector */}
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">Этап сделки:</h3>
                    <div className="flex flex-wrap gap-1.5">
                      {analysis.stages.map((stage: string) => (
                        <button key={stage}
                          onClick={() => setDealStep(stage)}
                          className={`px-2.5 py-1 rounded-lg text-xs border transition-colors ${
                            (dealStep || analysis.suggestedStage) === stage
                              ? 'bg-blue-600 text-white border-blue-600'
                              : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'
                          }`}>
                          {stage}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Resolution info */}
                  {result.resolution && analysis && (
                    <div className={`mt-4 p-3 rounded-lg border ${
                      result.resolution.decision === 'auto_attach' ? 'bg-emerald-50 border-emerald-200' :
                      result.resolution.decision === 'review_required' ? 'bg-amber-50 border-amber-200' :
                      pendingDeal ? 'bg-blue-50 border-blue-200' : 
                      'bg-gray-50 border-gray-200'
                    }`}>
                      <div className="flex items-center gap-2">
                        {pendingDeal ? <span className="text-lg">📎</span> :
                         result.resolution.decision === 'auto_attach' ? <span className="text-lg">🔗</span> :
                         result.resolution.decision === 'review_required' ? <span className="text-lg">⚠️</span> :
                         <span className="text-lg">🆕</span>}
                        <div className="text-xs">
                          {pendingDeal ? (
                            <div>
                              <p className="font-medium text-blue-800">📎 Контекст сделки: документ будет привязан к текущей сделке</p>
                              <p className="text-gray-500 mt-0.5">Нажмите «Привязать к текущей сделке» для закрытия требования</p>
                            </div>
                          ) : result.resolution.decision === 'auto_attach' ? (
                            <p className="font-medium text-emerald-800">
                              ✅ Документ соответствует сделке ({result.resolution.score}%)
                            </p>
                          ) : result.resolution.decision === 'review_required' ? (
                            <p className="font-medium text-amber-800">
                              ⚠ Найдено {result.resolution.candidate_count} похожих сделок
                            </p>
                          ) : (
                            <p className="font-medium text-gray-600">
                              🆕 Документ не соответствует существующим сделкам
                            </p>
                          )}
                          {!pendingDeal && result.resolution.evidence?.slice(0, 3).map((e: any, i: number) => (
                            <p key={i} className="text-gray-500 mt-0.5">
                              {e.matched ? '✓' : '✗'} {e.field}: {e.weight}%
                            </p>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Action buttons */}
                  <div className="flex gap-3 mt-4">
                    {(!pendingDeal) ? (
                      <button onClick={goToDeal} disabled={uploading}
                        className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                        {uploading ? 'Создание...' : '📋 Создать сделку'}
                      </button>
                    ) : (
                      <button onClick={goToDeal} disabled={uploading}
                        className="flex-1 px-4 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50">
                        {uploading ? 'Привязка...' : '🔗 Привязать к текущей сделке'}
                      </button>
                    )}
                    <button onClick={() => { setFile(null); setStep('select') }}
                      className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
                      + Загрузить ещё
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ── Deal Created ── */}
            {step === 'deal_created' && dealResult && (
              <div className="space-y-4">
                <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl border border-green-200 p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-3xl">✅</span>
                    <div>
                      <h2 className="text-lg font-semibold">Сделка создана</h2>
                      <p className="text-sm text-gray-600">
                        {dealResult.deal_title?.slice(0, 80)}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                    <div className="bg-white p-3 rounded-lg">
                      <span className="text-xs text-gray-500">Тип сделки</span>
                      <p className="font-semibold mt-0.5">{dealResult.deal_type}</p>
                    </div>
                    <div className="bg-white p-3 rounded-lg">
                      <span className="text-xs text-gray-500">Учётное назначение</span>
                      <p className="font-semibold mt-0.5">{dealResult.accounting_intent === 'postable' ? '📊 Подлежит проводке' : '📋 Только учёт'}</p>
                    </div>
                    {dealResult.price > 0 && (
                      <div className="bg-white p-3 rounded-lg">
                        <span className="text-xs text-gray-500">Сумма</span>
                        <p className="font-semibold mt-0.5">{dealResult.price.toLocaleString('ru-RU')} ₽</p>
                      </div>
                    )}
                    <div className="bg-white p-3 rounded-lg">
                      <span className="text-xs text-gray-500">Статус</span>
                      <p className="font-semibold mt-0.5 text-green-600">{dealResult.deal_stage || 'DEAL_CANDIDATE'}</p>
                    </div>
                  </div>

                  {/* Confidence level indicator */}
                  {dealResult.confidence_level && (
                    <div className="mt-3 text-xs">
                      <span className={`inline-block px-2 py-0.5 rounded-full ${
                        dealResult.confidence_level === 'auto_promote' ? 'bg-green-100 text-green-700' :
                        dealResult.confidence_level === 'review_required' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {dealResult.confidence_level === 'auto_promote' ? '✓ Автоматическое продвижение' :
                         dealResult.confidence_level === 'review_required' ? '⚠ Требует подтверждения' :
                         '✗ Ручная классификация'}
                      </span>
                    </div>
                  )}

                  {/* Received docs */}
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold text-green-700 mb-2">✅ Получено:</h3>
                    <div className="flex flex-wrap gap-2">
                      {dealResult.document_requirements?.filter((r: any) => r.status === 'verified').map((r: any, i: number) => (
                        <span key={i} className="px-3 py-1.5 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700">
                          ✓ {r.label}
                        </span>
                      ))}
                      {(!dealResult.document_requirements || dealResult.document_requirements.filter((r: any) => r.status === 'verified').length === 0) && (
                        <span className="text-xs text-gray-400">(основной документ)</span>
                      )}
                    </div>
                  </div>

                  {/* Missing docs */}
                  {dealResult.missing_count > 0 && (
                    <div className="mt-4">
                      <h3 className="text-sm font-semibold text-amber-700 mb-2">⏳ Требуется:</h3>
                      <div className="flex flex-wrap gap-2">
                        {dealResult.document_requirements?.filter((r: any) => r.status !== 'verified').map((r: any, i: number) => (
                          <button key={i} onClick={() => goToMissingDoc(r)}
                            className={`px-3 py-1.5 border rounded-lg text-xs transition-colors cursor-pointer ${
                              r.is_required
                                ? 'bg-white border-dashed border-amber-300 hover:border-blue-400 hover:text-blue-600'
                                : 'bg-gray-50 border-gray-200 text-gray-400 hover:border-blue-300'
                            }`}>
                            {r.is_required ? '+ ' : '○ '}{r.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Accounting intent */}
                  {dealResult.accounting_intent && (
                    <div className="mt-3 text-xs text-gray-500">
                      Учётное назначение: {' '}
                      <span className={`font-medium ${dealResult.accounting_intent === 'postable' ? 'text-blue-600' : 'text-gray-600'}`}>
                        {dealResult.accounting_intent === 'postable' ? 'Подлежит проводке' : 'Только учёт'}
                      </span>
                    </div>
                  )}

                  <div className="flex gap-3 mt-6">
                    <button onClick={() => router.push(`/deals/${dealResult.deal_id}`)}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
                      📋 Открыть сделку
                    </button>
                    <button onClick={() => { 
                      const d = dealResult?.deal_id
                      setFile(null); setResult(null); setAnalysis(null); 
                      if (d) { setPendingDeal(d); pendingDealRef.current = d }
                      setDealResult(null)
                      setStep('select') 
                    }}
                      className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
                      + Загрузить ещё документ к сделке
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ── Sidebar ── */}
          <div className="space-y-6">
            <div className="bg-white rounded-xl border p-6">
              <h2 className="text-lg font-semibold mb-4">💡 Как работает импорт</h2>
              <ol className="text-sm space-y-3 text-gray-600">
                <li className="flex gap-2">
                  <span className="font-bold text-blue-600">1</span>
                  <span>Вы загружаете файл (PDF, JPG, DOCX, XLSX)</span>
                </li>
                <li className="flex gap-2">
                  <span className="font-bold text-blue-600">2</span>
                  <span>OCR-нода (GPU Tesla P100) распознаёт текст</span>
                </li>
                <li className="flex gap-2">
                  <span className="font-bold text-blue-600">3</span>
                  <span>Извлекаются: суммы, даты, ИНН, контрагенты</span>
                </li>
                <li className="flex gap-2">
                  <span className="font-bold text-blue-600">4</span>
                  <span>Документ классифицируется (договор, счёт, акт...)</span>
                </li>
                <li className="flex gap-2">
                  <span className="font-bold text-blue-600">5</span>
                  <span>Система определяет контекст сделки и недостающие документы</span>
                </li>
                <li className="flex gap-2">
                  <span className="font-bold text-blue-600">6</span>
                  <span>Вы переходите к сделке или загружаете следующий документ</span>
                </li>
              </ol>
            </div>

            {result && analysis && (
              <div className="bg-green-50 rounded-xl border border-green-200 p-4">
                <h3 className="text-sm font-semibold text-green-800 mb-1">✅ Готово</h3>
                <p className="text-xs text-green-700">
                  {analysis.currentDocLabel} — {analysis.dealTypeLabel}
                  <br />
                  ID: <code className="text-[10px]">{result.document_id?.slice(0, 12)}...</code>
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
