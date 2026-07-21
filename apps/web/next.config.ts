import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Standalone çıktı yalnızca Docker imajında (Linux) etkinleşir: Windows'ta
  // Next'in standalone symlink adımı Developer Mode olmadan EPERM verir. Yerel
  // `pnpm web:build` bu yüzden standart çıktı kullanır (env ile açılmadıkça).
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  outputFileTracingRoot: path.join(import.meta.dirname, "../.."),
  // Workspace paketini (ham TS) Next derler — ayrı build adımı gerekmez.
  transpilePackages: ["@tenderiq/api-client"],
  webpack: (config) => {
    // pdfjs-dist'in Node-only opsiyonel `canvas` bağımlılığı tarayıcı/SSR
    // paketine girmesin (react-pdf'in Next.js önerisi).
    config.resolve.alias = { ...config.resolve.alias, canvas: false };
    return config;
  },
};

export default nextConfig;
