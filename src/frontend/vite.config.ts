import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  test: { include: ['api/**/*.test.ts', 'tests/**/*.test.{ts,tsx}'] },
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      ['/health', '/sessions', '/catalog', '/requirements', '/comparisons', '/history'].map(
        (path) => [
          path,
          { target: process.env.BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true },
        ],
      ),
    ),
  },
});
