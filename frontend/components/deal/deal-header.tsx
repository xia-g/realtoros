import { HealthGauge } from '@/components/ui/health-gauge'

interface DealHeaderProps {
  deal: {
    id: string
    title: string
    type: string
    stage: string
    status: string
    health_score?: number
    compliance_score?: number
    risk_score?: number
  }
}

export function DealHeader({ deal }: DealHeaderProps) {
  return (
    <div className="flex items-center justify-between p-4 border-b bg-card rounded-lg">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold">{deal.title}</h1>
          <span className="px-2 py-0.5 text-xs rounded-full bg-brand-100 text-brand-800">
            {deal.type}
          </span>
          <span className={`px-2 py-0.5 text-xs rounded-full ${
            deal.status === 'active' ? 'bg-green-100 text-green-800'
            : deal.status === 'completed' ? 'bg-blue-100 text-blue-800'
            : 'bg-gray-100 text-gray-800'
          }`}>
            {deal.stage}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">#{deal.id.slice(0, 8)}</p>
      </div>
      <div className="flex items-center gap-4">
        {deal.health_score !== undefined && (
          <HealthGauge score={deal.health_score} size="md" label="Health" />
        )}
        {deal.compliance_score !== undefined && (
          <HealthGauge score={deal.compliance_score} size="sm" label="Compliance" />
        )}
        {deal.risk_score !== undefined && (
          <HealthGauge score={100 - deal.risk_score} size="sm" label="Safety" />
        )}
      </div>
    </div>
  )
}
