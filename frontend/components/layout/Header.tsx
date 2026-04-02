'use client'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Activity, BarChart2, Zap, Send, BookOpen } from 'lucide-react'

const NAV = [
  { href: '/',             label: 'Dashboard',    icon: Activity  },
  { href: '/signals',      label: 'Signals',      icon: Zap       },
  { href: '/analytics',    label: 'Analytics',    icon: BarChart2 },
  { href: '/how-it-works', label: 'Guide', icon: BookOpen  },
]

export function Header() {
  const path = usePathname()

  return (
    <header className="sticky top-0 z-50 border-b border-surface-border bg-surface/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 group">
          <Image src="/eolas-logo.jpg" alt="EOLAS" width={32} height={32} className="rounded-lg" />
          <div className="leading-none">
            <span className="font-bold text-white text-sm">EOLAS</span>
            <span className="text-brand text-sm font-bold"> Signals</span>
          </div>
        </Link>

        {/* Nav */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors',
                path === href
                  ? 'bg-brand/15 text-brand'
                  : 'text-gray-400 hover:text-white hover:bg-surface-elevated',
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </Link>
          ))}
        </nav>

        {/* CTA */}
        <div className="flex items-center gap-3">
          <a
            href={process.env.NEXT_PUBLIC_TELEGRAM_CHANNEL ?? '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-300 hover:text-white border border-surface-border hover:border-gray-500 rounded-lg transition-colors"
          >
            <Send className="w-3.5 h-3.5" />
            Telegram Alerts
          </a>
          <a
            href={process.env.NEXT_PUBLIC_EOLAS_URL ?? 'https://perps.eolas.fun'}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors"
          >
            Trade on EOLAS
          </a>
        </div>
      </div>

      {/* Mobile nav */}
      <div className="md:hidden flex border-t border-surface-border">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] transition-colors',
              path === href ? 'text-brand' : 'text-gray-500',
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Link>
        ))}
      </div>
    </header>
  )
}
