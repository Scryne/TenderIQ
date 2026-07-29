import { defineConfig, devices } from "@playwright/test";

/**
 * TenderIQ E2E — tarayıcı katmanı, CI'da koşar.
 *
 * ## İki yığın, çünkü kayıt modu SUNUCU seviyesindedir
 *
 * `SIGNUP_MODE` bir ortam değişkenidir ve istek başına değiştirilemez. Bekleme
 * listesi modunu tarayıcıdan sınamanın tek dürüst yolu, o modda çalışan ayrı bir
 * yığın kaldırmak: "açık kayıt" (:8100/:3100) ve "bekleme listesi"
 * (:8101/:3101). Alternatif — modu istemciden taklit etmek — tam olarak sınamak
 * istediğimiz şeyi (sunucunun kararını) atlardı.
 *
 * Next **bir kez** derlenir; iki `next start` aynı derlemeyi farklı `API_URL`
 * ile sunar (sunucu tarafı env çalışma anında okunur).
 *
 * ## Dış servise çıkış YOK
 *
 * `EMAIL_PROVIDER=memory` ve `BILLING_PROVIDER=fake` **sabitlenir**. `.env`
 * geliştirici makinesinde gerçek bir sağlayıcı (resend/iyzico) seçiyor olabilir;
 * sabitlemeseydik E2E gerçek e-posta gönderir ve gerçek ödeme ağ geçidine
 * çıkardı. Doğrulama bağlantısı `/_test/inbox` ucundan okunur (yalnız memory
 * sağlayıcısında ve production dışında açıktır).
 *
 * ## Determinizm
 *
 * Sabit `sleep` yok; beklemeler ya Playwright'ın otomatik `expect` beklemesi ya
 * da `waitForURL`/yanıt bekleme gibi belirleyici sinyaller. Kimlikler her koşuda
 * benzersiz üretilir (`e2e/support/identity.ts`) — aksi hâlde ikinci koşu
 * "e-posta zaten kayıtlı" ile düşerdi ve test yanlış şeyi ölçerdi.
 *
 * ## Yerel koşum
 *
 *   docker compose -f infra/compose/docker-compose.yml up -d postgres redis
 *   uv run alembic upgrade head
 *   pnpm --filter @tenderiq/web build
 *   pnpm test:e2e
 */

const API_OPEN = process.env.E2E_API_OPEN ?? "http://127.0.0.1:8100";
const API_WAITLIST = process.env.E2E_API_WAITLIST ?? "http://127.0.0.1:8101";
const WEB_OPEN = process.env.E2E_WEB_OPEN ?? "http://127.0.0.1:3100";
const WEB_WAITLIST = process.env.E2E_WEB_WAITLIST ?? "http://127.0.0.1:3101";

/** Her iki API örneğinin paylaştığı, dışa çıkışı kapatan ortam. */
const apiEnv: Record<string, string> = {
  EMAIL_PROVIDER: "memory",
  BILLING_PROVIDER: "fake",
  BILLING_WEBHOOK_SECRET: "e2e-webhook-secret",
  BILLING_ENV: "sandbox",
  ENVIRONMENT: "development",
  AUTH_SECRET: "e2e-auth-secret-en-az-otuz-iki-karakter-uzunlugunda",
  REQUIRE_VERIFIED_EMAIL: "true",
  DATABASE_URL:
    process.env.DATABASE_URL ??
    // RLS'ye TABİ uygulama rolü (owner değil): E2E, üretimdeki ile aynı
    // yetkilerle koşmalı — owner rolüyle koşan bir E2E, politikaların
    // gerçekten çalıştığını kanıtlamaz.
    "postgresql+psycopg://tenderiq_app:tenderiq_app@localhost:5432/tenderiq",
  REDIS_URL: process.env.REDIS_URL ?? "redis://localhost:6379/0",
};

/**
 * `--reload` bilinçli: Windows'ta uvicorn reload'suz `ProactorEventLoop`
 * kullanıyor ve async psycopg onunla çalışmıyor (her DB isteği 500 verir).
 * CI (Linux) etkilenmez; tek komut iki ortamda da çalışsın diye açık bırakıldı.
 */
function apiServer(port: number, signupMode: string) {
  return {
    command: `uv run uvicorn tenderiq_api.main:app --host 127.0.0.1 --port ${port} --reload`,
    url: `http://127.0.0.1:${port}/healthz`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { ...apiEnv, SIGNUP_MODE: signupMode },
  };
}

function webServer(port: number, apiUrl: string) {
  return {
    command: `pnpm --filter @tenderiq/web start --port ${port}`,
    url: `http://127.0.0.1:${port}/login`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: { API_URL: apiUrl, PORT: String(port) },
  };
}

export default defineConfig({
  testDir: "./e2e",
  // Koşu öncesi oran-sınırı sayaçlarını temizler; sebebi orada yazılı.
  globalSetup: "./e2e/support/global-setup.ts",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  // Paralel koşmuyor: iki yığın tek Postgres'i paylaşıyor ve eşzamanlılık,
  // testlerin birbirinin kotasını/kuyruğunu görmesine yol açabilir. E2E sayısı
  // azdır; determinizm hızdan önce gelir.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["github"]] : [["list"]],
  use: { trace: "on-first-retry", screenshot: "only-on-failure" },
  webServer: [
    apiServer(8100, "open"),
    apiServer(8101, "waitlist"),
    webServer(3100, API_OPEN),
    webServer(3101, API_WAITLIST),
  ],
  projects: [
    {
      name: "acik-kayit",
      use: { ...devices["Desktop Chrome"], baseURL: WEB_OPEN },
      testIgnore: /waitlist\.spec\.ts/,
    },
    {
      name: "bekleme-listesi",
      use: { ...devices["Desktop Chrome"], baseURL: WEB_WAITLIST },
      testMatch: /waitlist\.spec\.ts/,
    },
  ],
});
