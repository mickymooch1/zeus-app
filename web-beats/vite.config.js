import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';

// Reads src/sw.js, stamps __SW_VERSION__ with the current build timestamp,
// and emits sw.js to the root of the build output.
const serviceWorkerPlugin = {
  name: 'zeus-service-worker',
  generateBundle() {
    const template = fs.readFileSync(path.resolve('./src/sw.js'), 'utf-8');
    const versioned = template.replace('__SW_VERSION__', `v${Date.now()}`);
    this.emitFile({ type: 'asset', fileName: 'sw.js', source: versioned });
  },
  // In dev, serve a no-op SW so /sw.js doesn't 404
  configureServer(server) {
    server.middlewares.use('/sw.js', (_req, res) => {
      res.setHeader('Content-Type', 'application/javascript; charset=utf-8');
      res.end('// development — service worker disabled');
    });
  },
};

export default defineConfig({
  plugins: [react(), serviceWorkerPlugin],
  build: {
    outDir: '../web-beats-dist',
    assetsDir: 'assets-beats',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (/[\\/]node_modules[\\/](react|react-dom|react-router-dom|scheduler)[\\/]/.test(id)) {
            return 'vendor';
          }
          if (/[\\/]node_modules[\\/](i18next|react-i18next|i18next-browser-languagedetector)[\\/]/.test(id)) {
            return 'i18n';
          }
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/billing': 'http://localhost:8000',
      '/files': 'http://localhost:8000',
    },
  },
});
