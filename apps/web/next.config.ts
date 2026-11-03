import fs from "node:fs";
import path from "node:path";

import type { NextConfig } from "next";

import { PHASE_PRODUCTION_BUILD } from "next/constants";

import { assertBuildTimeEnv } from "./src/config/env";

const isProduction = process.env.NODE_ENV === "production";

/**
 * Depolama origin'ini YEREL çalıştırmada kök `.env`den türetir.
 *
 * ## Neden gerekiyor
 *
 * Tarayıcı, imzalı URL'lerle nesne depolamaya DOĞRUDAN çıkar: yükleme bir
 * `PUT`, PDF önizlemesi bir `GET`. Origin CSP `connect-src`e girmezse tarayıcı
 * ikisini de keser — yükleme "Failed to fetch" verir, doküman tuvali sessizce
 * boş kalır. Tur 11'de üretimde yaşanan arıza buydu; compose tarafı build
 * ARG'ıyla (`${STORAGE_ORIGIN:-${OBJECT_STORAGE_ENDPOINT_URL}}`) düzeltildi ama
 * **yerel `next dev`/`next build` yolunda karşılığı yoktu.** Next yalnız kendi
 * dizinindeki (`apps/web`) `.env` dosyalarını okur; değerin tek gerçek kaynağı
 * olan kök `.env` oraya hiç ulaşmıyordu.
 *
 * ## Neden ikinci bir dosyaya yazmak yerine türetme
 *
 * `apps/web/.env.local`a elle kopyalamak origin'i İKİ yere yazardı; R2 hesabı
 * değişince biri sessizce eskir ve arıza yine sessizdir. Compose hangi zinciri
 * kullanıyorsa aynısı burada da kullanılır: açık `NEXT_PUBLIC_STORAGE_ORIGIN` →
 * `STORAGE_ORIGIN` → `OBJECT_STORAGE_ENDPOINT_URL`in origin'i.
 *
 * ## Üretim kapısı GEVŞEMİYOR
 *
 * Kök `.env` Docker derleme bağlamına HİÇ girmiyor (`.dockerignore` `.env` ve
 * `.env.*`i dışlar) ve CI değişkeni job env'inde açıkça veriyor. Yani imaj
 * derlemesinde bu türetme dosyayı bulamaz, sessizce atlar ve eksik build ARG'ı
 * `assertBuildTimeEnv()` eskisi gibi yakalar. Türetme yalnız değişken HİÇ
 * verilmemişken devreye girer; verilmişse ona dokunmaz.
 */
function deriveStorageOriginFromRootEnv(): string {
  if (process.env.NEXT_PUBLIC_STORAGE_ORIGIN || process.env.STORAGE_ORIGIN) return "";

  let raw: string;
  try {
    raw = fs.readFileSync(path.join(import.meta.dirname, "../../.env"), "utf8");
  } catch {
    // Kök `.env` yok (Docker imaj derlemesi, CI, taze klon): türetme yapılmaz.
    return "";
  }

  const lines = raw.split(/\r?\n/);
  const read = (key: string): string => {
    const line = lines.find((candidate) => candidate.trimStart().startsWith(`${key}=`));
    if (line === undefined) return "";
    // Satır sonu açıklaması (`# ör. ...`) `.env.example` biçiminde yaygın.
    return line
      .slice(line.indexOf("=") + 1)
      .split("#")[0]
      .trim()
      .replace(/^["']|["']$/g, "");
  };

  let origin = read("NEXT_PUBLIC_STORAGE_ORIGIN") || read("STORAGE_ORIGIN");
  if (origin === "") {
    const endpoint = read("OBJECT_STORAGE_ENDPOINT_URL");
    if (endpoint === "") return "";
    try {
      origin = new URL(endpoint).origin;
    } catch {
      // Bozuk endpoint yapılandırma hatasıdır; derlemeyi burada düşürmeyiz —
      // eksiklik olarak kalır ve `assertBuildTimeEnv()` üretimde konuşur.
      return "";
    }
  }
  // `assertBuildTimeEnv()` ve sunucu tarafı okumalar `process.env`e bakar.
  process.env.NEXT_PUBLIC_STORAGE_ORIGIN = origin;
  return origin;
}

/**
 * Türetme derleme başlamadan, modül yüklenirken koşar.
 *
 * `process.env`i sonradan değiştirmek YETMİYOR: Next `NEXT_PUBLIC_*` değerlerini
 * paketlere gömerken kendi anlık görüntüsünü kullanıyor ve `config()` çağrıldığı
 * anda o görüntü alınmış oluyor — denendi, `connect-src 'self'` olarak kaldı.
 * Bu yüzden değer ayrıca `nextConfig.env` üzerinden veriliyor: gömmeyi yapan
 * belgelenmiş mekanizma budur ve proxy (`src/proxy.ts`) paketini de kapsar.
 */
const derivedStorageOrigin = deriveStorageOriginFromRootEnv();

/**
 * Tüm yanıtlara eklenen güvenlik başlıkları (J.1).
 *
 * **CSP burada DEĞİL.** İçerik Güvenlik Politikası artık zorlayıcı ve nonce
 * tabanlı olduğu için istek başına üretilmek zorunda; statik başlık listesinde
 * yeri yok. Tanımı `src/lib/security/csp.ts`, yayını `src/proxy.ts`.
 */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // CSP `frame-ancestors 'none'` taşıyor; bu başlık onu tanımayan eski
  // tarayıcılar için yedektir ve proxy'nin çalışmadığı rotaları
  // (statik varlıklar, /api) da kapsar.
  { key: "X-Frame-Options", value: "DENY" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  // HSTS yalnız production'da: yerel http geliştirmede tarayıcıyı https'e
  // kilitlemek, alan adı TLS'e geçmeden önce erişimi kesebilirdi.
  ...(isProduction
    ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]
    : []),
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Depolama origin'i DERLEME anında dondurulur — iki ad da, değer boş olsa bile.
  //
  // Next 16'da CSP'yi üreten `proxy` Node çalışma zamanında koşuyor (eski
  // `middleware` edge'deydi). Next `process.env.X`i yalnız derleme anında TANIMLI
  // değişkenler için sabite çeviriyor; tanımsız olan Node'da çalışma anında
  // gerçek `process.env`ten okunur. Yani buraya hiçbir şey yazılmasaydı, derlemede
  // verilmemiş bir origin çalışma anında politikaya sızabilirdi — CSP'nin imajla
  // birlikte sabit olduğu değişmezi sessizce gevşerdi. `env` her iki adı da
  // (boşsa `""`) gömer; çalışma anı değeri edge'deki gibi yine ETKİSİZDİR.
  //
  // Dışarıdan (build ARG / CI job env) gelen değer EZİLMEZ: aynısı geçirilir.
  // Türetme bir değer bulduysa `process.env`e de yazdığı için o da buradan geçer.
  // Tarayıcı paketine yalnız zaten herkese açık olan `NEXT_PUBLIC_*` girer;
  // `STORAGE_ORIGIN`i okuyan kod (`config/env.ts`) yalnız sunucu/proxy paketinde.
  env: {
    NEXT_PUBLIC_STORAGE_ORIGIN: derivedStorageOrigin || process.env.NEXT_PUBLIC_STORAGE_ORIGIN || "",
    STORAGE_ORIGIN: process.env.STORAGE_ORIGIN || "",
  },
  // Standalone çıktı yalnızca Docker imajında (Linux) etkinleşir: Windows'ta
  // Next'in standalone symlink adımı Developer Mode olmadan EPERM verir. Yerel
  // `pnpm web:build` bu yüzden standart çıktı kullanır (env ile açılmadıkça).
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  outputFileTracingRoot: path.join(import.meta.dirname, "../.."),
  // Workspace paketini (ham TS) Next derler — ayrı build adımı gerekmez.
  transpilePackages: ["@tenderiq/api-client"],
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  // pdfjs-dist'in Node-only opsiyonel `canvas` bağımlılığı tarayıcı/SSR
  // paketine girmesin (react-pdf'in Next.js önerisi). Next 16'da derleyici
  // Turbopack: eski `webpack` kancasındaki `resolve.alias.canvas = false`ın
  // karşılığı budur — Turbopack'te `false` yok, boş bir modüle yönlendirilir.
  // `webpack` kancası bilerek KALDIRILDI: Turbopack derlemesinde yok sayılır,
  // varlığı ise Next 16'da derlemeyi "yanlış yapılandırma" diye düşürür.
  turbopack: {
    resolveAlias: {
      canvas: "./src/lib/empty-module.ts",
    },
  },
};

/**
 * Yapılandırma FAZA göre verilir.
 *
 * Zorunlu derleme-zamanı değişkenleri yalnız `phase-production-build`ta
 * doğrulanır: bu dosya `next start` sırasında da yüklenir, ama o an değer
 * artık imaja gömülüdür ve `process.env`de GÖRÜNMEZ. Kontrolü faza bağlamadan
 * yazmak, doğru derlenmiş bir imajın açılışını yanlışlıkla engelliyordu
 * (Tur 12'de E2E bunu yakaladı).
 *
 * Eksik build ARG derlemeyi düşürür — hatalı yapılandırmayla imaj üretilemez.
 */
export default function config(phase: string): NextConfig {
  // Doğrulamadan ÖNCE: türetme başarılıysa değer artık gerçekten mevcuttur ve
  // denetimin ondan haberi olmalı. Docker/CI'da türetme no-op olduğu için kapı
  // eskisi gibi kapalı kalır.
  deriveStorageOriginFromRootEnv();
  if (phase === PHASE_PRODUCTION_BUILD) assertBuildTimeEnv();
  return nextConfig;
}
