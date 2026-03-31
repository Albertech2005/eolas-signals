export type Direction = 'LONG' | 'SHORT' | 'NO_TRADE'
export type SignalStatus = 'ACTIVE' | 'HIT_TP1' | 'HIT_TP2' | 'HIT_SL' | 'EXPIRED'

export interface ScoreBreakdown {
  oi_divergence: number
  funding_rate: number
  liquidation: number
  momentum: number
  volatility: number
  total?: number
}

export interface Signal {
  id: string
  symbol: string
  direction: Direction
  confidence: number
  entry_price: number
  stop_loss: number
  take_profit_1: number
  take_profit_2: number
  scores: ScoreBreakdown
  reasons: string[]
  eolas_url: string | null
  status: SignalStatus
  pnl_pct: number | null
  is_winner: boolean | null
  created_at: string
  expires_at: string | null
  is_actionable?: boolean
}

export interface MarketData {
  symbol: string
  price: number
  price_change_1h: number | null
  price_change_4h: number | null
  price_change_24h: number | null
  volume_24h: number | null
  open_interest: number | null
  oi_change_1h: number | null
  funding_rate: number | null
  long_liquidations_1h: number | null
  short_liquidations_1h: number | null
  long_short_ratio: number | null
  eolas_long_url: string
  eolas_short_url: string
  updated_at: string | null
}

export interface PerformanceStats {
  overall: {
    total_signals: number
    winning: number
    losing: number
    win_rate: number
  }
  by_symbol: {
    symbol: string
    total: number
    wins: number
    losses: number
    win_rate: number
    avg_confidence: number
    avg_pnl_pct: number
    best_pnl_pct: number
    worst_pnl_pct: number
  }[]
}

export interface LiveSignal {
  symbol: string
  direction: Direction
  confidence: number
  entry_price: number
  stop_loss?: number
  take_profit_1?: number
  take_profit_2?: number
  reasons?: string[]
  status?: SignalStatus
  pnl_pct?: number | null
  is_winner?: boolean | null
  created_at?: string
  expires_at?: string | null
  eolas_url: string | null
  is_actionable: boolean
  scores: ScoreBreakdown
}
