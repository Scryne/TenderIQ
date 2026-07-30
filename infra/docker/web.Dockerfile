# TenderIQ web imajı — Next.js standalone çıktısı, pnpm monorepo, çok aşamalı.
# syntax=docker/dockerfile:1
FROM node:26-bookworm-slim AS base
ENV NEXT_TELEMETRY_DISABLED=1
# Taban imajın devraldığı Debian CVE'leri için güvenlik yaması (bkz. api.Dockerfile).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# ── Build aşaması ────────────────────────────────────────────────────────────
FROM base AS build
ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH
RUN corepack enable
WORKDIR /app

# 1) Yalnızca manifestler + kilit — bağımlılık katmanını önbelleğe al.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/api-client/package.json packages/api-client/package.json
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile

# 2) Kaynak + tip üretimi + build.
# NEXT_PUBLIC_* değişkenleri build anında gömülür; tarayıcı host'ta çalıştığından
# API'nin host adresi (localhost:8000) varsayılandır.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
# CSP `connect-src`e giren nesne depolama origin'i. Build argümanı olmak ZORUNDA:
# politikayı üreten middleware edge çalışma zamanında koşuyor ve orada
# `process.env` derleme sırasında sabite çevriliyor — çalışma anında verilen
# değer görünmez. Boş kalırsa zorlayıcı politika imzalı PDF URL'ini engeller ve
# doküman tuvali sessizce boş kalır (bkz. apps/web/src/lib/security/csp.ts).
ARG NEXT_PUBLIC_STORAGE_ORIGIN=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_STORAGE_ORIGIN=$NEXT_PUBLIC_STORAGE_ORIGIN \
    NEXT_OUTPUT=standalone
COPY packages/api-client packages/api-client
COPY apps/web apps/web
RUN pnpm --filter @tenderiq/api-client generate \
    && pnpm --filter @tenderiq/web build

# ── Çalıştırma aşaması ───────────────────────────────────────────────────────
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Çalışma imajında paket yöneticisi YOK: `node server.js` dışında hiçbir şey
# koşmuyor. Node taban imajıyla gelen npm CLI kendi bağımlılıklarını (tar,
# sigstore, brace-expansion…) taşır ve bunlar imaj taramasında HIGH/CRITICAL
# olarak çıkar — kullanılmasalar bile saldırı yüzeyidir. Kaldırmak hem taramayı
# temizler hem de gerçekten yüzeyi daraltır (npm'i sildiğimiz için imajda
# `npm install` çalıştırılamaz — bu bilinçlidir).
RUN rm -rf /usr/local/lib/node_modules/npm \
    /usr/local/lib/node_modules/corepack \
    /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack

RUN groupadd --system --gid 1001 nodejs \
    && useradd --system --uid 1001 --gid nodejs nextjs

# Standalone çıktı, izleme köküne göre monorepo yapısını korur.
COPY --from=build --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
