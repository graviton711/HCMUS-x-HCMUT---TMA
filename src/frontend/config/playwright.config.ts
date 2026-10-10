import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '../tests',
  testMatch: 'e2e.spec.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 8000 },
  outputDir: '../../../artifacts/frontend/playwright',
  reporter: [
    ['list'],
    ['json', { outputFile: '../../../artifacts/frontend/playwright-report.json' }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173',
    browserName: 'chromium',
    launchOptions: {
      executablePath:
        process.env.PLAYWRIGHT_CHROME_PATH ??
        (process.platform === 'win32'
          ? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
          : undefined),
    },
    headless: true,
    viewport: { width: 1440, height: 960 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
