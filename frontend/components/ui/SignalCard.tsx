'use client'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Share2, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import { cn, formatPrice, timeAgo, generateTweetText } from '@/lib/utils'
import { ConfidenceGauge } from './ConfidenceGauge'
import { TradeButtonFull, TradeButton } from './TradeButton'
import type { Signal, LiveSignal } from '@/lib/types'

interface SignalCardProps {
  signal: Signal | LiveSignal
  compact?: boolean
  animate?: boolean
  currentPrice?: number // for live P&L on active signals
}

function isFullSignal(s: Signal | LiveSignal): s is Signal {
  return 'status' in s
}

const SCORE_MODULES = [
  { key: 'oi_divergence',  label: 'OI Divergence', max: 25 },
  { key: 'funding_rate',   label: 'Funding Rate',  max: 20 },
  { key: 'liquidation',    label: 'Liquidation',   max: 25 },
  { key: 'momentum',       label: 'Momentum',      max: 20 },
  { key: 'volatility',     label: 'Volatility',    max: 10 },
]

export function SignalCard({ signal, compact = false, animate = true, currentPrice }: SignalCardProps) {
  const [showAnalysis, setShowAnalysis] = useState(false)

  const isActionable = signal.direction !== 'NO_TRADE'
  const isLong = signal.direction === 'LONG'
  const full = isFullSignal(signal)

  // Live P&L — only for active/live signals with a known entry
  const isActive = !full || signal.status === 'ACTIVE'
  const livePnl =
    currentPrice && signal.entry_price > 0 && isActive && isActionable
      ? isLong
        ? ((currentPrice - signal.entry_price) / signal.entry_price) * 100
        : ((signal.entry_price - currentPrice) / signal.entry_price) * 100
      : null

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
          <div className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center font-bold text-xs',
            isLong ? 'bg-long/15 text-long' : isActionable ? 'bg-short/15 text-short' : 'bg-gray-800 text-gray-400',
          )}>
            {signal.symbol}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-white text-sm">{signal.symbol}/USDC</span>
              {full && signal.status !== 'ACTIVE' && <StatusBadge status={signal.status} />}
            </div>
            {full && signal.created_at && (
              <span className="text-xs text-gray-500">{timeAgo(signal.created_at)}</span>
            )}
          </div>
        </div>

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

      {isActionable ? (
        <>
          {/* Price levels */}
          <div className="grid grid-cols-3 gap-2 mb-4">
            <EntryZoneLevel entryPrice={signal.entry_price} symbol={signal.symbol} compact={compact} />
            <PriceLevel label="TP1" value={signal.take_profit_1 ?? 0} symbol={signal.symbol} color="text-long" />
            <PriceLevel label="SL"  value={signal.stop_loss ?? 0}      symbol={signal.symbol} color="text-short" />
          </div>

          {/* TP2 */}
          {!compact && (
            <div className="mb-4">
              <PriceLevel label="TP2 (extended)" value={signal.take_profit_2 ?? 0} symbol={signal.symbol} color="text-long" />
            </div>
          )}

          {/* Confidence + reasons */}
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

          {/* Full Score Breakdown toggle */}
          {!compact && (
            <button
              onClick={() => setShowAnalysis(v => !v)}
              className="w-full flex items-center justify-between px-3 py-2 mb-3 text-xs text-gray-400 hover:text-white border border-surface-border hover:border-gray-500 rounded-lg transition-colors"
            >
              <span className="font-medium">Full Score Breakdown</span>
              {showAnalysis ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}

          {/* Score breakdown panel */}
          {!compact && showAnalysis && (
            <div className="mb-3 p-3 bg-surface-elevated rounded-lg border border-surface-border space-y-2.5">
              {SCORE_MODULES.map(mod => {
                const raw = (signal.scores as any)?.[mod.key] ?? 0
                const pct = Math.min(100, (raw / mod.max) * 100)
                const scoreColor = pct >= 70 ? (isLong ? 'bg-long' : 'bg-short') : pct >= 40 ? 'bg-yellow-500' : 'bg-gray-600'
                return (
                  <div key={mod.key}>
                    <div className="flex items-center justify-between text-[10px] mb-1">
                      <span className="text-gray-400">{mod.label}</span>
                      <span className="font-mono text-white">
                        {raw.toFixed(1)}<span className="text-gray-600">/{mod.max}</span>
                      </span>
                    </div>
                    <div className="h-1.5 bg-surface-card rounded-full overflow-hidden">
                      <div className={cn('h-full rounded-full transition-all duration-500', scoreColor)} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
              <p className="text-[10px] text-gray-600 pt-1.5 border-t border-surface-border">
                Total: <span className="text-white font-mono">{signal.confidence}</span>/100 · fires at ≥45
              </p>
            </div>
          )}

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

      {/* Live P&L — active signals */}
      {livePnl !== null && (
        <div className="mt-3 pt-3 border-t border-surface-border flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-brand animate-pulse" />
            <span className="text-gray-500">Live P&amp;L</span>
          </div>
          <span className={cn('font-bold font-mono', livePnl >= 0 ? 'text-long' : 'text-short')}>
            {livePnl >= 0 ? '+' : ''}{livePnl.toFixed(2)}%
          </span>
        </div>
      )}

      {/* Result — resolved signals only */}
      {full && signal.pnl_pct != null && signal.is_winner != null && (
        <div className="mt-3 pt-3 border-t border-surface-border flex items-center justify-between text-xs">
          <span className="text-gray-500">Result</span>
          <span className={cn('font-bold font-mono', signal.is_winner === true ? 'text-long' : 'text-short')}>
            {signal.is_winner === true ? '+' : ''}{signal.pnl_pct?.toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  )

  if (!animate) return card

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      {card}
    </motion.div>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function EntryZoneLevel({ entryPrice, symbol, compact }: { entryPrice: number; symbol: string; compact: boolean }) {
  const low  = entryPrice * 0.997
  const high = entryPrice * 1.003
  return (
    <div className="bg-surface-elevated rounded-lg p-2 text-center">
      <div className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">Entry</div>
      <div className="text-xs font-mono font-semibold text-white">{formatPrice(entryPrice, symbol)}</div>
      {!compact && (
        <div className="text-[9px] text-gray-600 mt-0.5 leading-tight">
          {formatPrice(low, symbol)} – {formatPrice(high, symbol)}
        </div>
      )}
    </div>
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
    HIT_TP1: { label: 'TP1 ✓',       color: 'bg-long/10 text-long border-long/30' },
    HIT_TP2: { label: 'TP2 ✓',       color: 'bg-long/20 text-long border-long/40' },
    HIT_SL:  { label: 'Stopped Out', color: 'bg-short/10 text-short border-short/30' },
    EXPIRED: { label: 'Timed Out',   color: 'bg-gray-800 text-gray-500 border-gray-700' },
  }
  const c = config[status] ?? { label: status, color: 'bg-gray-800 text-gray-400 border-gray-700' }
  return (
    <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-semibold border', c.color)}>
      {c.label}
    </span>
  )
}
