// SPDX-License-Identifier: GPL-3.0-or-later
import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:4173/slot-otter/',
    viewport: { width: 1440, height: 1100 },
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
      args: ['--no-sandbox', '--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
    },
  },
  webServer: { command: 'npm run preview -- --port 4173 --base=/slot-otter/', url: 'http://127.0.0.1:4173/slot-otter/', reuseExistingServer: !process.env.CI },
});
