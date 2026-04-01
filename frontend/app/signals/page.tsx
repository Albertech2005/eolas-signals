'use client'
import { useState } from 'react'
import { useLatestSignals } from '@/hooks/useSignals'
import { SignalCard } from '@/components/ui/SignalCard'
import { cn } from '@/lib/utils'

const SYMBOLS = ['ALL', 'BTC', 'ETH', 'SOL', 'BNB', 'ARB', 'OP']
const DIRS = ['ALL', 'LONG', 'SHORT']

export default function SignalsPage() {
  const [symbol, setSymbol] = useState('ALL')
  const [dir, setDir] = useState('ALL')
  const { signals, isLoading } = useLatestSignals(50)

  const filtered = signals.filter(s => {
    if (s.direction === 'NO_TRADE') return false
    if (symbol !== 'ALL' && s.symbol !== symbol) return false
    if (dir !== 'ALL' && s.direction !== dir) return false
    return true
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white mb-1">Signal History</h1>
        <p className="text-gray-400 text-sm">All high-confidence signals with outcomes. Active signals are live — Timed Out means the market didn't move enough within the window.</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        <div className="flex gap-1.5">
          {SYMBOLS.map(s => (
            <button key={s} onClick={() => setSymbol(s)}
              className={cn('px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors border',
                symbol === s
                  ? 'bg-brand/15 text-brand border-brand/30'
                  : 'text-gray-400 border-surface-border hover:text-white hover:border-gray-600')}>
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5">
          {DIRS.map(d => (
            <button key={d} onClick={() => setDir(d)}
              className={cn('px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors border',
                dir === d
                  ? d === 'LONG'
                    ? 'bg-long/10 text-long border-long/30'
                    : d === 'SHORT'
                    ? 'bg-short/10 text-short border-short/30'
                    : 'bg-brand/15 text-brand border-brand/30'
                  : 'text-gray-400 border-surface-border hover:text-white hover:border-gray-600')}>
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map(i => (
            <div key={i} className="h-64 bg-surface-card border border-surface-border rounded-xl animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-lg">No signals match your filter.</p>
          <p className="text-sm mt-1">The engine is conservative by design — only the best setups fire.</p>
        </div>
      ) : (
        <>
          <p className="text-xs text-gray-500">{filtered.length} signals shown</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map(s => (
              <SignalCard key={s.id} signal={s} animate />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
