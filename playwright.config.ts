import { defineConfig, devices } from "@playwright/test";

/**
 * TenderIQ E2E — Faz 3 çıkış kapısı: incele → onayla → export uçtan uca (Playwright).
 *
 * Ön koşullar (ayrık test-runner; normal `pnpm test`/`vitest`'e karışmaz):
 *   1. Tam yığın ayakta:            pnpm up            (docker compose)
 *   2. Deterministik veri tohumla:  pnpm e2e:seed      (scripts/seed_e2e.py)
 *   3. Runner + tarayıcı (bir kez): pnpm add -Dw @playwright/test
 *                                   pnpm exec playwright install chromium
 *   4. Koştur:                      pnpm test:e2e
 *
 * `E2E_BASE_URL` ile hedef değiştirilebilir (varsayılan yerel web).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
