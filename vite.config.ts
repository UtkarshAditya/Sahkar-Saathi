import { fileURLToPath, URL } from 'node:url';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const backend = 'http://127.0.0.1:8000'; // 127.0.0.1, not localhost: avoids IPv6 lookups on Windows

  return {
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
      // Same routing as Caddy in Docker: /api, /admin and /static go to Django on one origin,
      // so no CORS config is needed. In mock mode there is no backend, and /admin stays the
      // React overview page.
      proxy:
        env.VITE_USE_MOCKS === 'true'
          ? undefined
          : { '/api': backend, '/admin': backend, '/static': backend },
    },
  };
});
