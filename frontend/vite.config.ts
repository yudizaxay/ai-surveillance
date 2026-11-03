import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies API + WebSocket to the FastAPI backend.
const api = process.env.VITE_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.VITE_PORT ?? 5173),
    proxy: {
      '/api': api,
      '/ws': { target: api.replace(/^http/, 'ws'), ws: true },
    },
  },
})
