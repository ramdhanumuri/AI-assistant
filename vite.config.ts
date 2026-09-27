import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 12000,
    strictPort: false,
    allowedHosts: ['.prod-runtime.all-hands.dev', 'localhost'],
    /* Forward the API to the FastAPI backend so the browser only ever talks to
       one origin. That is what lets the session cookies stay first-party and
       SameSite=Lax — pointing the SPA at :12001 directly would make every
       request cross-site and force SameSite=None + Secure. */
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:12001',
        changeOrigin: false,
      },
    },
  },
  build: {
    target: 'es2020',
    sourcemap: false,
  },
});