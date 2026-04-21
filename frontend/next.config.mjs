/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
      {
        source: '/uploads/:path*',
        destination: 'http://localhost:8000/uploads/:path*',
      },
      {
        source: '/data/:path*',
        destination: 'http://localhost:8000/data/:path*',
      },
    ]
  },
}

export default nextConfig
