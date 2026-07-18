'use client'
import { useState } from 'react'
import { api, endpoints } from '@lib/api-client'

interface CopilotDrawerProps {
  dealId?: string
  mode?: 'deal' | 'compliance' | 'regulation' | 'operations' | 'executive'
}

export function CopilotDrawer({ dealId, mode = 'deal' }: CopilotDrawerProps) {
  const [query, setQuery] = useState('')
  const [response, setResponse] = useState<string | null>(null)
  const [sources, setSources] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const modeLabels: Record<string, string> = {
    deal: 'сделка',
    compliance: 'соответствие',
    regulation: 'регуляции',
    operations: 'операции',
    executive: 'резюме',
  }

  const handleAsk = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res: any = await api.post(endpoints.aiAsk, {
        question: query,
        deal_id: dealId,
        mode,
      })
      setResponse(res.answer || JSON.stringify(res))
      setSources(res.sources || [])
    } catch (err: any) {
      setResponse('Ошибка: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const suggestions = [
    'Каких документов не хватает?',
    'Можно ли зарегистрировать эту сделку?',
    'Какие риски по сделке?',
    'Статус compliance по сделке',
    'Краткое резюме сделки',
    'Какие этапы остались?',
  ]

  return (
    <div className="flex flex-col h-full bg-white rounded-xl border">
      <div className="p-3 border-b">
        <h3 className="font-semibold text-sm">AI Copilot</h3>
        <p className="text-xs text-muted-foreground capitalize">{modeLabels[mode] || mode} режим</p>
      </div>

      <div className="flex-1 overflow-auto p-3 space-y-3">
        {!response && suggestions.map((s) => (
          <button key={s} onClick={() => { setQuery(s); setTimeout(handleAsk, 100) }}
            className="block w-full text-left text-xs p-2 rounded-lg bg-gray-50 hover:bg-gray-100">
            {s}
          </button>
        ))}

        {loading && <p className="text-sm text-muted-foreground animate-pulse">Думаю...</p>}

        {response && (
          <div className="space-y-3">
            <div className="p-3 bg-brand-50 rounded-lg">
              <p className="text-sm whitespace-pre-wrap">{response}</p>
            </div>
            {sources.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Источники ({sources.length})</p>
                {sources.slice(0, 5).map((s: any, i: number) => (
                  <div key={i} className="text-xs p-2 bg-gray-50 rounded mb-1">
                    <span className="font-medium">{s.title || s.source_type}</span>
                    {s.confidence && <span className="ml-2 text-green-600">{Math.round(s.confidence * 100)}%</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="p-3 border-t">
        <div className="flex gap-2">
          <input value={query} onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
            placeholder="Задайте вопрос..."
            className="flex-1 px-3 py-1.5 text-sm border rounded-lg" />
          <button onClick={handleAsk} disabled={loading}
            className="px-3 py-1.5 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 disabled:opacity-50">
            Спросить
          </button>
        </div>
      </div>
    </div>
  )
}
