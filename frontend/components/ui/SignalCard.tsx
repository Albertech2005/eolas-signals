'use client'
import { motion } from 'framer-motion'
import { Share2, Clock, TrendingUp, TrendingDown } from 'lucide-react'
import { cn, formatPrice, formatFundingRate, timeAgo, generateTweetText, getDirectionBg } from '@/lib/utils'
import { ConfidenceGauge } from './ConfidenceGauge'
import { TradeButtonFull, TradeButton } from './TradeButton'
import type { Signal, LiveSignal } from '@/lib/types'

interface SignalCardProps {
  signal: Signal | LiveSignal
  compact?: boolean
  animate?: boolean
}

function isFullSignal(s: Signal | LiveSignal): s is Signal {
  return 'status' in s
}

export function SignalCard({ signal, compact = false, animate = true }: SignalCardProps) {
  const isActionable = signal.direction !== 'NO_TRADE'
  const isLong = signal.direction === 'LONG'
  const full = isFullSignal(signal)

  const card = (
    <div
      className={cn(
        'rounded-xl border transition-all duration-200',
        'bg-surface-card hover:bg-surface-elevated',
        isActionable
          ? isLong
            ? 'border-long/25 hover:border-long/40'
            : 'border-short/25 hover:border-short/40'
          : 'border-surface-border hover:border-gray-600',
        compact ? 'p-4' : 'p-5',
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          {/* Symbol badge */}
          <div className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center font-bold text-xs',
            isLong ? 'bg-long/15 text-long' : isActionable ? 'bg-short/15 text-short' : 'bg-gray-800 text-gray-400',
          )}>
            {signal.symbol}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-white text-sm">{signal.symbol}/USDC</span>
              {full && signal.status !== 'ACTIVE' && (
                <StatusBadge status={signal.status} />
              )}
            </div>
            {full && (
              <span className="text-xs text-gray-500">{timeAgo(signal.created_at)}</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Direction pill */}
          <span className={cn(
            'px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wider border',
            isActionable
              ? isLong
                ? 'bg-long/10 text-long border-long/30'
                : 'bg-short/10 text-short border-short/30'
              : 'bg-gray-800 text-gray-400 border-gray-700',
          )}>
            {isLong ? '↑ LONG' : isActionable ? '↓ SHORT' : 'NO TRADE'}
          </span>
        </div>
      </div>

      {isActionable ? (
        <>
          {/* Price levels */}
          <div className="grid grid-cols-3 gap-2 mb-4">
            <PriceLevel label="Entry" value={signal.entry_price} symbol={signal.symbol} color="text-white" />
            <PriceLevel label="TP1" value={signal.take_profit_1 ?? 0} symbol={signal.symbol} color="text-long" />
            <PriceLevel label="SL" value={signal.stop_loss ?? 0} symbol={signal.symbol} color="text-short" />
          </div>

          {/* TP2 row */}
          {!compact && (
            <div className="mb-4">
              <PriceLevel label="TP2 (extended)" value={signal.take_profit_2 ?? 0} symbol={signal.symbol} color="text-long" />
            </div>
          )}

          {/* Confidence + scores */}
          <div className={cn('flex gap-4', compact ? 'mb-3' : 'mb-4')}>
            <ConfidenceGauge
              score={signal.confidence}
              size={compact ? 'sm' : 'md'}
              showLabel={!compact}
              showBreakdown={!compact}
              scores={signal.scores as any}
            />

            {!compact && (
              <div className="flex-1 space-y-2">
                <p className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Why this signal</p>
                <ul className="space-y-1">
                  {signal.reasons?.slice(0, 4).map((r, i) => (
                    <li key={i} className="text-xs text-gray-300 flex items-start gap-1.5">
                      <span className={cn('mt-0.5 shrink-0', isLong ? 'text-long' : 'text-short')}>▸</span>
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* CTA */}
          {signal.eolas_url && (
            <div className="space-y-2">
              {compact ? (
                <TradeButton url={signal.eolas_url} direction={signal.direction} symbol={signal.symbol} size="sm" className="w-full justify-center" />
              ) : (
                <>
                  <TradeButtonFull url={signal.eolas_url} direction={signal.direction} symbol={signal.symbol} />
                  {full && (
                    <button
                      onClick={() => window.open(`https://twitter.com/intent/tweet?text=${generateTweetText(signal)}`, '_blank')}
                      className="w-full flex items-center justify-center gap-2 py-2 text-xs text-gray-400 hover:text-white border border-surface-border hover:border-gray-500 rounded-lg transition-colors"
                    >
                      <Share2 className="w-3.5 h-3.5" />
                      Share signal on X
                    </button>
                  )}
                </>
              )}
            </div>
          )}
        </>
      ) : (
        <div className="flex items-center gap-2 text-gray-500 text-sm py-2">
          <Clock className="w-4 h-4" />
          <span>Waiting for high-confidence setup…</span>
        </div>
      )}

      {/* PnL badge for resolved signals */}
      {full && signal.pnl_pct != null && (
        <div className={cn(
          'mt-3 pt-3 border-t flex items-center justify-between text-xs',
          'border-surface-border',
        )}>
          <span className="text-gray-500">Result</span>
          <span className={cn('font-bold font-mono', signal.is_winner ? 'text-long' : 'text-short')}>
            {signal.is_winner ? '+' : ''}{signal.pnl_pct?.toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  )

  if (!animate) return card

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {card}
    </motion.div>
  )
}

function PriceLevel({ label, value, symbol, color }: { label: string; value: number; symbol: string; color: string }) {
  return (
    <div className="bg-surface-elevated rounded-lg p-2 text-center">
      <div className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">{label}</div>
      <div className={cn('text-xs font-mono font-semibold', color)}>
        {value ? formatPrice(value, symbol) : '—'}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; color: string }> = {
    HIT_TP1: { label: 'TP1 ✓', color: 'bg-long/10 text-long border-long/30' },
    HIT_TP2: { label: 'TP2 ✓', color: 'bg-long/20 text-long border-long/40' },
    HIT_SL: { label: 'Stopped Out', color: 'bg-short/10 text-short border-short/30' },
    EXPIRED: { label: 'Timed Out', color: 'bg-gray-800 text-gray-500 border-gray-700' },
  }
  const c = config[status] ?? { label: status, color: 'bg-gray-800 text-gray-400 border-gray-700' }
  return (
    <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-semibold border', c.color)}>
      {c.label}
    </span>
  )
}
