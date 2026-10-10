import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  test: {
    include: [
      'src/shared/**/*.test.ts',
      'src/entities/**/*.test.ts',
      'src/features/**/*.test.{ts,tsx}',
      'src/pages/**/*.test.{ts,tsx}',
      'tests/**/*.test.{ts,tsx}',
    ],
  },
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
