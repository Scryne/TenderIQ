import path from "node:path";

import type { NextConfig } from "next";

const isProduction = process.env.NODE_ENV === "production";

/**
 * CSP `connect-src` kaynakları.
 *
 * Tarayıcı iki dış origin'e gider: imzalı nesne depolama URL'i (PDF önizleme
 * baytları doğrudan R2'den indirilir — bkz. `pdf-viewer.tsx`) ve varsa Sentry.
 * İkisi de dağıtıma özgüdür; bu yüzden env'den okunur. Yanlış yapılandırma
 * sessizce PDF önizlemeyi kırabileceği için politika ÖNCE rapor modunda yayılır.
 */
function connectSources(): string[] {
  const sources = ["'self'"];
  const storageOrigin = process.env.NEXT_PUBLIC_STORAGE_ORIGIN;
  if (storageOrigin) sources.push(storageOrigin);
  const sentryDsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (sentryDsn) {
    try {
      sources.push(new URL(sentryDsn).origin);
    } catch {
      // Bozuk DSN build'i düşürmemeli; Sentry zaten devre dışı kalır.
    }
  }
  return sources;
}

/**
 * İçerik Güvenlik Politikası (J.1).
 *
 * `'unsafe-inline'` script-src'de BİLİNÇLİ bir borçtur: Next'in hidrasyon
 * betikleri satır içidir ve nonce'a geçmek her sayfayı dinamik render'a zorlar.
 * Bu yüzden politika şimdilik **yalnız raporlama modunda** yayınlanır (aşağıda
 * `Content-Security-Policy-Report-Only`): ihlalleri görürüz ama hiçbir şeyi
 * kırmayız. Zorlayıcı moda geçiş, nonce'lu script-src ile GA öncesi yapılır.
 */
function contentSecurityPolicy(): string {
  const directives = [
    "default-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    // PDF.js worker'ı webpack tarafından paketlenir (aynı origin); bazı
    // yapılandırmalarda blob: üzerinden başlatılır.
    "worker-src 'self' blob:",
    `connect-src ${connectSources().join(" ")}`,
  ];
  if (isProduction) directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}

/** Tüm yanıtlara eklenen güvenlik başlıkları (J.1). */
const securityHeaders = [
  { key: "Content-Security-Policy-Report-Only", value: contentSecurityPolicy() },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // frame-ancestors'ın CSP'si henüz rapor modunda; çerçeveleme savunması bu
  // başlıkla ZORLAYICI olarak durur.
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
  webpack: (config) => {
    // pdfjs-dist'in Node-only opsiyonel `canvas` bağımlılığı tarayıcı/SSR
    // paketine girmesin (react-pdf'in Next.js önerisi).
    config.resolve.alias = { ...config.resolve.alias, canvas: false };
    return config;
  },
};

export default nextConfig;
