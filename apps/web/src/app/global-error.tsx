"use client";

// Kök layout dahil her şeyin çöktüğü durumda gösterilen son çare hata sayfası.
// Render hatası Sentry'ye raporlanır (DSN yoksa captureException no-op'tur).
//
// Burada token utility'lerine ya da bileşenlere GÜVENİLEMEZ: bu sayfa kök
// layout çöktüğünde de çalışmak zorundadır, dolayısıyla globals.css'in
// yüklendiği varsayılamaz. Tek istisna olarak satır içi stil kullanılır ve
// renkler DESIGN.md §5.2 token değerleriyle birebir aynı tutulur (§15 ham hex
// yasağının bilinçli, gerekçelendirilmiş tek muafiyeti).
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
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#fafaf9",
          color: "#16171a",
          fontFamily: '"Segoe UI", system-ui, sans-serif',
          padding: "24px",
        }}
      >
        <main style={{ maxWidth: "440px", textAlign: "center" }}>
          <h1 style={{ margin: 0, fontSize: "20px", fontWeight: 600, letterSpacing: "-0.01em" }}>
            Beklenmeyen bir hata oluştu
          </h1>
          <p style={{ margin: "10px 0 0", fontSize: "14px", lineHeight: "22px", color: "#43454c" }}>
            Hata kaydedildi. Sayfayı yeniden yüklemeyi deneyin; sorun sürerse birkaç dakika sonra
            yeniden girin.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: "20px",
              height: "36px",
              padding: "0 14px",
              fontSize: "14px",
              fontWeight: 500,
              color: "#ffffff",
              background: "#16171a",
              border: "none",
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            Yeniden dene
          </button>
          {error.digest !== undefined && (
            <p
              style={{
                margin: "16px 0 0",
                fontFamily: "ui-monospace, monospace",
                fontSize: "11px",
                color: "#6c6e75",
              }}
            >
              req_{error.digest}
            </p>
          )}
        </main>
      </body>
    </html>
  );
}
