import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { ThemeToggle } from "@/components/theme-toggle";

export const metadata: Metadata = {
  title: "Tasarım kataloğu",
  // Kalıcı bir QA yüzeyi; arama motorlarına girmemesi gerekir.
  robots: { index: false, follow: false },
};

const LINKS = [
  { href: "/design/tokens", label: "Token'lar" },
  { href: "/design/preview", label: "Ekran önizlemeleri" },
];

/**
 * Tasarım kataloğu kabuğu.
 *
 * Neden var: DESIGN.md §14 görsel doğrulama döngüsü, ekranların BEŞ durumunun
 * da (dolu / boş / filtre-boş / yükleniyor / hata) gözle görülmesini şart
 * koşuyor. Bu durumların çoğu canlı backend'de tetiklenemez — kotası dolmuş
 * bir hesap ya da 503 veren bir uç sipariş üzerine üretilemez. Katalog, sunum
 * bileşenlerini mock veriyle besleyerek hepsini tek ekranda görünür kılar ve
 * `scripts/shoot.mjs` bunları backend olmadan çekebilir.
 */
export default function DesignLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-40 flex h-14 items-center gap-4 border-b border-border bg-canvas/90 px-5 backdrop-blur-sm">
        <span className="font-display text-sm font-semibold text-ink-1">
          TenderIQ · tasarım kataloğu
        </span>
        <nav className="flex items-center gap-1">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-sm px-2.5 py-1.5 text-sm text-ink-2 transition-colors duration-[120ms] hover:bg-hover hover:text-ink-1"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Link
            href="/"
            className="rounded-sm px-2.5 py-1.5 text-sm text-ink-3 hover:text-ink-1"
          >
            Siteye dön
          </Link>
          <ThemeToggle />
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1440px] px-5 py-8 lg:px-8">{children}</main>
    </div>
  );
}
