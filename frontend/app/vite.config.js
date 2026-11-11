import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    // для VITE_API_MODE=real: запросы идут на локальный backend
    proxy: { '/api': 'http://localhost:8000', '/users': 'http://localhost:8000' },
  },
  build: {
    rollupOptions: {
      output: {
        // крупные библиотеки — отдельными чанками, чтобы кэшировались между релизами
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          query: ['@tanstack/react-query'],
        },
      },
    },
  },
});
