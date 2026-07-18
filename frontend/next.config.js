/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  trailingSlash: true,
  env: {
    NEXT_PUBLIC_API_URL: '',
    NEXT_PUBLIC_WS_URL: '',
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://127.0.0.1:8090/api/v1/:path*',
      },
    ]
  },
}
module.exports = nextConfig
