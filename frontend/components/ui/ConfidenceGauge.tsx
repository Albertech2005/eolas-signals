'use client'
import { cn, getConfidenceColor, getConfidenceLabel } from '@/lib/utils'

interface ConfidenceGaugeProps {
  score: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  showBreakdown?: boolean
  scores?: {
    oi_divergence: number
    funding_rate: number
    liquidation: number
    momentum: number
    volatility: number
  }
}

const SCORE_BARS = [
  { key: 'oi_divergence', label: 'OI Divergence', max: 25, color: 'bg-indigo-500' },
  { key: 'funding_rate', label: 'Funding Rate', max: 20, color: 'bg-violet-500' },
  { key: 'liquidation', label: 'Liquidation', max: 25, color: 'bg-pink-500' },
  { key: 'momentum', label: 'Momentum', max: 20, color: 'bg-orange-500' },
  { key: 'volatility', label: 'Volatility Quality', max: 10, color: 'bg-teal-500' },
]

export function ConfidenceGauge({ score, size = 'md', showLabel = true, showBreakdown = false, scores }: ConfidenceGaugeProps) {
  const color = getConfidenceColor(score)
  const label = getConfidenceLabel(score)

  const circleSize = { sm: 56, md: 80, lg: 110 }[size]
  const strokeWidth = { sm: 5, md: 7, lg: 8 }[size]
  const fontSize = { sm: 'text-base', md: 'text-2xl', lg: 'text-3xl' }[size]

  const radius = (circleSize - strokeWidth * 2) / 2
  const circumference = 2 * Math.PI * radius
  const progress = (score / 100) * circumference
  const dashOffset = circumference - progress

  const strokeColor = score >= 85 ? '#22c55e' : score >= 70 ? '#84cc16' : '#6b7280'

  return (
    <div className="flex flex-col items-center gap-2">
      {/* Circular gauge */}
      <div className="relative" style={{ width: circleSize, height: circleSize }}>
        <svg width={circleSize} height={circleSize} className="-rotate-90">
          {/* Background */}
          <circle
            cx={circleSize / 2}
            cy={circleSize / 2}
            r={radius}
            fill="none"
            stroke="#1e1e2a"
            strokeWidth={strokeWidth}
          />
          {/* Progress */}
          <circle
            cx={circleSize / 2}
            cy={circleSize / 2}
            r={radius}
            fill="none"
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.6s ease' }}
          />
        </svg>
        {/* Score text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn('font-bold font-mono leading-none', fontSize, color)}>{score}</span>
          {size !== 'sm' && <span className="text-gray-500 text-[9px] mt-0.5 uppercase tracking-wider">/ 100</span>}
        </div>
      </div>

      {showLabel && (
        <span className={cn('text-xs font-semibold uppercase tracking-wider', color)}>
          {label}
        </span>
      )}

      {showBreakdown && scores && (
        <div className="w-full space-y-1.5 mt-1">
          {SCORE_BARS.map(({ key, label, max, color: barColor }) => {
            const val = scores[key as keyof typeof scores] ?? 0
            const pct = (val / max) * 100
            return (
              <div key={key} className="space-y-0.5">
                <div className="flex justify-between items-center">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wide">{label}</span>
                  <span className="text-[10px] text-gray-400 font-mono">{val.toFixed(1)}/{max}</span>
                </div>
                <div className="h-1.5 bg-surface-elevated rounded-full overflow-hidden">
                  <div
                    className={cn('h-full rounded-full transition-all duration-500', barColor)}
                    style={{ width: `${Math.min(100, pct)}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
