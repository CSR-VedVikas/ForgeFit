import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // listen on 0.0.0.0 so phones on same Wi‑Fi can connect
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
})
