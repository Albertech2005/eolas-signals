/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#6366f1',
          dark: '#4f46e5',
          light: '#818cf8',
        },
        long: {
          DEFAULT: '#22c55e',
          dark: '#16a34a',
          bg: '#052e16',
          border: '#166534',
        },
        short: {
          DEFAULT: '#ef4444',
          dark: '#dc2626',
          bg: '#2d0000',
          border: '#7f1d1d',
        },
        surface: {
          DEFAULT: '#0f0f14',
          card: '#16161f',
          elevated: '#1e1e2a',
          border: '#2a2a3a',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(99,102,241,0.3)' },
          '100%': { boxShadow: '0 0 20px rgba(99,102,241,0.7)' },
        },
        slideIn: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
