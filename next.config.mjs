/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
        ],
      },
    ]
  },
  async rewrites() {
    return [
      { source: "/", destination: "/index.html" },
      { source: "/login", destination: "/index.html" },
      { source: "/home", destination: "/home.html" },
      { source: "/game", destination: "/game.html" },
      { source: "/payment", destination: "/payment.html" },
      { source: "/profile", destination: "/profile.html" },
      { source: "/telegram-verify", destination: "/telegram-verify.html" },
      { source: "/game-link", destination: "/game-link.html" },
    ]
  },
}

export default nextConfig
