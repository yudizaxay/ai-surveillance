import { createLogger, defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies API + WebSocket to the FastAPI backend.
const api = process.env.VITE_API ?? 'http://127.0.0.1:8000'

// A closed tab, a reload, or a backend restart breaks proxied sockets mid-write. That is normal in development,
// but Vite prints each one as a long "ws proxy socket error: write EPIPE" stack trace. Drop only those expected
// network errors from the log (the dashboard reconnects on its own); every other error is still printed.
const logger = createLogger()
const loggerError = logger.error
logger.error = (msg, options) => {
  if (/(?:ws|http) proxy (?:socket )?error/.test(msg) && /EPIPE|ECONNRESET|ECONNREFUSED|ERR_STREAM/.test(msg)) return
  loggerError(msg, options)
}

export default defineConfig({
  plugins: [react()],
  customLogger: logger,
  server: {
    port: Number(process.env.VITE_PORT ?? 5173),
    proxy: {
      '/api': api,
      '/ws': { target: api.replace(/^http/, 'ws'), ws: true },
    },
  },
})
