/**
 * Lighthouse erişilebilirlik ölçümü — tüm rotalar, tek komut.
 *
 * **Neden bir betik.** `chrome-devtools` MCP bu projede kurulu değil (bkz.
 * CLAUDE.md); Lighthouse'u elle 15 kez koşturmak hem yavaş hem de skorların
 * hangi yapılandırmayla alındığını belirsiz bırakıyor. Ölçümün tekrar
 * üretilebilir olması gerekiyor: DESIGN.md §12 skor eşiğini (≥95) bir görev
 * kapatma koşulu yapıyor, yani sayının nereden geldiği önemli.
 *
 * **Kimlikli sayfalar da ölçülür.** Ürünün asıl yüzeyi (`/tenders`, `/panel`,
 * `/settings`, inceleme çalışma alanı) oturum arkasındadır. Yalnız herkese açık
 * sayfaları ölçmek, erişilebilirlik borcunun büyük kısmını görmezden gelmek
 * olurdu. Oturum çerezi Playwright ile alınır ve Lighthouse'a `--extra-headers`
 * ile geçirilir.
 *
 * ## Kullanım
 *
 *   # Üretim derlemesi bir portta ayakta olmalı (dev sunucusu ÖLÇÜLMEZ:
 *   # kaynak haritaları ve HMR skoru bozar)
 *   pnpm --filter @tenderiq/web build
 *   API_URL=http://127.0.0.1:8020 pnpm --filter @tenderiq/web start --port 3200
 *
 *   node scripts/lighthouse-a11y.mjs --base http://127.0.0.1:3200
 *   node scripts/lighthouse-a11y.mjs --base http://127.0.0.1:3200 --only /usage
 *
 * Çıktı: konsola tablo + `--json <yol>` verilirse makine okunur özet.
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const LIGHTHOUSE_CLI = join(REPO_ROOT, "node_modules", "lighthouse", "cli", "index.js");

const args = process.argv.slice(2);
function arg(name, fallback = undefined) {
  const index = args.indexOf(name);
  return index === -1 ? fallback : args[index + 1];
}

const BASE = arg("--base", "http://127.0.0.1:3200");
const ONLY = arg("--only");
const JSON_OUT = arg("--json");
const CHROME_PATH = process.env.CHROME_PATH ?? chromium.executablePath();

/** Tohum betiğindeki E2E hesabı (`scripts/seed_e2e.py`). */
const SEED_EMAIL = process.env.E2E_EMAIL ?? "e2e@tenderiq-e2e.com";
const SEED_PASSWORD = process.env.E2E_PASSWORD ?? "e2e-password-123";

/** `auth: true` olanlar oturum çerezi ile ölçülür. */
const ROUTES = [
  { path: "/", auth: false },
  { path: "/login", auth: false },
  { path: "/register", auth: false },
  { path: "/forgot-password", auth: false },
  { path: "/reset-password?token=ornek", auth: false },
  { path: "/verify-email?token=ornek", auth: false },
  { path: "/accept-invitation?token=ornek", auth: false },
  { path: "/kvkk", auth: false },
  { path: "/sartlar", auth: false },
  { path: "/trust", auth: false },
  { path: "/dpa", auth: false },
  { path: "/panel", auth: true },
  { path: "/tenders", auth: true },
  { path: "/usage", auth: true },
  { path: "/settings", auth: true },
  { path: "/capability", auth: true },
];

/** Oturum açıp `Cookie` başlığı üretir. */
async function sessionCookieHeader() {
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ baseURL: BASE });
    const page = await context.newPage();
    await page.goto("/login");
    await page.getByLabel(/e-posta/i).fill(SEED_EMAIL);
    await page.getByLabel(/parola|şifre/i).fill(SEED_PASSWORD);
    await page.getByRole("button", { name: /giriş yap|oturum aç/i }).click();
    await page.waitForURL(/\/(panel|tenders)/, { timeout: 30_000 });
    const cookies = await context.cookies();
    if (cookies.length === 0) throw new Error("oturum çerezi alınamadı");
    return cookies.map((c) => `${c.name}=${c.value}`).join("; ");
  } finally {
    await browser.close();
  }
}

function runLighthouse(url, extraHeaders) {
  const dir = mkdtempSync(join(tmpdir(), "lh-"));
  const outPath = join(dir, "report.json");
  const cliArgs = [
    LIGHTHOUSE_CLI,
    url,
    "--only-categories=accessibility",
    "--output=json",
    `--output-path=${outPath}`,
    "--chrome-flags=--headless=new --no-sandbox",
    "--quiet",
    // Skor cihaz emülasyonundan etkilenmesin: erişilebilirlik denetimleri
    // masaüstü genişliğinde ölçülür (BRIEF: hedef ortam 1440–1920px masaüstü).
    "--preset=desktop",
  ];
  if (extraHeaders) {
    const headerPath = join(dir, "headers.json");
    writeFileSync(headerPath, JSON.stringify({ Cookie: extraHeaders }));
    cliArgs.push(`--extra-headers=${headerPath}`);
  }
  try {
    // Lighthouse CLI'si `node` ile DOĞRUDAN çağrılır: Windows'ta `pnpm`/`npx`
    // birer `.cmd` sarmalayıcıdır ve `execFileSync` onları ENOENT ile
    // bulamaz. Ayrıca sürüm kilitli olur — skor, araç sürümü değiştiğinde
    // sessizce kayarsa ölçüm karşılaştırılamaz hâle gelirdi.
    try {
      execFileSync(process.execPath, cliArgs, {
        encoding: "utf-8",
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env, CHROME_PATH },
      });
    } catch (error) {
      // ÇIKIŞ KODUNA GÜVENİLMEZ. Windows'ta `chrome-launcher`, raporu
      // yazdıktan SONRA geçici profil klasörünü silmeye çalışıyor ve
      // `EPERM` ile düşüyor (Chrome süreci dosyayı hâlâ tutuyor). Yani
      // ölçüm başarılı, süreç başarısız. Kararı rapor DOSYASI verir; dosya
      // yoksa hata gerçektir ve stderr ile birlikte yükseltilir.
      if (!existsSync(outPath)) {
        const stderr = error.stderr ? `\n${String(error.stderr).trim().split("\n").slice(-5).join("\n")}` : "";
        throw new Error(`${error.message.split("\n")[0]}${stderr}`);
      }
    }
    const report = JSON.parse(readFileSync(outPath, "utf-8"));
    const score = Math.round(report.categories.accessibility.score * 100);
    const failed = Object.values(report.audits)
      .filter((a) => a.score !== null && a.score < 1 && a.scoreDisplayMode !== "informative")
      .map((a) => ({
        id: a.id,
        title: a.title,
        items: (a.details?.items ?? []).length,
        // Düğüm parçacıkları JSON çıktısında tutulur: "hangi sayfa kaç puan"
        // bilgisi düzeltme yapmaya yetmez, hangi ELEMENT olduğu gerekir.
        nodes: (a.details?.items ?? [])
          .map((item) => item.node?.snippet ?? item.node?.selector)
          .filter(Boolean),
      }));
    return { score, failed };
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// `--only` başındaki `/` istemez: Git Bash yolu Windows yoluna çevirdiği için
// `--only /tenders` argümana `C:/Program Files/tenders` olarak geliyor. Son
// segment üzerinden eşleştirmek bu tuzağı ortadan kaldırır.
const onlyKey = ONLY ? `/${ONLY.split(/[\\/]/).filter(Boolean).pop()}` : null;
const routes = onlyKey ? ROUTES.filter((r) => r.path.startsWith(onlyKey)) : ROUTES;
if (routes.length === 0) {
  console.error(`'${ONLY}' ile eşleşen rota yok.`);
  process.exit(2);
}

let cookieHeader = null;
if (routes.some((r) => r.auth)) {
  cookieHeader = await sessionCookieHeader();
  console.log("[a11y] oturum çerezi alındı\n");
}

const results = [];
for (const route of routes) {
  const url = `${BASE}${route.path}`;
  let outcome;
  try {
    outcome = runLighthouse(url, route.auth ? cookieHeader : null);
  } catch (error) {
    console.log(`HATA ${route.path}: ${error.message.split("\n")[0]}`);
    results.push({ path: route.path, score: null, failed: [] });
    continue;
  }
  results.push({ path: route.path, ...outcome });
  const mark = outcome.score >= 95 ? "OK  " : outcome.score >= 90 ? "ORTA" : "DUSUK";
  console.log(`${mark} ${String(outcome.score).padStart(3)}  ${route.path}`);
  for (const audit of outcome.failed) {
    console.log(`         ✗ ${audit.id} — ${audit.title} (${audit.items} öğe)`);
  }
}

const lowest = results.filter((r) => r.score !== null).sort((a, b) => a.score - b.score)[0];
console.log(`\nEn düşük: ${lowest?.path} = ${lowest?.score}`);
if (JSON_OUT) {
  writeFileSync(JSON_OUT, JSON.stringify({ base: BASE, measuredAt: new Date().toISOString(), results }, null, 2));
  console.log(`JSON: ${JSON_OUT}`);
}

// DESIGN.md §12: skor ≥95 olmadan UI görevi kapanmaz.
const failing = results.filter((r) => r.score === null || r.score < 95);
process.exit(failing.length === 0 ? 0 : 1);
