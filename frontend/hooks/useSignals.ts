'use client'
import useSWR from 'swr'
import { api } from '@/lib/api'
import type { Signal, MarketData, LiveSignal } from '@/lib/types'

const fetcher = (fn: () => Promise<any>) => fn()

function isSignalExpired(signal: LiveSignal): boolean {
  if (signal.status === 'EXPIRED') return true
  if (signal.expires_at && new Date(signal.expires_at) < new Date()) return true
  return false
}

export function useLiveSignals() {
  const { data, error, isLoading } = useSWR(
    'signals/live',
    () => api.signals.live(),
    { refreshInterval: 15_000, revalidateOnFocus: true }
  )
  const allSignals = (data?.signals ?? []) as LiveSignal[]
  return {
    signals: allSignals.filter(s => !isSignalExpired(s)),
    dataAge: data?.data_age_seconds ?? null,
    error,
    isLoading,
  }
}

export function useActiveSignals() {
  const { data, error, isLoading, mutate } = useSWR(
    'signals/active',
    () => api.signals.active(),
    { refreshInterval: 30_000 }
  )
  return {
    signals: (data?.signals ?? []) as Signal[],
    error,
    isLoading,
    refresh: mutate,
  }
}

export function useLatestSignals(limit = 20) {
  const { data, error, isLoading } = useSWR(
    `signals/latest/${limit}`,
    () => api.signals.latest(limit),
    { refreshInterval: 60_000 }
  )
  return {
    signals: (data?.signals ?? []) as Signal[],
    error,
    isLoading,
  }
}

export function useMarkets() {
  const { data, error, isLoading } = useSWR(
    'markets',
    () => api.markets.list(),
    { refreshInterval: 10_000 }
  )
  return {
    markets: (data?.markets ?? []) as MarketData[],
    error,
    isLoading,
  }
}

export function useSummaryStats() {
  const { data, error, isLoading } = useSWR(
    'analytics/summary',
    () => api.analytics.summary(),
    { refreshInterval: 120_000 }
  )
  return { stats: data, error, isLoading }
}

export function usePerformance() {
  const { data, error, isLoading } = useSWR(
    'analytics/performance',
    () => api.analytics.performance(),
    { refreshInterval: 300_000 }
  )
  return { performance: data, error, isLoading }
}

export function useStreaks() {
  const { data, error, isLoading } = useSWR(
    'analytics/streaks',
    () => api.analytics.streaks(),
    { refreshInterval: 300_000 }
  )
  return { streaks: (data?.streaks ?? []) as import('../lib/types').SymbolStreak[], error, isLoading }
}
