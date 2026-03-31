import type { Metadata } from 'next'
import './globals.css'
import { Header } from '@/components/layout/Header'

export const metadata: Metadata = {
  title: 'EOLAS Signals — Perpetual Trading Intelligence',
  description: 'High-confidence perpetual trading signals powered by real-time market data. Trade on EOLAS DEX.',
  icons: {
    icon: '/favicon.jpg',
  },
  openGraph: {
    title: 'EOLAS Signals',
    description: 'High-confidence perpetual trading signals. Trade on EOLAS DEX.',
    type: 'website',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-surface text-white antialiased">
        <Header />
        <main className="max-w-7xl mx-auto px-4 py-6">
          {children}
        </main>
        <footer className="border-t border-surface-border mt-16 py-6">
          <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-600">
            <span>⚡ EOLAS Signals — Not financial advice. Trade responsibly.</span>
            <a href={process.env.NEXT_PUBLIC_EOLAS_URL ?? 'https://perps.eolas.fun'}
               target="_blank" rel="noopener noreferrer"
               className="text-brand hover:text-brand-light transition-colors">
              perps.eolas.fun ↗
            </a>
          </div>
        </footer>
      </body>
    </html>
  )
}
