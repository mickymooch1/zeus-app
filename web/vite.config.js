import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/sessions': 'http://localhost:8000',
      '/history': 'http://localhost:8000',
      '/tunnel-url': 'http://localhost:8000',
    },
  },
})
