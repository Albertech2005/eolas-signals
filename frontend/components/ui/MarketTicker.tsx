'use client'
import { cn, formatPrice, formatPct, formatFundingRate, formatLargeNumber } from '@/lib/utils'
import type { MarketData } from '@/lib/types'
import { ExternalLink } from 'lucide-react'

interface MarketTickerProps {
  market: MarketData
}

export function MarketTicker({ market }: MarketTickerProps) {
  const change = market.price_change_24h
  const isUp = (change ?? 0) >= 0

  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-4 hover:border-gray-600 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-bold text-white">{market.symbol}</span>
          <span className="text-xs text-gray-500">USDC Perp</span>
        </div>
        <div className="flex gap-2">
          <a href={market.eolas_long_url} target="_blank" rel="noopener noreferrer"
             className="px-2 py-0.5 text-[10px] font-bold rounded bg-long/10 text-long border border-long/30 hover:bg-long hover:text-white transition-colors">
            LONG
          </a>
          <a href={market.eolas_short_url} target="_blank" rel="noopener noreferrer"
             className="px-2 py-0.5 text-[10px] font-bold rounded bg-short/10 text-short border border-short/30 hover:bg-short hover:text-white transition-colors">
            SHORT
          </a>
        </div>
      </div>

      <div className="flex items-end justify-between mb-3">
        <span className="text-2xl font-bold font-mono text-white">
          {formatPrice(market.price, market.symbol)}
        </span>
        <span className={cn('text-sm font-semibold', isUp ? 'text-long' : 'text-short')}>
          {formatPct(change)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        <DataRow label="OI" value={formatLargeNumber(market.open_interest)} />
        <DataRow label="OI Change" value={formatPct(market.oi_change_1h)} highlight={market.oi_change_1h} />
        <DataRow label="Funding" value={formatFundingRate(market.funding_rate)}
          className={
            (market.funding_rate ?? 0) > 0.0005 ? 'text-short' :
            (market.funding_rate ?? 0) < -0.0005 ? 'text-long' : 'text-gray-400'
          }
        />
        <DataRow label="24h Vol" value={formatLargeNumber(market.volume_24h)} />
      </div>
    </div>
  )
}

function DataRow({ label, value, highlight, className }: {
  label: string; value: string; highlight?: number | null; className?: string
}) {
  const autoColor = highlight != null
    ? highlight >= 0 ? 'text-long' : 'text-short'
    : undefined

  return (
    <div className="flex justify-between items-center">
      <span className="text-gray-600">{label}</span>
      <span className={cn('font-mono font-medium', autoColor ?? className ?? 'text-gray-300')}>
        {value}
      </span>
    </div>
  )
}
