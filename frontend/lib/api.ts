const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    next: { revalidate: 0 },
  })
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`)
  }
  return res.json()
}

export const api = {
  signals: {
    list: (params?: { symbol?: string; status?: string; limit?: number }) =>
      apiFetch<{ signals: import('./types').Signal[] }>(`/signals?${new URLSearchParams(params as any)}`),
    active: () => apiFetch<{ signals: import('./types').Signal[] }>('/signals/active'),
    latest: (limit = 10) => apiFetch<{ signals: import('./types').Signal[] }>(`/signals/latest?limit=${limit}`),
    live: () => apiFetch<{ signals: import('./types').LiveSignal[]; data_age_seconds: number }>('/signals/live'),
    get: (id: string) => apiFetch<import('./types').Signal>(`/signals/${id}`),
  },
  markets: {
    list: () => apiFetch<{ markets: import('./types').MarketData[] }>('/markets'),
    get: (symbol: string) => apiFetch<import('./types').MarketData>(`/markets/${symbol}`),
    supported: () => apiFetch<{ symbols: string[] }>('/markets/supported/list'),
  },
  analytics: {
    performance: () => apiFetch<import('./types').PerformanceStats>('/analytics/performance'),
    history: (days = 30, symbol?: string) =>
      apiFetch<{ signals: import('./types').Signal[] }>(`/analytics/history?days=${days}${symbol ? `&symbol=${symbol}` : ''}`),
    leaderboard: () => apiFetch<{ leaderboard: any[] }>('/analytics/leaderboard'),
    summary: () => apiFetch<{
      total_signals: number
      winning_signals: number
      active_signals: number
      win_rate: number
      supported_markets: number
    }>('/analytics/stats/summary'),
  },
  health: () => apiFetch<{ status: string; data_age_seconds: number }>('/health'),
}
