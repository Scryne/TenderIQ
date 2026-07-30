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
