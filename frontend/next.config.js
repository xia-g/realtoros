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
        destination: 'http://192.168.1.114:8090/api/v1/:path*',
      },
    ]
  },
}
module.exports = nextConfig
