'use client'
import { ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Direction } from '@/lib/types'

interface TradeButtonProps {
  url: string
  direction: Direction
  symbol: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
  onClick?: () => void
}

export function TradeButton({ url, direction, symbol, size = 'md', className, onClick }: TradeButtonProps) {
  const isLong = direction === 'LONG'

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  }

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-2 font-bold rounded-lg transition-all duration-150',
        'border shadow-lg active:scale-95 cursor-pointer',
        isLong
          ? 'bg-long/15 border-long/40 text-long hover:bg-long hover:text-white hover:shadow-long/30 hover:shadow-lg'
          : 'bg-short/15 border-short/40 text-short hover:bg-short hover:text-white hover:shadow-short/30 hover:shadow-lg',
        sizeClasses[size],
        className,
      )}
    >
      <ExternalLink className={size === 'sm' ? 'w-3 h-3' : 'w-4 h-4'} />
      Trade {symbol} {isLong ? 'LONG' : 'SHORT'} on EOLAS
    </a>
  )
}

export function TradeButtonFull({
  url,
  direction,
  symbol,
  className,
}: Omit<TradeButtonProps, 'size'>) {
  const isLong = direction === 'LONG'

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        'flex items-center justify-center gap-3 w-full px-6 py-4 rounded-xl font-bold text-base',
        'border-2 transition-all duration-150 active:scale-98',
        'shadow-xl cursor-pointer',
        isLong
          ? 'bg-long text-white border-long/50 hover:bg-long-dark hover:shadow-long/40 hover:shadow-2xl'
          : 'bg-short text-white border-short/50 hover:bg-short-dark hover:shadow-short/40 hover:shadow-2xl',
        className,
      )}
    >
      <ExternalLink className="w-5 h-5" />
      <span>{isLong ? '🟢' : '🔴'} Trade {symbol} {isLong ? 'LONG' : 'SHORT'} on EOLAS DEX</span>
    </a>
  )
}
