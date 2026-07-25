import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Sayfa başlığı — DESIGN.md §9.1 iskeleti.
 *
 *   1. Sayfa başlığı H1 .......... 24px/600
 *   2. Alt açıklama (tek satır) .. 14px/ink-2, maks 68 karakter
 *   3. Sağ üstte birincil eylem .. sayfada TEK primary buton (§8.5)
 *
 * Breadcrumb üst çubukta yaşar (AppShell), burada tekrarlanmaz.
 */
export function PageHeader({
  title,
  description,
  meta,
  actions,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  /** Başlığın hemen yanındaki durum rozeti / kaynak sayacı. */
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mb-6 flex flex-wrap items-start justify-between gap-x-6 gap-y-3",
        className,
      )}
    >
      <div className="min-w-0">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1.5">
          <h1 className="min-w-0 truncate font-display text-2xl font-semibold text-ink-1">
            {title}
          </h1>
          {meta}
        </div>
        {description !== undefined && (
          <p className="mt-1.5 max-w-[68ch] text-sm text-ink-2">{description}</p>
        )}
      </div>
      {actions !== undefined && (
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      )}
    </div>
  );
}

/** Bölüm başlığı — kart gruplarının üstünde (§9.1 seviye 2). */
export function SectionHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex flex-wrap items-end justify-between gap-3", className)}>
      <div className="min-w-0">
        <h2 className="font-display text-lg font-semibold text-ink-1">{title}</h2>
        {description !== undefined && (
          <p className="mt-0.5 max-w-[68ch] text-sm text-ink-2">{description}</p>
        )}
      </div>
      {actions !== undefined && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
