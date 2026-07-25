import Link from "next/link";
import type { ReactNode } from "react";

import { EvidenceRail, SourceRef } from "@/components/evidence";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** Marka işareti — kaynağa bağlı satır motifinin en küçük hali. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "grid size-8 shrink-0 place-items-center rounded-md bg-accent text-ink-on-accent",
        className,
      )}
    >
      <svg viewBox="0 0 20 20" className="size-4" aria-hidden fill="none">
        <path
          d="M3 4.5h14M3 10h10M3 15.5h6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <circle cx="16.5" cy="15.5" r="1.75" fill="currentColor" />
      </svg>
    </span>
  );
}

export function BrandLockup({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2.5" aria-label="TenderIQ ana sayfa">
      <BrandMark />
      <span className="font-display text-base font-semibold tracking-tight text-ink-1">
        TenderIQ
      </span>
    </Link>
  );
}

/**
 * Auth iskeleti — DESIGN.md §9.6.
 *
 * Sol: form, maks 400px, dikey ortalı. Sağ: marka alanı — stok fotoğraf değil,
 * ürünün kendi imza motifi ve tek bir tipografik ifade. Sağ sütun 1024px
 * altında tamamen kalkar; giriş ekranında kaydırmaya değecek içerik değildir.
 */
export function AuthLayout({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="grid min-h-screen bg-canvas lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
      {/* Marka, form ve alt not AYNI sol kenarda hizalanır ve blok olarak
          sütunda ortalanır. Formu tek başına ortalayıp markayı sola bırakmak
          kompozisyonu dağıtıyordu. */}
      <main className="flex min-w-0 flex-col items-center px-5 py-8 sm:px-10">
        <div className="w-full max-w-[400px]">
          <BrandLockup />
        </div>
        <div className="flex w-full max-w-[400px] flex-1 flex-col justify-center py-10">
          <h1 className="font-display text-2xl font-semibold text-ink-1">{title}</h1>
          {description !== undefined && (
            <p className="mt-2 max-w-[46ch] text-sm text-ink-2">{description}</p>
          )}
          <div className="mt-7">{children}</div>
        </div>
        {footer !== undefined && (
          <div className="w-full max-w-[400px] text-xs text-ink-3">{footer}</div>
        )}
      </main>

      <aside className="relative hidden overflow-hidden border-l border-border bg-surface lg:flex lg:flex-col lg:justify-center lg:px-12">
        <div aria-hidden className="bg-rule pointer-events-none absolute inset-0 opacity-60" />
        <div className="relative max-w-[440px]">
          <p className="font-display text-3xl leading-tight font-semibold tracking-tight text-balance text-ink-1">
            Bir bulgu, kaynağını gösteremiyorsa bulgu değildir.
          </p>
          <p className="mt-4 max-w-[52ch] text-sm text-ink-2">
            TenderIQ her gereksinimi, her riski ve her teslim belgesini şartnamedeki tam sayfa ve
            maddeye bağlar. Kararı siz verirsiniz — kanıtı ürün getirir.
          </p>

          {/* İmza motifinin canlı örneği: gerçek ekranın bir parçası. */}
          <div className="mt-8 rounded-lg border border-border bg-surface p-4 shadow-sm">
            <EvidenceRail tone="danger">
              <p className="text-[13.5px] leading-5 text-ink-1">
                Yüklenici, sözleşme bedelinin %6&apos;sı oranında kesin teminat verecektir.
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <SourceRef page={42} section="4.3.1" />
                <Badge tone="danger" dot>
                  Yüksek risk
                </Badge>
              </div>
            </EvidenceRail>
          </div>
        </div>
      </aside>
    </div>
  );
}

/**
 * Tek amaçlı sayfa kabuğu (e-posta doğrulama, davet kabulü). Form değil,
 * tek bir sonucu bildirir — ortalanmış tek sütun doğru biçimdir.
 */
export function AuthNotice({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-canvas px-5 py-10">
      <div className="w-full max-w-[440px]">
        <BrandLockup />
        <div className="mt-6 rounded-lg border border-border bg-surface p-6">
          <h1 className="font-display text-xl font-semibold text-ink-1">{title}</h1>
          <div className="mt-3 flex flex-col gap-4 text-sm text-ink-2">{children}</div>
        </div>
      </div>
    </main>
  );
}
