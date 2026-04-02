'use client'
import { usePerformance, useStreaks } from '@/hooks/useSignals'
import { cn } from '@/lib/utils'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Trophy, TrendingUp, Activity, Target, Flame, Snowflake } from 'lucide-react'

export default function AnalyticsPage() {
  const { performance, isLoading } = usePerformance()
  const { streaks } = useStreaks()

  if (isLoading) {
    return <div className="flex items-center justify-center h-64 text-gray-500">Loading performance data…</div>
  }

  if (!performance) {
    return (
      <div className="text-center py-20 text-gray-500">
        <p className="text-lg">No performance data yet.</p>
        <p className="text-sm mt-1">Signals need to resolve (hit TP or SL) before stats appear.</p>
      </div>
    )
  }

  const { overall, by_symbol } = performance

  const chartData = by_symbol.map(s => ({
    name: s.symbol,
    winRate: s.win_rate,
    signals: s.total,
    avgPnl: s.avg_pnl_pct,
  }))

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white mb-1">Signal Analytics</h1>
        <p className="text-gray-400 text-sm">Transparent performance tracking. Every signal outcome recorded.</p>
      </div>

      {/* Overall stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatBox icon={Activity}   label="Total Signals" value={overall.total_signals}       color="text-white" />
        <StatBox icon={TrendingUp} label="Win Rate"       value={`${overall.win_rate}%`}       color="text-long" />
        <StatBox icon={Target}     label="Winning"        value={overall.winning}               color="text-long" />
        <StatBox icon={Trophy}     label="Losing"         value={overall.losing}                color="text-short" />
      </div>

      {/* Win / Loss Streaks */}
      {streaks.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Current Streaks</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
            {streaks.map(s => {
              const isWin = s.streak_type === 'win'
              return (
                <div
                  key={s.symbol}
                  className={cn(
                    'rounded-xl border p-4 text-center',
                    isWin ? 'bg-long/5 border-long/20' : 'bg-short/5 border-short/20',
                  )}
                >
                  <div className="text-xs font-bold text-white mb-1">{s.symbol}</div>
                  <div className={cn('text-2xl font-bold font-mono', isWin ? 'text-long' : 'text-short')}>
                    {s.count}
                  </div>
                  <div className={cn('flex items-center justify-center gap-1 text-[10px] font-semibold mt-1', isWin ? 'text-long' : 'text-short')}>
                    {isWin ? <Flame className="w-3 h-3" /> : <Snowflake className="w-3 h-3" />}
                    {isWin ? 'WIN STREAK' : 'LOSS STREAK'}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Win rate chart */}
      {chartData.length > 0 && (
        <div className="bg-surface-card border border-surface-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-5">Win Rate by Symbol</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} barSize={32}>
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#6b7280', fontSize: 12 }} />
              <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: '#6b7280', fontSize: 11 }}
                tickFormatter={v => `${v}%`} />
              <Tooltip
                contentStyle={{ background: '#16161f', border: '1px solid #2a2a3a', borderRadius: 8, color: '#fff' }}
                formatter={(v: any) => [`${v.toFixed(1)}%`, 'Win Rate']}
              />
              <Bar dataKey="winRate" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.winRate >= 60 ? '#22c55e' : entry.winRate >= 50 ? '#eab308' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Per-symbol table */}
      <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
        <div className="p-4 border-b border-surface-border">
          <h2 className="text-sm font-semibold text-white">Performance Breakdown</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase tracking-wider">
                <th className="px-4 py-3 text-left">Symbol</th>
                <th className="px-4 py-3 text-right">Signals</th>
                <th className="px-4 py-3 text-right">Win Rate</th>
                <th className="px-4 py-3 text-right">Avg PnL</th>
                <th className="px-4 py-3 text-right">Best</th>
                <th className="px-4 py-3 text-right">Worst</th>
                <th className="px-4 py-3 text-right">Avg Confidence</th>
              </tr>
            </thead>
            <tbody>
              {by_symbol.map((s, i) => {
                // Find current streak for this symbol
                const streak = streaks.find(st => st.symbol === s.symbol)
                return (
                  <tr key={s.symbol} className={cn('border-t border-surface-border hover:bg-surface-elevated transition-colors',
                    i % 2 === 0 ? '' : 'bg-surface-elevated/30')}>
                    <td className="px-4 py-3 font-bold text-white">
                      <div className="flex items-center gap-2">
                        {s.symbol}
                        {streak && streak.count >= 2 && (
                          <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded',
                            streak.streak_type === 'win' ? 'bg-long/10 text-long' : 'bg-short/10 text-short')}>
                            {streak.streak_type === 'win' ? '🔥' : '❄️'} {streak.count}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-300 font-mono">{s.total}</td>
                    <td className="px-4 py-3 text-right font-mono font-bold">
                      <span className={s.win_rate >= 60 ? 'text-long' : s.win_rate >= 50 ? 'text-yellow-400' : 'text-short'}>
                        {s.win_rate.toFixed(1)}%
                      </span>
                    </td>
                    <td className={cn('px-4 py-3 text-right font-mono', s.avg_pnl_pct >= 0 ? 'text-long' : 'text-short')}>
                      {s.avg_pnl_pct >= 0 ? '+' : ''}{s.avg_pnl_pct.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-long">+{s.best_pnl_pct.toFixed(2)}%</td>
                    <td className="px-4 py-3 text-right font-mono text-short">{s.worst_pnl_pct.toFixed(2)}%</td>
                    <td className="px-4 py-3 text-right font-mono text-gray-300">{s.avg_confidence.toFixed(0)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-gray-600 text-center">
        All past performance is for reference only. Not financial advice.
        Signal outcomes are determined by price hitting TP1, TP2, or SL within the 24h validity window.
      </p>
    </div>
  )
}

function StatBox({ icon: Icon, label, value, color }: { icon: any; label: string; value: any; color: string }) {
  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-4 flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-surface-elevated flex items-center justify-center">
        <Icon className={cn('w-4 h-4', color)} />
      </div>
      <div>
        <div className={cn('text-xl font-bold font-mono', color)}>{value}</div>
        <div className="text-[11px] text-gray-500">{label}</div>
      </div>
    </div>
  )
}
