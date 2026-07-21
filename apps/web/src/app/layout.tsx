import type { Metadata } from "next";
import { JetBrains_Mono, Public_Sans } from "next/font/google";
import type { ReactNode } from "react";

import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

// Tasarım sistemi tip seçimi (DESIGN BRIEF): Public Sans UI, JetBrains Mono
// sayısallar/ihale no/kaynak referansları. globals.css --font-* ile eşlenir.
const publicSans = Public_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-public-sans",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin", "latin-ext"],
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "TenderIQ",
  description: "Yapay zekâ destekli ihale ve RFP analiz platformu",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <body
        className={`${publicSans.variable} ${jetbrainsMono.variable} min-h-screen antialiased`}
      >
        <Providers>{children}</Providers>
        <Toaster position="bottom-right" />
      </body>
    </html>
  );
}
