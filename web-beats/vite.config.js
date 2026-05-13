import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../web-beats-dist',
    assetsDir: 'assets-beats',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/billing': 'http://localhost:8000',
      '/files': 'http://localhost:8000',
    },
  },
})
