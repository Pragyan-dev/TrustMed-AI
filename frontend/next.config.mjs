import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const d3SelectionPath = path.join(__dirname, 'node_modules', 'd3-zoom', 'node_modules', 'd3-selection')
const d3TransitionPath = path.join(__dirname, 'node_modules', 'd3-zoom', 'node_modules', 'd3-transition')

/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack(config) {
    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      'd3-selection': d3SelectionPath,
      'd3-transition': d3TransitionPath,
    }

    return config
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ]
  },
}

export default nextConfig
