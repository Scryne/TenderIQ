"use client";

// Kök layout dahil her şeyin çöktüğü durumda gösterilen son çare hata sayfası.
// Render hatası Sentry'ye raporlanır (DSN yoksa captureException no-op'tur).
import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="tr">
      <body className="flex min-h-screen items-center justify-center">
        <div className="space-y-4 text-center">
          <h1 className="text-xl font-semibold">Beklenmeyen bir hata oluştu</h1>
          <p className="text-sm text-neutral-500">
            Hata kaydedildi. Sorun sürerse lütfen daha sonra tekrar deneyin.
          </p>
          <button
            type="button"
            onClick={reset}
            className="rounded-md border px-4 py-2 text-sm hover:bg-neutral-100"
          >
            Tekrar dene
          </button>
        </div>
      </body>
    </html>
  );
}
