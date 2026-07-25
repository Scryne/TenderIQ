import { FilterX, RotateCw, ShieldAlert, TriangleAlert, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/* ═════ DURUM TASARIMI — DESIGN.md §10 ═════════════════════════════════════
 * Ekranların %70'i "mutlu yol" için tasarlanır; kaliteyi yargılatan %30 budur.
 * Her sayfada beş durum da kodlanır: dolu / boş / filtre-boş / yükleniyor /
 * hata. Bu dosya son dördünü tek dilde konuşturur. ═══════════════════════ */

/**
 * §10.1 — Boş durum. **"Veri bulunamadı" yasak.** Boş durum bir davettir,
 * bir hata değil: ne olacağını söyler ve eylem butonu taşır.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  compact = false,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-border bg-surface px-6 text-center",
        compact ? "py-10" : "py-16",
        className,
      )}
    >
      <span className="grid size-10 place-items-center rounded-md bg-surface-2">
        <Icon aria-hidden className="size-5 text-ink-3" strokeWidth={1.5} />
      </span>
      <p className="mt-4 text-base font-semibold text-ink-1">{title}</p>
      <p className="mt-1.5 max-w-[42ch] text-sm text-ink-2">{description}</p>
      {action !== undefined && <div className="mt-5">{action}</div>}
    </div>
  );
}

/**
 * §10.2 — Filtre sonucu boş. Boş durumdan **ayrı** görünür; kullanıcı hangi
 * durumda olduğunu bilmelidir. Çıkış yolu her zaman "filtreleri temizle".
 */
export function FilterEmptyState({
  query,
  onReset,
  className,
}: {
  /** Ne aradığı geri okunur — "…eşleşen kayıt yok" tek başına yetersiz. */
  query?: string;
  onReset: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border-strong bg-surface px-6 py-12 text-center",
        className,
      )}
    >
      <FilterX aria-hidden className="size-5 text-ink-3" strokeWidth={1.5} />
      <p className="mt-3 text-sm font-medium text-ink-1">
        {query != null && query !== ""
          ? `“${query}” ile eşleşen kayıt yok.`
          : "Seçili filtrelerle eşleşen kayıt yok."}
      </p>
      <p className="mt-1 text-sm text-ink-2">Kayıtlar duruyor — yalnız filtre daraltıyor.</p>
      <Button variant="secondary" size="sm" className="mt-4" onClick={onReset}>
        <FilterX strokeWidth={1.75} />
        Filtreleri temizle
      </Button>
    </div>
  );
}

/**
 * §10.4 — Hata. Üç soruyu bu sırayla cevaplar: ne oldu · neden · nasıl çözülür.
 * Teknik kod gösterilecekse küçük ve altta. Özür dilemez, çözüm söyler (Ek B.2).
 */
export function ErrorState({
  title = "Veriler yüklenemedi",
  description = "Sunucuya ulaşılamıyor. Bağlantınızı kontrol edip yeniden deneyin.",
  detail,
  onRetry,
  className,
  compact = false,
}: {
  title?: string;
  description?: string;
  /** `HTTP 503 · req_a8f2` gibi izleme bilgisi. */
  detail?: string | null;
  onRetry?: () => void;
  className?: string;
  compact?: boolean;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-border bg-surface px-6 text-center",
        compact ? "py-8" : "py-14",
        className,
      )}
    >
      <span className="grid size-10 place-items-center rounded-md bg-danger-weak">
        <TriangleAlert aria-hidden className="size-5 text-danger" strokeWidth={1.75} />
      </span>
      <p className="mt-4 text-base font-semibold text-ink-1">{title}</p>
      <p className="mt-1.5 max-w-[46ch] text-sm text-ink-2">{description}</p>
      {onRetry !== undefined && (
        <Button variant="secondary" size="sm" className="mt-5" onClick={onRetry}>
          <RotateCw strokeWidth={1.75} />
          Yeniden dene
        </Button>
      )}
      {detail != null && detail !== "" && (
        <p className="mt-4 font-mono text-[11px] text-ink-3">{detail}</p>
      )}
    </div>
  );
}

/**
 * Kart içi kısmi hata — sayfa çökmez, yalnız o widget hata gösterir (§10.4).
 * Her grafik/veri kartı bunu kendi sınırında kullanır.
 */
export function InlineError({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2.5 rounded-sm border border-danger/30 bg-danger-weak px-3 py-2.5",
        className,
      )}
    >
      <TriangleAlert
        aria-hidden
        className="mt-0.5 size-4 shrink-0 text-danger"
        strokeWidth={1.75}
      />
      <p className="min-w-0 flex-1 text-sm text-ink-1">{message}</p>
      {onRetry !== undefined && (
        <Button variant="ghost" size="xs" onClick={onRetry} className="shrink-0 text-danger">
          Yeniden dene
        </Button>
      )}
    </div>
  );
}

/** §10.5 — Yetkisiz. Ne yapılacağını söyler, kapıyı yüzüne kapatmaz. */
export function ForbiddenState({
  description = "Bu bölüm için yönetici yetkisi gerekiyor.",
  action,
  className,
}: {
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-border bg-surface px-6 py-14 text-center",
        className,
      )}
    >
      <span className="grid size-10 place-items-center rounded-md bg-surface-2">
        <ShieldAlert aria-hidden className="size-5 text-ink-3" strokeWidth={1.5} />
      </span>
      <p className="mt-4 text-base font-semibold text-ink-1">Erişim yetkiniz yok</p>
      <p className="mt-1.5 max-w-[42ch] text-sm text-ink-2">{description}</p>
      {action !== undefined && <div className="mt-5">{action}</div>}
    </div>
  );
}

/**
 * §10.3 — Yükleniyor. Skeleton gerçek içeriğin şeklini taklit eder: aynı
 * yükseklik, aynı sütun genişlikleri. Spinner değil.
 */
export function TableSkeleton({ rows = 5, columns = 3 }: { rows?: number; columns?: number }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface" aria-busy>
      <div className="flex h-9 items-center gap-4 border-b border-border bg-surface-2 px-3">
        {Array.from({ length: columns }, (_, i) => (
          <Skeleton key={i} className="h-2.5 w-20" />
        ))}
      </div>
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="flex h-12 items-center gap-4 border-b border-border px-3 last:border-b-0">
          <Skeleton className="h-3 flex-1" style={{ maxWidth: `${52 - r * 4}%` }} />
          {Array.from({ length: columns - 1 }, (_, c) => (
            <Skeleton key={c} className="h-3 w-24" />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Bulgu listesi iskeleti — satır anatomisini (metin + meta satırı) taklit eder. */
export function FindingListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-busy>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="rounded-lg border border-border bg-surface p-3.5">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="mt-2 h-3" style={{ width: `${74 - i * 8}%` }} />
          <div className="mt-3 flex gap-2">
            <Skeleton className="h-[22px] w-24" />
            <Skeleton className="h-[22px] w-16" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Kart ızgarası iskeleti — KPI satırı ve plan kartları için. */
export function CardGridSkeleton({ count = 4, height = 108 }: { count?: number; height?: number }) {
  return (
    <div
      className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]"
      aria-busy
    >
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className="rounded-lg" style={{ height }} />
      ))}
    </div>
  );
}
