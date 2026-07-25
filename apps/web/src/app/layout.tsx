import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Instrument_Sans, Inter_Tight } from "next/font/google";
import type { ReactNode } from "react";

import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

/* Yön A "Mürekkep" tip eşleşmesi (DESIGN.md §6.2 · "Kurumsal, ciddi" satırı).
 * Üçünde de `latin-ext` alt kümesi doğrulandı — İ ı Ğ ğ Ş ş Ç ç Ö ö Ü ü tam;
 * eksik glif olsaydı tarayıcı fallback yapar ve arayüzde iki font karışırdı (§6.1). */
const instrumentSans = Instrument_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-instrument-sans",
  display: "swap",
});
const interTight = Inter_Tight({
  subsets: ["latin", "latin-ext"],
  variable: "--font-inter-tight",
  display: "swap",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "TenderIQ",
    template: "%s · TenderIQ",
  },
  description: "Yapay zekâ destekli ihale ve RFP analizi — her bulgu kaynağına bağlı.",
};

// Ham hex muafiyeti (§15): Next metadata API'si burada literal ister, CSS
// değişkeni kabul etmez. Değerler --canvas token'larıyla birebir aynıdır.
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fafaf9" },
    { media: "(prefers-color-scheme: dark)", color: "#0b0b0c" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <body
        className={`${instrumentSans.variable} ${interTight.variable} ${plexMono.variable} min-h-screen antialiased`}
      >
        <Providers>{children}</Providers>
        <Toaster />
      </body>
    </html>
  );
}
