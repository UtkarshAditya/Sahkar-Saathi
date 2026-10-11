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
    // When the Django backend runs locally, uncomment to proxy API calls
    // (mirrors what Caddy does in the deployed setup, so no CORS config is needed).
    // proxy: { '/api': 'http://localhost:8000' },
  },
});
