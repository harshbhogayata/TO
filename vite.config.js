import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import fs from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // Inject build timestamp into service worker for cache busting
    {
      name: 'sw-version',
      writeBundle() {
        const swPath = resolve(__dirname, 'dist/sw.js');
        if (fs.existsSync(swPath)) {
          const version = Date.now().toString(36);
          let content = fs.readFileSync(swPath, 'utf-8');
          content = content.replace('__SW_VERSION__', version);
          fs.writeFileSync(swPath, content);
        }
      },
    },
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: [],
  },
})
