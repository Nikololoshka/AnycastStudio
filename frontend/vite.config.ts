import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const BACKEND = 'http://127.0.0.1:8000';

export default defineConfig(() => ({
  plugins: [react(), tailwindcss()],
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.0.0'),
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    // Same origin for the SPA and the API: the session cookie and the CSRF
    // token work without CORS, and the OAuth redirect lands here.
    proxy: {
      '/api': { target: BACKEND, changeOrigin: false },
      '/admin': { target: BACKEND, changeOrigin: false },
      // The admin's stylesheets. Without this Vite answers with index.html and
      // the admin renders unstyled.
      '/static': { target: BACKEND, changeOrigin: false },
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
}));
