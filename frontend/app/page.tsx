'use client'
import { useLiveSignals, useMarkets, useSummaryStats } from '@/hooks/useSignals'
import { useWebSocket } from '@/hooks/useWebSocket'
import { SignalCard } from '@/components/ui/SignalCard'
import { MarketTicker } from '@/components/ui/MarketTicker'
import { cn, formatPct } from '@/lib/utils'
import { Activity, TrendingUp, Award, Zap, Send, Copy, CheckCheck, ExternalLink, Star } from 'lucide-react'
import { useState, useEffect, useRef, useMemo } from 'react'
import Image from 'next/image'
import { motion } from 'framer-motion'
import type { LiveSignal } from '@/lib/types'

const WS_URL = (process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000') + '/ws'

// ── Watchlist helpers ────────────────────────────────────────────────────────
function loadWatchlist(): Set<string> {
  try {
    const raw = localStorage.getItem('eolas_watchlist')
    return raw ? new Set(JSON.parse(raw)) : new Set()
  } catch { return new Set() }
}
function saveWatchlist(s: Set<string>) {
  try { localStorage.setItem('eolas_watchlist', JSON.stringify(Array.from(s))) } catch {}
}

export default function Dashboard() {
  const { signals, dataAge, isLoading } = useLiveSignals()
  const { markets } = useMarkets()
  const { stats } = useSummaryStats()
  const { status: wsStatus } = useWebSocket(WS_URL)

  // Map symbol → current price for live P&L
  const marketMap = useMemo(() => {
    const m: Record<string, number> = {}
    markets.forEach(mk => { m[mk.symbol] = mk.price })
    return m
  }, [markets])

  const actionableSignals = signals.filter(s => s.is_actionable)
  const noTradeSignals    = signals.filter(s => !s.is_actionable)

  // ── Rate-of-change tracking ───────────────────────────────────────────────
  // Stores a snapshot of scores from ~1 refresh cycle ago
  const snapshotRef = useRef<Record<string, number>>({})
  const [scoreTrends, setScoreTrends] = useState<Record<string, number>>({})

  useEffect(() => {
    if (!noTradeSignals.length) return

    // Compute deltas vs snapshot
    const trends: Record<string, number> = {}
    noTradeSignals.forEach(s => {
      const prev = snapshotRef.current[s.symbol]
      if (prev !== undefined) trends[s.symbol] = s.confidence - prev
    })
    setScoreTrends(trends)

    // Update snapshot 14s from now (just before next 15s SWR refresh)
    const t = setTimeout(() => {
      const snap: Record<string, number> = {}
      noTradeSignals.forEach(s => { snap[s.symbol] = s.confidence })
      snapshotRef.current = snap
    }, 14_000)
    return () => clearTimeout(t)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signals])

  // ── Watchlist ─────────────────────────────────────────────────────────────
  const [watchlist, setWatchlist] = useState<Set<string>>(new Set())
  useEffect(() => { setWatchlist(loadWatchlist()) }, [])

  const toggleWatch = (symbol: string) => {
    setWatchlist(prev => {
      const next = new Set(prev)
      next.has(symbol) ? next.delete(symbol) : next.add(symbol)
      saveWatchlist(next)
      return next
    })
  }

  // Sort monitoring: watched first
  const sortedMonitoring = useMemo(() => [
    ...noTradeSignals.filter(s => watchlist.has(s.symbol)),
    ...noTradeSignals.filter(s => !watchlist.has(s.symbol)),
  ], [noTradeSignals, watchlist])

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-brand/20 via-surface-elevated to-surface-elevated border border-brand/20 p-6 sm:p-8">
        <div className="absolute inset-0 bg-gradient-to-br from-brand/5 to-transparent pointer-events-none" />
        <div className="relative flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <div className={cn('w-2 h-2 rounded-full live-dot', wsStatus === 'connected' ? 'bg-long' : 'bg-gray-500')} />
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                {wsStatus === 'connected' ? 'Live' : 'Connecting…'}
                {dataAge != null && ` · Data ${dataAge.toFixed(0)}s old`}
              </span>
            </div>
            <div className="flex items-center gap-3 mb-2">
              <Image src="/eolas-logo.jpg" alt="EOLAS" width={40} height={40} className="rounded-xl" />
              <h1 className="text-2xl sm:text-3xl font-bold text-white">
                EOLAS <span className="text-brand">Signal Intelligence</span>
              </h1>
            </div>
            <p className="text-gray-400 text-sm max-w-md">
              High-confidence LONG/SHORT signals derived from OI, funding rates, liquidations &amp; momentum.
              Execute instantly on EOLAS Perps.
            </p>
          </div>
          <a
            href={process.env.NEXT_PUBLIC_EOLAS_URL ?? 'https://perps.eolas.fun'}
            target="_blank" rel="noopener noreferrer"
            className="shrink-0 px-6 py-3 bg-brand text-white font-bold rounded-xl hover:bg-brand-dark transition-colors text-sm"
          >
            Open EOLAS DEX →
          </a>
        </div>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard icon={Zap}       label="Active Signals" value={stats.active_signals}      color="text-brand" />
          <StatCard icon={TrendingUp} label="Total Signals"  value={stats.total_signals}       color="text-white" />
          <StatCard icon={Award}     label="Win Rate"        value={`${stats.win_rate}%`}       color="text-long" />
          <StatCard icon={Activity}  label="Markets"         value={stats.supported_markets}    color="text-violet-400" />
        </div>
      )}

      {/* Active Signals */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-white">Active Signals</h2>
            {actionableSignals.length > 0 && (
              <span className="px-2 py-0.5 bg-brand/15 text-brand border border-brand/30 rounded-full text-xs font-bold">
                {actionableSignals.length}
              </span>
            )}
          </div>
          <span className="text-xs text-gray-500">Score threshold ≥75 · Min 2 strong signals</span>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => <SignalSkeleton key={i} />)}
          </div>
        ) : actionableSignals.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center border border-surface-border rounded-xl bg-surface-card">
            <div className="w-14 h-14 rounded-xl bg-surface-elevated border border-surface-border flex items-center justify-center mb-4">
              <Activity className="w-7 h-7 text-brand/60 animate-pulse" />
            </div>
            <p className="text-white font-bold text-lg mb-1">Engine is scanning markets</p>
            <p className="text-gray-500 text-sm max-w-sm mb-4">
              No high-confidence setups right now. The engine requires ≥75 confidence with at least 2 aligned indicators.
            </p>
            <div className="flex items-center gap-3">
              <a href="/signals" className="px-4 py-2 text-xs font-semibold text-brand border border-brand/30 rounded-lg hover:bg-brand/10 transition-colors">
                View Signal History →
              </a>
              <a href={process.env.NEXT_PUBLIC_TELEGRAM_CHANNEL ?? 'https://t.me/eolastest'} target="_blank" rel="noopener noreferrer"
                className="px-4 py-2 text-xs font-semibold text-gray-300 border border-surface-border rounded-lg hover:border-gray-500 transition-colors">
                Get Telegram Alerts
              </a>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {actionableSignals.map(signal => (
              <SignalCard
                key={signal.symbol}
                signal={signal}
                currentPrice={marketMap[signal.symbol]}
                animate
              />
            ))}
          </div>
        )}
      </section>

      {/* Monitoring */}
      {sortedMonitoring.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">
              Monitoring — Waiting for Setup
            </h2>
            {watchlist.size > 0 && (
              <span className="text-[10px] text-brand font-semibold">
                ★ {watchlist.size} watching
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
            {sortedMonitoring.map(s => {
              const score   = s.confidence ?? 0
              const pct     = Math.min(100, (score / 75) * 100)
              const color   = score >= 65 ? 'text-yellow-400' : score >= 45 ? 'text-gray-400' : 'text-gray-600'
              const delta   = scoreTrends[s.symbol] ?? 0
              const trend   = delta >= 3 ? '↑' : delta <= -3 ? '↓' : null
              const watched = watchlist.has(s.symbol)

              return (
                <div
                  key={s.symbol}
                  className={cn(
                    'relative bg-surface-card border rounded-lg p-3 text-center transition-colors',
                    watched ? 'border-brand/30' : 'border-surface-border',
                  )}
                >
                  {/* Watchlist star */}
                  <button
                    onClick={() => toggleWatch(s.symbol)}
                    className={cn(
                      'absolute top-1.5 right-1.5 w-5 h-5 flex items-center justify-center rounded transition-colors',
                      watched ? 'text-brand' : 'text-gray-700 hover:text-gray-500',
                    )}
                    title={watched ? 'Remove from watchlist' : 'Add to watchlist'}
                  >
                    <Star className="w-3 h-3" fill={watched ? 'currentColor' : 'none'} />
                  </button>

                  <div className="text-xs font-bold text-white mb-1.5">{s.symbol}</div>
                  <div className="w-full h-1 bg-surface-elevated rounded-full mb-1.5">
                    <div
                      className={cn('h-1 rounded-full transition-all duration-700', score >= 65 ? 'bg-yellow-500' : 'bg-brand/60')}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className={cn('text-[10px] font-semibold flex items-center justify-center gap-1', color)}>
                    {score > 0 ? `${score}/75` : 'Scanning…'}
                    {trend && (
                      <span className={trend === '↑' ? 'text-long' : 'text-short'}>{trend}</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Live Markets */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white">Live Markets</h2>
          <a href="https://perps.eolas.fun" target="_blank" rel="noopener noreferrer"
            className="text-xs text-brand hover:text-brand-light transition-colors">
            Trade on EOLAS ↗
          </a>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {markets.map(m => <MarketTicker key={m.symbol} market={m} />)}
        </div>
      </section>

      <TokenCA />

      {/* Telegram CTA */}
      <div className="rounded-xl bg-gradient-to-r from-[#0088cc]/10 to-surface-elevated border border-[#0088cc]/20 p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#0088cc]/20 flex items-center justify-center text-[#0088cc]">
            <Send className="w-5 h-5" />
          </div>
          <div>
            <p className="font-semibold text-white text-sm">Get instant signal alerts on Telegram</p>
            <p className="text-gray-400 text-xs mt-0.5">Only fires when confidence ≥75. No spam — only high-quality setups.</p>
          </div>
        </div>
        <a
          href={process.env.NEXT_PUBLIC_TELEGRAM_CHANNEL ?? '#'}
          target="_blank" rel="noopener noreferrer"
          className="shrink-0 px-5 py-2.5 bg-[#0088cc] text-white font-bold rounded-xl hover:bg-[#0077b5] transition-colors text-sm"
        >
          Join Channel →
        </a>
      </div>
    </div>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: any; color: string }) {
  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-4 flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-surface-elevated flex items-center justify-center">
        <Icon className={cn('w-4 h-4', color)} />
      </div>
      <div>
        <div className={cn('text-lg font-bold font-mono', color)}>{value}</div>
        <div className="text-[11px] text-gray-500">{label}</div>
      </div>
    </div>
  )
}

const EOLAS_CA      = '0xf878e27afb649744eec3c5c0d03bc9335703cfe3'
const BASESCAN_URL  = `https://basescan.org/token/${EOLAS_CA}`
const UNISWAP_URL   = `https://app.uniswap.org/explore/tokens/base/${EOLAS_CA}`

function TokenCA() {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    await navigator.clipboard.writeText(EOLAS_CA)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="rounded-xl bg-gradient-to-r from-brand/10 via-surface-elevated to-surface-elevated border border-brand/20 p-5 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Image src="/eolas-logo.jpg" alt="EOLAS" width={40} height={40} className="rounded-xl shrink-0" />
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-bold text-white text-sm">EOLAS Token</p>
              <span className="px-2 py-0.5 bg-blue-500/15 text-blue-400 border border-blue-500/25 rounded-full text-[10px] font-bold uppercase tracking-wide">Base</span>
            </div>
            <p className="text-gray-500 text-[11px] mt-0.5">Contract Address</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <a href={BASESCAN_URL} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-2 bg-surface-card border border-surface-border rounded-lg text-xs text-gray-400 hover:text-white hover:border-brand/40 transition-colors">
            <ExternalLink className="w-3.5 h-3.5" />Basescan
          </a>
          <a href={UNISWAP_URL} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-2 bg-brand/10 border border-brand/30 rounded-lg text-xs text-brand font-semibold hover:bg-brand/20 transition-colors">
            Buy EOLAS ↗
          </a>
        </div>
      </div>
      <div className="mt-4 flex items-center gap-2 bg-surface-card border border-surface-border rounded-lg px-3 py-2.5">
        <code className="flex-1 text-xs text-gray-300 font-mono break-all leading-relaxed">{EOLAS_CA}</code>
        <button
          onClick={handleCopy}
          className={cn(
            'shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all',
            copied ? 'bg-long/20 text-long border border-long/30' : 'bg-surface-elevated border border-surface-border text-gray-400 hover:text-white hover:border-brand/40',
          )}
        >
          {copied ? <CheckCheck className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
        </button>
      </div>
    </div>
  )
}

function SignalSkeleton() {
  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-5 animate-pulse">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 bg-surface-elevated rounded-lg" />
        <div className="flex-1 space-y-1.5">
          <div className="h-3 bg-surface-elevated rounded w-24" />
          <div className="h-2.5 bg-surface-elevated rounded w-16" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 mb-4">
        {[1, 2, 3].map(i => <div key={i} className="h-10 bg-surface-elevated rounded-lg" />)}
      </div>
      <div className="h-10 bg-surface-elevated rounded-xl" />
    </div>
  )
}
