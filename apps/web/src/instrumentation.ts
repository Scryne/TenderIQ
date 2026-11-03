// Sentry sunucu/edge başlatması (Next instrumentation kancası).
// NEXT_PUBLIC_SENTRY_DSN boşsa tamamen no-op — dev kurulumu Sentry gerektirmez.
// PII maskeleme: SENTRY_DATA_COLLECTION (IP/gövde/kişisel başlık gönderilmez); kiracı bağlamı
// backend olaylarında taşınır (tarayıcı JWT'yi hiç görmez — httpOnly cookie).
import * as Sentry from "@sentry/nextjs";

import { assertRuntimeEnv } from "@/config/env";
import { SENTRY_DATA_COLLECTION } from "@/lib/sentry-data-collection";

export async function register() {
  // Sunucu açılışında zorunlu değişkenler doğrulanır; eksikse süreç BAŞLAMAZ.
  // Derleme-zamanı olanlar da tekrar bakılır: derleme başka bir aşamada
  // yapılmış olabilir ve imaj elden ele geçer (bkz. `config/env.ts`).
  assertRuntimeEnv();

  if (!process.env.NEXT_PUBLIC_SENTRY_DSN) return;
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    environment: process.env.NODE_ENV,
    dataCollection: SENTRY_DATA_COLLECTION,
    tracesSampleRate: 0, // şimdilik yalnız hata izleme (backend ile aynı karar)
  });
}

// App Router istek hatalarını (RSC/route handler) Sentry'ye iletir.
export const onRequestError = Sentry.captureRequestError;
