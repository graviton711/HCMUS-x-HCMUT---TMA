import { defineConfig } from 'vitest/config';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  test: {
    include: [
      'src/shared/**/*.test.ts',
      'src/entities/**/*.test.ts',
      'src/features/**/*.test.{ts,tsx}',
      'src/pages/**/*.test.{ts,tsx}',
      'tests/**/*.test.{ts,tsx}',
      'scripts/**/*.test.mjs',
    ],
  },
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      ['/health', '/sessions', '/catalog', '/requirements', '/comparisons', '/history', '/agent'].map(
        (path) => [
          path,
          { target: process.env.BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true },
        ],
      ),
    ),
  },
});
