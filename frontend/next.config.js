/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: (process.env.NEXT_PUBLIC_API_URL || '').trim() ||
      (process.env.NODE_ENV === 'production'
        ? 'https://doctor-voice-pro-backend.fly.dev'
        : 'http://localhost:8000'),
  },
}

module.exports = nextConfig
