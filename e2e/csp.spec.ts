import { expect, test } from "@playwright/test";

/**
 * İçerik Güvenlik Politikası ZORLAYICI modda ve nonce tabanlı.
 *
 * **Bu dosya olmadan politikayı sıkılaştırmak güvenli değil.** Zorlayıcı CSP'nin
 * arızası sessizdir: başlık kusursuz görünür, sayfa da ilk bakışta doğru
 * boyanır, ama nonce bir betiğe ulaşmadıysa hidrasyon hiç olmaz ve arayüz
 * ölüdür — hiçbir buton çalışmaz. Sunucu tarafında hiçbir hata görünmez.
 * Bu yüzden burada üç şey birden ölçülür:
 *
 * 1. **Politika gerçekten zorlayıcı** (rapor moduna geri düşmemiş) ve
 *    `script-src`te `'unsafe-inline'` yok — yani koruma iptal edilmemiş.
 * 2. **Tarayıcı hiçbir ihlal bildirmiyor** (`securitypolicyviolation` olayı)
 *    ve konsolda hata yok.
 * 3. **Sayfa yaşıyor:** React olayları bağlanmış (hidrasyon oldu).
 *
 * Kimlik gerektirmeyen rotalar seçildi; korumalı sayfalar diğer spec'lerde
 * zaten gerçek oturumla geziliyor ve oradaki konsol hataları da aynı politikaya
 * tabidir.
 */
const PUBLIC_ROUTES = [
  "/",
  "/login",
  "/register",
  "/forgot-password",
  "/kvkk",
  "/sartlar",
  "/trust",
  "/dpa",
] as const;

/** Tohumdaki E2E hesabı (`scripts/seed_e2e.py`). */
const SEED_EMAIL = process.env.E2E_EMAIL ?? "e2e@tenderiq-e2e.com";
const SEED_PASSWORD = process.env.E2E_PASSWORD ?? "e2e-password-123";

type Violation = { directive: string; blocked: string };

for (const route of PUBLIC_ROUTES) {
  test(`CSP zorlayıcı ve ihlalsiz: ${route}`, async ({ page }) => {
    const violations: Violation[] = [];
    const consoleErrors: string[] = [];

    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => consoleErrors.push(`pageerror: ${error.message}`));

    // İhlaller sayfa betikleri çalışmaya başlamadan önce dinlenmeye başlamalı;
    // `addInitScript` bunu garanti eder (`goto` sonrası dinlemek ilk, en
    // önemli ihlali kaçırırdı).
    await page.addInitScript(() => {
      const store: Violation[] = [];
      (window as unknown as { __cspViolations: Violation[] }).__cspViolations = store;
      document.addEventListener("securitypolicyviolation", (event) => {
        store.push({ directive: event.effectiveDirective, blocked: event.blockedURI });
      });
    });

    const response = await page.goto(route);
    expect(response, `${route} yanıt vermedi`).not.toBeNull();

    const headers = response!.headers();
    const policy = headers["content-security-policy"];

    // Rapor moduna geri düşme, sessizce korumayı kapatır: başlık vardır,
    // hiçbir şeyi engellemez.
    expect(policy, `${route} zorlayıcı CSP başlığı taşımıyor`).toBeTruthy();
    expect(headers["content-security-policy-report-only"]).toBeUndefined();

    const scriptSrc = policy!
      .split(";")
      .map((directive) => directive.trim())
      .find((directive) => directive.startsWith("script-src"));
    expect(scriptSrc, "script-src yönergesi yok").toBeTruthy();
    expect(scriptSrc).toContain("'nonce-");
    expect(scriptSrc).toContain("'strict-dynamic'");
    // `'unsafe-inline'` script-src'de olsaydı nonce'un hiçbir değeri kalmazdı.
    expect(scriptSrc).not.toContain("'unsafe-inline'");

    // İhlal raporları toplanabiliyor olmalı; yönerge yoksa politika
    // sıkılaştıkça kör uçarız.
    expect(policy).toContain("report-uri /api/csp-report");

    // NOT: `style-src`te `'unsafe-inline'` bilinçli olarak DURUYOR — `sonner`
    // çalışma anında nonce'suz bir `<style>` bloğu enjekte ediyor ve nonce
    // kabul etmiyor (Tur 11'de ölçüldü, bkz. `lib/security/csp.ts`). Burada
    // onu yasaklayan bir beklenti YOK; koyulsaydı bilinen bir borcu her koşuda
    // kırmızıya çevirirdi.

    // Next'in kendi betikleri nonce almış olmalı. Almadıysa politika onları
    // engellerdi ve sayfa hidrasyon yapmazdı.
    const nonced = await page.locator("script[nonce]").count();
    expect(nonced, `${route}: nonce taşıyan betik yok`).toBeGreaterThan(0);

    // Sayfa YAŞIYOR mu? React olay bağlamayı bitirdiyse gövdedeki ilk öğede
    // React internal alanı bulunur. Bu, "boyandı ama ölü" hâlini yakalar.
    await expect
      .poll(
        () =>
          page.evaluate(() => {
            const element = document.body.firstElementChild;
            if (!element) return false;
            return Object.keys(element).some((key) => key.startsWith("__react"));
          }),
        { message: `${route}: hidrasyon olmadı (CSP betikleri engelliyor olabilir)` },
      )
      .toBe(true);

    const collected = await page.evaluate(
      () => (window as unknown as { __cspViolations?: Violation[] }).__cspViolations ?? [],
    );
    expect(collected, `${route} CSP ihlali üretti: ${JSON.stringify(collected)}`).toEqual([]);
    expect(consoleErrors, `${route} konsol hatası üretti: ${consoleErrors.join(" | ")}`).toEqual(
      [],
    );
  });
}

/**
 * Kimlikli ekranlar — özellikle inceleme çalışma alanı.
 *
 * Herkese açık sayfalar politikanın en basit hâlini sınar. Asıl risk oturum
 * arkasındadır: inceleme ekranı `react-pdf`/`pdfjs` çalıştırıyor (worker +
 * blob URL) ve zorlayıcı CSP altında en kırılgan yüzey orası. `style-src`
 * Tur 11'de `'unsafe-inline'`dan `'self'`e sıkıldı; satır içi `<style>` bloğu
 * üreten bir kütüphane varsa ihlal İLK burada görünür.
 */
test("kimlikli ekranlarda da CSP ihlali yok (inceleme çalışma alanı dâhil)", async ({ page }) => {
  const violations: Violation[] = [];
  const consoleErrors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(`pageerror: ${error.message}`));
  await page.addInitScript(() => {
    const store: Violation[] = [];
    (window as unknown as { __cspViolations: Violation[] }).__cspViolations = store;
    document.addEventListener("securitypolicyviolation", (event) => {
      store.push({ directive: event.effectiveDirective, blocked: event.blockedURI });
    });
  });

  await page.goto("/login");
  await page.getByLabel("E-posta").fill(SEED_EMAIL);
  await page.getByLabel("Parola").fill(SEED_PASSWORD);
  await page.getByRole("button", { name: "Giriş yap" }).click();
  await page.waitForURL(/\/panel/);

  // Tohumlanan ihaleye git, oradan inceleme ekranına.
  await page.goto("/tenders");
  // `:visible` şart: liste hem mobil kart listesi hem masaüstü tablosu olarak
  // render ediliyor (§7.4) ve ilk eşleşen bağlantı masaüstü genişliğinde
  // GİZLİ olan mobil sürüm. Görünürlük filtresi olmadan test, var olan bir
  // öğeyi "yok" sanıyordu.
  const tenderLink = page.locator('a[href^="/tenders/"]:visible').first();
  await expect(tenderLink).toBeVisible();
  const href = await tenderLink.getAttribute("href");
  const tenderId = href?.split("/")[2];
  expect(tenderId, "tohumda ihale yok — seed_e2e.py koştu mu?").toBeTruthy();

  for (const route of [`/tenders/${tenderId}`, `/tenders/${tenderId}/review`, "/usage", "/settings"]) {
    await page.goto(route);
    // Doküman tuvali tembel yüklenir; ihlal ancak render başlayınca doğar.
    await page.waitForLoadState("networkidle");
  }

  const collected = await page.evaluate(
    () => (window as unknown as { __cspViolations?: Violation[] }).__cspViolations ?? [],
  );
  expect(collected, `kimlikli ekranlarda CSP ihlali: ${JSON.stringify(collected)}`).toEqual([]);

  // Konsol hataları CSP ile SINIRLI tutulur. Depolama origin'i bu koşumda
  // bilinçli olarak ölü bir yerel port (bkz. playwright.config.ts): PDF baytları
  // hiç gelmez ve tarayıcı bir AĞ hatası yazar. Bu beklenen; sınanan şey
  // politikanın o origin'e izin VERDİĞİ — vermezse hata CSP hatası olur ve
  // aşağıdaki filtre onu yakalar.
  const cspErrors = consoleErrors.filter((message) =>
    message.includes("Content Security Policy"),
  );
  expect(cspErrors, `kimlikli ekranlarda CSP konsol hatası: ${cspErrors.join(" | ")}`).toEqual([]);
});

/**
 * Rapor ucu gerçekten kabul ediyor mu?
 *
 * Politikada `report-uri` yazmak yetmez — uç 404 ya da 500 dönüyorsa raporlar
 * kaybolur ve bunu kimse fark etmez. Tarayıcının gönderdiği iki biçim de
 * denenir.
 */
test("CSP rapor ucu her iki biçimi de kabul eder", async ({ request }) => {
  const legacy = await request.post("/api/csp-report", {
    headers: { "content-type": "application/csp-report" },
    data: {
      "csp-report": {
        "document-uri": "http://127.0.0.1/login",
        "effective-directive": "script-src",
        "blocked-uri": "inline",
        disposition: "enforce",
      },
    },
  });
  expect(legacy.status()).toBe(204);

  const modern = await request.post("/api/csp-report", {
    headers: { "content-type": "application/reports+json" },
    data: [
      {
        type: "csp-violation",
        url: "http://127.0.0.1/login",
        body: { effectiveDirective: "script-src", blockedURL: "inline", disposition: "enforce" },
      },
    ],
  });
  expect(modern.status()).toBe(204);

  // Bozuk gövde uçta 500 üretmemeli: tarayıcı sürümleri farklı şeyler gönderir
  // ve 500'ler log gürültüsünden başka bir şey üretmez.
  const malformed = await request.post("/api/csp-report", {
    headers: { "content-type": "application/csp-report" },
    data: "bu json degil",
  });
  expect(malformed.status()).toBe(204);
});
