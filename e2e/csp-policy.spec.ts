import { expect, test } from "@playwright/test";

import { ENV_VARIABLES, variablesWithoutReader } from "@/config/env";
import { buildContentSecurityPolicy, connectSources } from "@/lib/security/csp";

/**
 * Politika ÜRETİCİSİNİN birim testi — tarayıcı açmadan.
 *
 * ## Neden ayrı bir test
 *
 * "Değişken tanımlı" ile "politika doğru" AYRI şeylerdir ve Tur 11'de tam bu
 * boşluk üretimde bir arıza üretti: `NEXT_PUBLIC_STORAGE_ORIGIN` bir dosyada
 * tanımlıymış gibi durup politikaya hiç girmiyordu.
 *
 * `test_yapilandirma_denetimi.py` ilk yarıyı (değişken dağıtım dosyalarında
 * kurulu mu) kapatıyor. Burası ikinci yarı: **değer gerçekten politikaya
 * giriyor mu.** `e2e/csp.spec.ts` bunu tarayıcıyla uçtan uca doğruluyor ama
 * oradaki arıza mesajı "sayfa ihlal üretti" der; burada hangi yönergenin neyi
 * kaçırdığı doğrudan görünür.
 *
 * Tarayıcı gerekmediği için hızlıdır; `process.env` üzerinde oynayıp saf
 * fonksiyonun çıktısına bakar.
 */

function withEnv<T>(overrides: Record<string, string | undefined>, run: () => T): T {
  const previous: Record<string, string | undefined> = {};
  for (const [key, value] of Object.entries(overrides)) {
    previous[key] = process.env[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  try {
    return run();
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function directive(policy: string, name: string): string {
  const found = policy
    .split(";")
    .map((part) => part.trim())
    .find((part) => part === name || part.startsWith(`${name} `));
  expect(found, `politikada '${name}' yönergesi yok: ${policy}`).toBeTruthy();
  return found!;
}

test("manifestodaki her değişkenin STATİK okuyucusu var", () => {
  // `process.env[ad]` dinamik erişimi, derleme anında gömülen değeri göremez
  // (Next yalnız statik üye erişimini metinsel olarak değiştirir). Okuyucusu
  // olmayan bir değişken, doğru yapılandırılmış kurulumda bile "eksik" görünür
  // ve açılışı yanlış yere kilitler.
  expect(variablesWithoutReader()).toEqual([]);
  expect(ENV_VARIABLES.length).toBeGreaterThan(0);
});

test("depolama origin'i connect-src'e GİRER", () => {
  const sources = withEnv(
    { NEXT_PUBLIC_STORAGE_ORIGIN: "https://depo.example.com", STORAGE_ORIGIN: undefined },
    () => connectSources(),
  );
  expect(sources).toContain("https://depo.example.com");
});

test("yedek ad (STORAGE_ORIGIN) de connect-src'e girer", () => {
  const sources = withEnv(
    { NEXT_PUBLIC_STORAGE_ORIGIN: undefined, STORAGE_ORIGIN: "https://yedek.example.com" },
    () => connectSources(),
  );
  expect(sources).toContain("https://yedek.example.com");
});

test("origin YOKSA connect-src yalnız aynı-origin'dir (arızanın imzası)", () => {
  const sources = withEnv(
    { NEXT_PUBLIC_STORAGE_ORIGIN: undefined, STORAGE_ORIGIN: undefined },
    () => connectSources(),
  );
  // Bu, Tur 11'de üretimde oluşan hâlin ta kendisi: politika "geçerli" görünür,
  // tarayıcı imzalı PDF URL'ini çekemez ve tuval sessizce boş kalır.
  expect(sources).toEqual(["'self'"]);
});

test("Sentry DSN varsa origin'i eklenir, bozuksa politika düşmez", () => {
  const iyi = withEnv({ NEXT_PUBLIC_SENTRY_DSN: "https://abc@o1.ingest.sentry.io/2" }, () =>
    connectSources(),
  );
  expect(iyi).toContain("https://o1.ingest.sentry.io");

  // Bozuk DSN bir yapılandırma hatasıdır ama politikayı üretememek daha kötüdür:
  // o durumda HİÇBİR sayfa açılmazdı.
  const bozuk = withEnv({ NEXT_PUBLIC_SENTRY_DSN: "bu-bir-url-degil" }, () => connectSources());
  expect(bozuk).toEqual(["'self'"]);
});

test("politika iskeleti: nonce'lu script-src, frame-ancestors none, rapor ucu", () => {
  const policy = withEnv({ NEXT_PUBLIC_STORAGE_ORIGIN: "https://depo.example.com" }, () =>
    buildContentSecurityPolicy("TEST_NONCE", true),
  );

  expect(directive(policy, "script-src")).toContain("'nonce-TEST_NONCE'");
  expect(directive(policy, "script-src")).toContain("'strict-dynamic'");
  expect(directive(policy, "script-src")).not.toContain("'unsafe-inline'");
  expect(directive(policy, "frame-ancestors")).toBe("frame-ancestors 'none'");
  expect(directive(policy, "object-src")).toBe("object-src 'none'");
  expect(directive(policy, "connect-src")).toContain("https://depo.example.com");
  expect(policy).toContain("report-uri /api/csp-report");
  // Production'da HTTPS yükseltmesi; dev'de olmamalı (yerel http'yi kırardı).
  expect(policy).toContain("upgrade-insecure-requests");
  const devPolicy = buildContentSecurityPolicy("N", false);
  expect(devPolicy).not.toContain("upgrade-insecure-requests");
});

test("connect-src `blob:` taşır — PDF.js tuvalinin şartı", () => {
  // Depolama origin'i DOĞRU olsa bile `blob:` yoksa doküman tuvali boş kalır:
  // baytlar R2'den iner (200), `URL.createObjectURL` ile sarılır, PDF.js o
  // adresi `fetch`lemeye çalışır ve CSP keser. Belirti depolama origin'i eksik
  // olduğundakiyle AYNI olduğu için ikisi kolayca birbirine karışır; bu yüzden
  // ayrı bir kapı.
  const policy = withEnv({ NEXT_PUBLIC_STORAGE_ORIGIN: "https://depo.example.com" }, () =>
    buildContentSecurityPolicy("N", true),
  );
  expect(directive(policy, "connect-src")).toContain("blob:");
  expect(directive(policy, "connect-src")).toContain("https://depo.example.com");
});

test("'unsafe-eval' YALNIZ geliştirmede; üretime sızmaz", () => {
  // İki yönlü kapı. Üretim yönü güvenlik kapısıdır: `'unsafe-eval'` script-src'in
  // XSS korumasını büyük ölçüde geri verir (enjekte edilen dize kod olarak
  // çalıştırılabilir), oraya asla girmemeli.
  expect(directive(buildContentSecurityPolicy("N", true), "script-src")).not.toContain(
    "'unsafe-eval'",
  );
  // Dev yönü kullanılabilirlik kapısıdır: `next dev` paketi modülleri `eval()` ile
  // sarar; izin yoksa hidrasyon HİÇ olmaz — sayfa "çalışıyor" görünür ama form
  // gönderimi düz GET'e düşer ve dev sunucusunda giriş yapılamaz.
  expect(directive(buildContentSecurityPolicy("N", false), "script-src")).toContain(
    "'unsafe-eval'",
  );
});
