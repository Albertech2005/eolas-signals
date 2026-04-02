/** @type {import('next').NextConfig} */
const nextConfig = {
  // 'standalone' is for Docker/Node deployments only — breaks Vercel client-side routing
  ...(process.env.BUILD_STANDALONE === 'true' && { output: 'standalone' }),
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
    NEXT_PUBLIC_EOLAS_URL: process.env.NEXT_PUBLIC_EOLAS_URL || 'https://perps.eolas.fun',
  },
}

module.exports = nextConfig
