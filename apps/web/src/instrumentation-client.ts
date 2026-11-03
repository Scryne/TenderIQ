// Sentry tarayıcı başlatması (Next 15.3+ instrumentation-client kancası).
// DSN boşsa no-op; PII gönderilmez (SENTRY_DATA_COLLECTION), session replay bilinçli olarak kapalı.
import * as Sentry from "@sentry/nextjs";

import { SENTRY_DATA_COLLECTION } from "@/lib/sentry-data-collection";

if (process.env.NEXT_PUBLIC_SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    environment: process.env.NODE_ENV,
    dataCollection: SENTRY_DATA_COLLECTION,
    tracesSampleRate: 0,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
  });
}

// App Router gezinmelerini Sentry'nin hata bağlamına işler.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
