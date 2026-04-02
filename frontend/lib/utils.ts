import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { Direction } from './types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatPrice(price: number, symbol?: string): string {
  if (!price) return '$0.00'
  if (symbol === 'BTC' || price > 10000) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(price)
  }
  if (price > 100) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 3 }).format(price)
  }
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(price)
}

export function formatLargeNumber(n: number | null | undefined): string {
  if (n == null) return 'N/A'
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`
  return `$${n.toFixed(0)}`
}

export function formatFundingRate(rate: number | null | undefined): string {
  if (rate == null) return 'N/A'
  const pct = rate * 100
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(4)}%`
}

export function formatPct(n: number | null | undefined, decimals = 2): string {
  if (n == null) return 'N/A'
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(decimals)}%`
}

export function getDirectionColor(direction: Direction): string {
  if (direction === 'LONG') return 'text-long'
  if (direction === 'SHORT') return 'text-short'
  return 'text-gray-400'
}

export function getDirectionBg(direction: Direction): string {
  if (direction === 'LONG') return 'bg-long/10 border-long/30'
  if (direction === 'SHORT') return 'bg-short/10 border-short/30'
  return 'bg-gray-800/50 border-gray-700'
}

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 85) return 'text-green-400'
  if (confidence >= 70) return 'text-yellow-400'
  return 'text-gray-400'
}

export function getConfidenceLabel(confidence: number): string {
  if (confidence >= 90) return 'VERY HIGH'
  if (confidence >= 80) return 'HIGH'
  if (confidence >= 70) return 'MODERATE'
  return 'LOW'
}

export function timeAgo(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = (now.getTime() - date.getTime()) / 1000
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export function generateTweetText(signal: import('./types').Signal): string {
  const dir    = signal.direction === 'LONG' ? '🟢 LONG' : '🔴 SHORT'
  const entry  = formatPrice(signal.entry_price, signal.symbol)
  const tp1    = formatPrice(signal.take_profit_1, signal.symbol)
  const tp2    = formatPrice(signal.take_profit_2, signal.symbol)
  const sl     = formatPrice(signal.stop_loss, signal.symbol)
  const conf   = signal.confidence
  const confLabel = conf >= 90 ? '🔥 VERY HIGH' : conf >= 80 ? '💪 HIGH' : '✅ GOOD'
  return encodeURIComponent(
    `⚡ ${signal.symbol}/USDC ${dir} Signal\n\n` +
    `Confidence: ${conf}/100 — ${confLabel}\n` +
    `Entry zone: ~${entry}\n` +
    `TP1: ${tp1} · TP2: ${tp2}\n` +
    `SL:  ${sl}\n\n` +
    `Powered by @EOLASProtocol signal engine.\n` +
    `Trade it on EOLAS Perps 👇\n` +
    `${signal.eolas_url ?? 'https://perps.eolas.fun'}\n\n` +
    `#EOLAS #DeFi #CryptoSignals #${signal.symbol}`
  )
}
