import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Keep large, rarely changing libraries in their own cached chunks.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router'],
          i18n: ['i18next', 'react-i18next'],
          icons: ['lucide-react'],
        },
      },
    },
  },
  server: {
    port: 5173,
    // Same-origin API calls to the local Django backend (uvicorn on port 8000), mirroring
    // what Caddy does in deployment, so no CORS config is needed. Only used when
    // VITE_USE_MOCKS=false. 127.0.0.1, not localhost, avoids IPv6 lookups on Windows.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
});
