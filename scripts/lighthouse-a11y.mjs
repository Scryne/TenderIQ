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

/**
 * Ölçülen rotalar. `auth: true` olanlar oturum çerezi ile ölçülür.
 *
 * `:tenderId` yer tutucusu koşum sırasında GERÇEK bir kimlikle doldurulur
 * (`discoverTenderId`): inceleme ekranı ürünün çekirdek çalışma alanıdır ve
 * dinamik rota olduğu için sabit listeye yazılamaz. Tur 10'da tam bu yüzden
 * ölçülmemiş kalmıştı.
 */
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
  { path: "/tenders/:tenderId", auth: true },
  { path: "/tenders/:tenderId/review", auth: true },
  { path: "/usage", auth: true },
  { path: "/settings", auth: true },
  { path: "/capability", auth: true },
];

/** Ölçülecek Lighthouse kategorileri (`--categories` ile değiştirilir). */
const CATEGORIES = (arg("--categories", "accessibility") ?? "accessibility")
  .split(",")
  .map((c) => c.trim())
  .filter(Boolean);

/** DESIGN.md §12 eşiği yalnız erişilebilirlik için geçerlidir. */
const A11Y_MIN_SCORE = Number(arg("--min-a11y", "95"));

/**
 * Oturum açar; `Cookie` başlığını ve tohumdaki ilk ihale kimliğini döndürür.
 *
 * İkisi tek tarayıcı oturumunda alınır: kimlik keşfi için ayrı bir giriş,
 * oran-sınırı sayacını gereksizce tüketirdi (kayıt/giriş uçları sınırlı).
 */
async function loginAndDiscover() {
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

    // İhale kimliği LİSTEDEN okunur, ortam değişkeninden değil: tohum yeniden
    // koşulduğunda kimlik değişir ve elle verilen bir değer sessizce 404'e
    // düşerdi (Lighthouse 404 sayfasını ölçer, skor "iyi" görünür).
    await page.goto("/tenders");
    const href = await page
      .locator('a[href^="/tenders/"]')
      .first()
      .getAttribute("href", { timeout: 15_000 });
    const tenderId = href?.split("/")[2] ?? null;
    if (!tenderId) {
      throw new Error("tohumda ihale bulunamadı — `uv run python scripts/seed_e2e.py` koştu mu?");
    }

    const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
    return { cookieHeader, tenderId };
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
    `--only-categories=${CATEGORIES.join(",")}`,
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
    const scores = {};
    for (const [name, category] of Object.entries(report.categories)) {
      scores[name] = category.score === null ? null : Math.round(category.score * 100);
    }

    // Erişilebilirlik denetimleri yalnız a11y kategorisinden alınır: performans
    // "denetimleri" (LCP, TTFB…) ölçüm değerleridir, düzeltilecek kusur değil —
    // ikisini aynı listede toplamak kapıyı anlamsızlaştırırdı.
    const a11yAuditIds = new Set(
      (report.categories.accessibility?.auditRefs ?? []).map((ref) => ref.id),
    );
    const failed = Object.values(report.audits)
      .filter(
        (a) =>
          a11yAuditIds.has(a.id) &&
          a.score !== null &&
          a.score < 1 &&
          a.scoreDisplayMode !== "informative",
      )
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

    // Performans metrikleri (ms). Skorun kendisi ortama çok duyarlıdır; ham
    // değerler karşılaştırma için skordan daha kullanışlı.
    const metrics = {};
    for (const id of ["largest-contentful-paint", "server-response-time", "first-contentful-paint",
      "total-blocking-time", "cumulative-layout-shift", "speed-index"]) {
      const audit = report.audits[id];
      if (audit && audit.numericValue !== undefined) {
        metrics[id] = Math.round(audit.numericValue * 100) / 100;
      }
    }
    return { scores, failed, metrics };
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
let tenderId = null;
if (routes.some((r) => r.auth)) {
  ({ cookieHeader, tenderId } = await loginAndDiscover());
  console.log(`[lh] oturum alındı · ihale kimliği: ${tenderId}`);
}
console.log(`[lh] kategoriler: ${CATEGORIES.join(", ")}\n`);

const results = [];
for (const route of routes) {
  // Dinamik rota yer tutucusu gerçek kimlikle doldurulur; kimlik yoksa rota
  // ATLANIR (uydurma kimlikle ölçmek 404 sayfasını ölçmek olurdu).
  if (route.path.includes(":tenderId") && !tenderId) {
    console.log(`ATLA      ${route.path} (ihale kimliği yok)`);
    continue;
  }
  const path = route.path.replace(":tenderId", tenderId ?? "");
  const url = `${BASE}${path}`;
  let outcome;
  try {
    outcome = runLighthouse(url, route.auth ? cookieHeader : null);
  } catch (error) {
    console.log(`HATA      ${path}: ${error.message.split("\n")[0]}`);
    results.push({ path, scores: {}, failed: [], metrics: {} });
    continue;
  }
  results.push({ path, ...outcome });

  const a11y = outcome.scores.accessibility;
  const perf = outcome.scores.performance;
  const mark =
    a11y === undefined ? "    " : a11y >= A11Y_MIN_SCORE ? "OK  " : a11y >= 90 ? "ORTA" : "DUSUK";
  const parts = [];
  if (a11y !== undefined) parts.push(`a11y=${String(a11y).padStart(3)}`);
  if (perf !== undefined) parts.push(`perf=${String(perf).padStart(3)}`);
  const lcp = outcome.metrics["largest-contentful-paint"];
  const ttfb = outcome.metrics["server-response-time"];
  if (lcp !== undefined) parts.push(`LCP=${Math.round(lcp)}ms`);
  if (ttfb !== undefined) parts.push(`TTFB=${Math.round(ttfb)}ms`);
  console.log(`${mark} ${parts.join("  ")}  ${path}`);
  for (const audit of outcome.failed) {
    console.log(`         ✗ ${audit.id} — ${audit.title} (${audit.items} öğe)`);
  }
}

// ── Özet ve kapı ─────────────────────────────────────────────────────────────

const measured = results.filter((r) => r.scores.accessibility !== undefined);
const lowest = [...measured].sort(
  (a, b) => a.scores.accessibility - b.scores.accessibility,
)[0];
if (lowest) {
  console.log(`\nEn düşük a11y: ${lowest.path} = ${lowest.scores.accessibility}`);
}

if (CATEGORIES.includes("performance")) {
  const perfRows = results.filter((r) => r.metrics["largest-contentful-paint"] !== undefined);
  if (perfRows.length > 0) {
    const median = (values) => {
      const sorted = [...values].sort((a, b) => a - b);
      return sorted[Math.floor(sorted.length / 2)];
    };
    const lcpMedian = median(perfRows.map((r) => r.metrics["largest-contentful-paint"]));
    const ttfbMedian = median(
      perfRows.map((r) => r.metrics["server-response-time"] ?? 0).filter(Boolean),
    );
    console.log(
      `Performans ortancası: LCP=${Math.round(lcpMedian)}ms · TTFB=${Math.round(ttfbMedian)}ms ` +
        `(${perfRows.length} rota)`,
    );
  }
}

if (JSON_OUT) {
  writeFileSync(
    JSON_OUT,
    JSON.stringify(
      { base: BASE, measuredAt: new Date().toISOString(), categories: CATEGORIES, results },
      null,
      2,
    ),
  );
  console.log(`JSON: ${JSON_OUT}`);
}

// ── Çıkış kapısı ─────────────────────────────────────────────────────────────
//
// **Asıl kapı DÜŞEN DENETİM listesidir, skor değil.** Tur 10'da üç gerçek
// erişilebilirlik kusuru 95–100 skor aralığında saklanıyordu: bazı denetimlerin
// kategori ağırlığı 0 olduğu için skoru hiç düşürmüyorlar. Skor eşiği yalnız EK
// koruma olarak duruyor (bir denetim listede olmasa da skoru düşürebilir).
//
// Performans skoru kapıya GİRMEZ: değeri çalıştığı makineye çok duyarlı,
// eşik koymak CI'da gürültülü kırmızı üretirdi. Ham metrikler JSON'a yazılır ve
// karşılaştırma elle yapılır.
const auditFailures = results.filter((r) => r.failed.length > 0);
const scoreFailures = measured.filter((r) => r.scores.accessibility < A11Y_MIN_SCORE);
const unmeasured = results.filter((r) => r.scores.accessibility === undefined);

if (auditFailures.length > 0) {
  console.log(`\nKAPI: ${auditFailures.length} rotada düşen erişilebilirlik denetimi var.`);
}
if (scoreFailures.length > 0) {
  console.log(`KAPI: ${scoreFailures.length} rota a11y skoru < ${A11Y_MIN_SCORE}.`);
}
if (unmeasured.length > 0 && CATEGORIES.includes("accessibility")) {
  console.log(`KAPI: ${unmeasured.length} rota ölçülemedi: ${unmeasured.map((r) => r.path).join(", ")}`);
}

const gateOpen =
  auditFailures.length === 0 &&
  scoreFailures.length === 0 &&
  (unmeasured.length === 0 || !CATEGORIES.includes("accessibility"));
process.exit(gateOpen ? 0 : 1);
