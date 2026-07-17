// Sentry tarayıcı başlatması (Next 15.3+ instrumentation-client kancası).
// DSN boşsa no-op; PII gönderilmez, session replay bilinçli olarak kapalı.
import * as Sentry from "@sentry/nextjs";

if (process.env.NEXT_PUBLIC_SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    environment: process.env.NODE_ENV,
    sendDefaultPii: false,
    tracesSampleRate: 0,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
  });
}

// App Router gezinmelerini Sentry'nin hata bağlamına işler.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
