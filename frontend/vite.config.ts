import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  css: {
    postcss: `${import.meta.dirname}/postcss.config.js`,
  },
  resolve: {
    alias: {
      '@': `${import.meta.dirname}/src`,
    },
  },
  server: {
    port: 5174,
    host: true,
    proxy: {
      // /api/v1/... → http://localhost:8001/v1/...
      // (strips the /api prefix, keeps /v1/... intact)
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8001',
        changeOrigin: true,
        ws: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})