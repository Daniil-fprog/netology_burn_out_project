import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // по умолчанию: npm run dev → mock, npm run build → real
  const apiMode = (env.VITE_API_MODE || (command === 'serve' ? 'mock' : 'real')) === 'mock' ? 'mock' : 'real';
  return {
  define: { __API_MODE__: JSON.stringify(apiMode) },
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: { '/api': 'http://localhost:8000', '/users': 'http://localhost:8000' },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          query: ['@tanstack/react-query'],
        },
      },
    },
  },
};
});
