/**
 * DESIGN.md §14 görsel doğrulama döngüsünün motoru.
 *
 * `chrome-devtools` MCP bu projede kurulu değil; yerine apps/web'de zaten kurulu olan
 * Playwright + Chromium kullanılır. Script §14.2'deki dört zorunlu viewport'ta ekran
 * görüntüsü alır, konsol hatalarını toplar ve yatay taşmayı ölçer.
 *
 * Kullanım (Git Bash'te rotayı **baştaki eğik çizgi olmadan** ver — MSYS, `/x/y`
 * biçimindeki argümanı `C:/Program Files/Git/x/y` Windows yoluna çevirir ve
 * sessizce 404 alırsın):
 *   node scripts/shoot.mjs design/tokens tokens
 *   node scripts/shoot.mjs design/preview preview --dark
 *   node scripts/shoot.mjs tenders liste --only=1440
 *
 * Çıktı: design/shots/<etiket>-<viewport>.png  (+ stdout'ta konsol/taşma raporu)
 */

import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");
const SHOTS = join(ROOT, "design", "shots");

// §14.2 — dört zorunlu viewport. Ad → [genişlik, yükseklik].
const VIEWPORTS = {
  375: [375, 812],
  768: [768, 1024],
  1440: [1440, 900],
  1920: [1920, 1080],
};

const [, , routeArg, labelArg, ...flags] = process.argv;
if (routeArg === undefined) {
  console.error("Kullanım: node scripts/shoot.mjs <rota> [etiket] [--dark] [--only=1440]");
  process.exit(1);
}

// Kök sayfa için "." ya da "root" verilir: Git Bash'te tek "/" argümanı MSYS
// tarafından Git kurulum dizinine çevrilir ve sessizce 404 alınır.
const normalized = routeArg === "." || routeArg === "root" ? "" : routeArg.replace(/^\/+/, "");
const route = `/${normalized}`;
const derivedLabel = normalized.replace(/\//g, "-");
const label = labelArg ?? (derivedLabel === "" ? "kok" : derivedLabel);
const dark = flags.includes("--dark");
const onlyFlag = flags.find((f) => f.startsWith("--only="));
const only = onlyFlag?.slice("--only=".length).split(",");
const baseUrl = process.env.SHOOT_BASE_URL ?? "http://localhost:3000";

// Kimlik gerektiren ekranlar (/usage, /tenders, /settings…) girişsiz çekilirse
// yalnızca /login'in ekran görüntüsü alınır ve §14 döngüsü sessizce hiçbir şey
// doğrulamamış olur. Oturum her viewport için yeniden açılır: her viewport
// kendi tarayıcı bağlamıdır ve çerezler paylaşılmaz.
//
//   SHOOT_EMAIL=e2e@tenderiq.local SHOOT_PASSWORD=... node scripts/shoot.mjs usage abonelik
//
// Tohum: `pnpm e2e:seed` (scripts/seed_e2e.py).
const loginEmail = process.env.SHOOT_EMAIL;
const loginPassword = process.env.SHOOT_PASSWORD;

async function signIn(page, problems) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle", timeout: 45_000 });
  await page.fill("#email", loginEmail);
  await page.fill("#password", loginPassword);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 30_000 }),
    page.click('button[type="submit"]'),
  ]).catch((e) => problems.push(`[login] ${e.message}`));
}

/** Playwright apps/web'in bağımlılığı; kökten çözülemezse oradan resolve edilir. */
async function loadChromium() {
  try {
    return (await import("playwright")).chromium;
  } catch {
    const require = createRequire(join(ROOT, "apps", "web", "package.json"));
    const mod = await import(new URL(`file:///${require.resolve("playwright")}`).href);
    return (mod.default ?? mod).chromium;
  }
}

const chromium = await loadChromium();
mkdirSync(SHOTS, { recursive: true });

const browser = await chromium.launch();
const targets = Object.entries(VIEWPORTS).filter(([name]) => only === undefined || only.includes(name));
let failures = 0;

for (const [name, [width, height]] of targets) {
  const context = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 2,
    locale: "tr-TR",
    timezoneId: "Europe/Istanbul",
    colorScheme: dark ? "dark" : "light",
    reducedMotion: "no-preference",
  });
  // Koyu tema: uygulama `defaultTheme="light"` kullanır ve sistem tercihini
  // bilerek ezer (BRIEF `tema`). Bu yüzden `colorScheme` yetmez; next-themes'in
  // okuduğu anahtar sayfa betikleri çalışmadan ÖNCE tohumlanır.
  if (dark) {
    await context.addInitScript(() => {
      try {
        window.localStorage.setItem("theme", "dark");
      } catch {
        /* storage kapalıysa görmezden gel */
      }
    });
  }

  const page = await context.newPage();

  const problems = [];
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      problems.push(`[${message.type()}] ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => problems.push(`[pageerror] ${error.message}`));

  if (loginEmail !== undefined && loginPassword !== undefined) {
    await signIn(page, problems);
  }

  const url = `${baseUrl}${route}`;
  const response = await page.goto(url, { waitUntil: "networkidle", timeout: 45_000 }).catch((e) => {
    problems.push(`[navigation] ${e.message}`);
    return null;
  });

  // Next dev göstergesi ("N" düğmesi) sol altta durup içeriğin üstüne biniyor ve
  // ekran görüntüsünü kirletiyor. Uygulama yapılandırmasına dokunmadan, yalnız
  // çekim sırasında gizlenir.
  await page
    .addStyleTag({
      content:
        "nextjs-portal,[data-nextjs-toast],#__next-build-watcher{display:none !important}",
    })
    .catch(() => undefined);

  // Girişte tek seferlik animasyonlar bitsin; skeleton'lar yerine otursun.
  await page.waitForTimeout(700);

  // §15 responsive maddesi: yatay kaydırma yok — ölçülür, göz kararı değil.
  const overflow = await page.evaluate(() => {
    const d = document.documentElement;
    return { scrollWidth: d.scrollWidth, clientWidth: d.clientWidth };
  });

  const file = join(SHOTS, `${label}-${name}${dark ? "-dark" : ""}.png`);
  await page.screenshot({ path: file, fullPage: true });

  const status = response?.status() ?? "—";
  const overflows = overflow.scrollWidth > overflow.clientWidth + 1;
  if (overflows || problems.length > 0) failures += 1;

  console.log(`\n── ${name}px · HTTP ${status} · ${file.replace(ROOT, ".")}`);
  console.log(
    overflows
      ? `   ❌ YATAY TAŞMA: scrollWidth ${overflow.scrollWidth} > clientWidth ${overflow.clientWidth}`
      : `   ✅ yatay taşma yok`,
  );
  if (problems.length === 0) {
    console.log("   ✅ konsol temiz");
  } else {
    console.log(`   ❌ konsol (${problems.length}):`);
    for (const p of [...new Set(problems)].slice(0, 12)) console.log(`      ${p}`);
  }

  await context.close();
}

await browser.close();
console.log(`\n${failures === 0 ? "✅" : "❌"} ${targets.length} viewport · ${failures} sorunlu`);
process.exit(failures === 0 ? 0 : 1);
