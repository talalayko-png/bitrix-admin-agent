import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, proxy API/webhook calls to the FastAPI backend so the SPA can use
// same-origin relative URLs (VITE_API_BASE empty).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/webhooks': 'http://localhost:8000',
    },
  },
})
