import path from "node:path";

import type { NextConfig } from "next";

const isProduction = process.env.NODE_ENV === "production";

/**
 * Tüm yanıtlara eklenen güvenlik başlıkları (J.1).
 *
 * **CSP burada DEĞİL.** İçerik Güvenlik Politikası artık zorlayıcı ve nonce
 * tabanlı olduğu için istek başına üretilmek zorunda; statik başlık listesinde
 * yeri yok. Tanımı `src/lib/security/csp.ts`, yayını `src/middleware.ts`.
 */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // CSP `frame-ancestors 'none'` taşıyor; bu başlık onu tanımayan eski
  // tarayıcılar için yedektir ve middleware'in çalışmadığı rotaları
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
