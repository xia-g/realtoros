import { cn } from '@/lib/utils'

interface HealthGaugeProps {
  score: number
  size?: 'sm' | 'md' | 'lg'
  label?: string
}

const colorMap = (score: number) => {
  if (score >= 85) return 'stroke-green-500'
  if (score >= 70) return 'stroke-yellow-500'
  if (score >= 50) return 'stroke-orange-500'
  return 'stroke-red-500'
}

export function HealthGauge({ score, size = 'md', label }: HealthGaugeProps) {
  const dims = { sm: 40, md: 64, lg: 96 }
  const d = dims[size]
  const r = (d - 8) / 2
  const circumference = 2 * Math.PI * r
  const offset = circumference - (score / 100) * circumference

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={d} height={d} className="-rotate-90">
        <circle cx={d / 2} cy={d / 2} r={r} fill="none" stroke="currentColor" strokeWidth={4}
          className="text-muted-foreground/20" />
        <circle cx={d / 2} cy={d / 2} r={r} fill="none" strokeWidth={4}
          strokeDasharray={circumference} strokeDashoffset={offset}
          className={colorMap(score)} strokeLinecap="round" />
        <text x={d / 2} y={d / 2} textAnchor="middle" dominantBaseline="central"
          className="fill-foreground text-xs font-bold rotate-90"
          fontSize={size === 'sm' ? 8 : 14}>
          {Math.round(score)}
        </text>
      </svg>
      {label && <span className="text-xs text-muted-foreground">{label}</span>}
    </div>
  )
}
