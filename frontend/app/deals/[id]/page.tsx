'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'next/navigation'
import { api, endpoints } from '@lib/api-client'
import { Sidebar } from '@/components/layout/sidebar'
import { DealHeader } from '@/components/deal/deal-header'
import { CopilotDrawer } from '@/components/copilot/copilot-drawer'

const TABS = ['Обзор', 'Участники', 'Документы', 'Workflow', 'Compliance',
  'Риски', 'Таймлайн', 'Операции', 'AI Copilot', 'Аудит']

export default function DealWorkspacePage() {
  const { id } = useParams<{ id: string }>()
  const [activeTab, setActiveTab] = useState('Документы')

  const { data: deal, isLoading } = useQuery({
    queryKey: ['deal', id],
    queryFn: () => api.get(endpoints.deal(id)),
  })

  const { data: timeline } = useQuery({
    queryKey: ['deal-timeline', id],
    queryFn: () => api.get(endpoints.dealTimeline(id)),
    enabled: !!id,
  })

  const { data: compliance } = useQuery({
    queryKey: ['deal-compliance', id],
    queryFn: () => api.get(endpoints.dealCompliance(id)),
    enabled: !!id,
  })

  const { data: requirements } = useQuery({
    queryKey: ['deal-requirements', id],
    queryFn: () => api.get(`/api/v1/deals/${id}/requirements`),
    enabled: !!id,
  })

  if (isLoading) return <div className="flex h-screen items-center justify-center">Loading...</div>

  const renderTabContent = () => {
    switch (activeTab) {
      case 'Документы':
        return (
          <div className="space-y-3">
            <h3 className="font-semibold mb-3">Документы сделки</h3>
            {Array.isArray(requirements) && requirements.length > 0 ? (
              <div className="grid gap-2">
                {requirements.map((req: any) => (
                  <div key={req.package_id} className={`flex items-center justify-between p-3 rounded-lg border ${
                    req.status === 'verified' ? 'bg-green-50 border-green-200' : 'bg-white border-gray-200'
                  }`}>
                    <div className="flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${
                        req.status === 'verified' ? 'bg-green-500' : req.status === 'requested' ? 'bg-amber-400' : 'bg-gray-300'
                      }`} />
                      <div>
                        <p className="text-sm font-medium">{req.label}</p>
                        <p className="text-xs text-gray-500">{req.document_role || req.document_type}</p>
                      </div>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      req.status === 'verified' ? 'bg-green-100 text-green-700' : 'bg-amber-50 text-amber-600'
                    }`}>
                      {req.status === 'verified' ? '✓ Получен' : req.status === 'requested' ? '⏳ Ожидается' : req.status}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Требования не загружены</p>
            )}
            <div className="flex gap-2 mt-4">
              <a href={`/imports/documents?deal_id=${id}`}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 inline-block">
                + Загрузить документ
              </a>
            </div>
          </div>
        )

      case 'Таймлайн':
        return (
          <div>
            <h3 className="font-semibold mb-3">Таймлайн</h3>
            {timeline && Array.isArray(timeline) && timeline.length > 0 ? timeline.slice(0, 20).map((event: any) => (
              <div key={event.event_id || event.id} className="flex gap-3 py-2 border-l-2 border-blue-300 pl-3 ml-2">
                <div>
                  <p className="text-sm font-medium">{event.title || event.event_type}</p>
                  <p className="text-xs text-gray-500">
                    {event.created_at ? new Date(event.created_at).toLocaleString('ru-RU') : ''}
                  </p>
                  {event.description && <p className="text-xs text-gray-400 mt-0.5">{event.description}</p>}
                </div>
              </div>
            )) : <p className="text-sm text-gray-500">Событий пока нет</p>}
          </div>
        )

      case 'Compliance':
        return compliance ? (
          <div className="grid grid-cols-2 gap-3">
            <div className="p-4 bg-white rounded-lg border">
              <p className="text-sm text-gray-500">Score</p>
              <p className="text-lg font-bold">{String((compliance as Record<string,unknown>).score ?? '—')}</p>
            </div>
            <div className="p-4 bg-white rounded-lg border">
              <p className="text-sm text-gray-500">Risk Level</p>
              <p className="text-lg font-bold">{String((compliance as Record<string,unknown>).risk_level || '—')}</p>
            </div>
          </div>
        ) : <p className="text-sm text-gray-500">Нет данных по compliance</p>

      default:
        return <p className="text-sm text-gray-500">Вкладка в разработке</p>
    }
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <DealHeader deal={(deal || { id, title: 'Сделка #' + id.slice(0, 8), type: '—', stage: '—', status: 'active', health_score: 0, compliance_score: 0, risk_score: 0 }) as any} />

        {/* Tabs */}
        <div className="flex gap-1 px-4 py-2 border-b overflow-x-auto">
          {TABS.map((tab) => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors ${
                activeTab === tab ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'
              }`}>
              {tab}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="grid grid-cols-3 gap-4 p-4">
          <div className="col-span-2 space-y-4">
            <div className="p-4 bg-white rounded-xl border">
              {renderTabContent()}
            </div>
          </div>
          <div className="col-span-1">
            <CopilotDrawer dealId={id} />
          </div>
        </div>
      </main>
    </div>
  )
}
