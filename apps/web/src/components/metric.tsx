import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════════════════════
 * METRİK KARTI — DESIGN.md §8.1 · Varyant D (ilerlemeli), tek varyant.
 *
 * SAPMA VE GEREKÇESİ (§8.1): spec üçüncü satırda karşılaştırma dönemli bir
 * delta ister ("↑ %12,4 geçen haftaya göre"). Bu üründe dönemsel karşılaştırma
 * YOK — bir ihale tekil bir olaydır, geçen haftaya göre "artmaz". Delta
 * uydurmak §13.4'ün yasakladığı sahte içerik olurdu. Üçüncü satır bunun yerine
 * sayıyı karara bağlayan bir NİTELEYİCİ taşır: "en yakını 4 gün sonra",
 * "3'ü zorunlu belge". Bağlamsız sayı değersizdir — kural aynı kalıyor,
 * bağlamın kaynağı değişiyor.
 * ═══════════════════════════════════════════════════════════════════════════ */

type MetricTone = "ink" | "success" | "warning" | "danger" | "info";

const ICON_BOX: Record<MetricTone, string> = {
  ink: "bg-surface-2 text-ink-2",
  success: "bg-success-weak text-success",
  warning: "bg-warning-weak text-warning",
  danger: "bg-danger-weak text-danger",
  info: "bg-info-weak text-info",
};

const QUALIFIER: Record<MetricTone, string> = {
  ink: "text-ink-3",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
};

const BAR: Record<MetricTone, string> = {
  ink: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
};

export function MetricCard({
  label,
  value,
  unit,
  qualifier,
  tone = "ink",
  icon: Icon,
  progress,
  progressLabel,
  className,
}: {
  /** Küçük etiket. Elle büyük harfle yazılır — CSS uppercase Türkçe'de bozuk (Ek B.3). */
  label: string;
  value: ReactNode;
  /** Birim sayıdan küçük ve muted olur (§6.5): "gün", "₺", "%". */
  unit?: string;
  /** Sayıyı karara bağlayan tek satır. Bağlamsız sayı değersizdir. */
  qualifier?: string;
  tone?: MetricTone;
  icon?: LucideIcon;
  /** 0-100. Verildiğinde kartın alt kenarına yapışık 4px çubuk çizilir. */
  progress?: number;
  /** Ekran okuyucu için çubuğun anlamı; görsel olarak yazılmaz (§8.1.1 D). */
  progressLabel?: string;
  className?: string;
}) {
  const clamped =
    progress === undefined ? undefined : Math.max(0, Math.min(100, Math.round(progress)));

  return (
    <div
      className={cn(
        "relative flex min-w-0 flex-col overflow-hidden rounded-lg border border-border bg-surface p-5",
        className,
      )}
    >
      {/* Etiket ile ikon kutusu optik hizalanır: kutu 36px, etiket 11px —
          items-start bırakılırsa etiket kutunun üst kenarında yüzer (§13.3). */}
      <div className="flex min-h-9 items-center justify-between gap-3">
        <span className="text-overline min-w-0 text-ink-3">{label}</span>
        {Icon !== undefined && (
          <span
            className={cn(
              "grid size-9 shrink-0 place-items-center rounded-md",
              ICON_BOX[tone],
            )}
          >
            <Icon aria-hidden className="size-[18px]" strokeWidth={1.75} />
          </span>
        )}
      </div>

      <p className="mt-3 flex min-w-0 items-baseline gap-1.5">
        <span className="truncate font-display text-3xl font-semibold text-ink-1">{value}</span>
        {unit !== undefined && (
          <span className="shrink-0 text-base font-medium text-ink-3">{unit}</span>
        )}
      </p>

      {qualifier !== undefined && (
        <p className={cn("mt-2 truncate text-xs", QUALIFIER[tone])} title={qualifier}>
          {qualifier}
        </p>
      )}

      {clamped !== undefined && (
        <div
          role="progressbar"
          aria-valuenow={clamped}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={progressLabel ?? label}
          className="absolute inset-x-0 bottom-0 h-1 bg-surface-2"
        >
          <div
            className={cn("h-full transition-[width] duration-300", BAR[tone])}
            style={{ width: `${clamped}%` }}
          />
        </div>
      )}
    </div>
  );
}

/**
 * Kota ölçeri — `/usage` ve panelde. Kart değil satır bileşenidir; birden çok
 * kotayı alt alta hizalar. Eşiğe göre ton değiştirir (%80 uyarı, %100 tehlike).
 */
export function Meter({
  label,
  used,
  limit,
  formatValue,
  unlimitedLabel = "Sınırsız",
  showThresholdNote = true,
  className,
}: {
  label: string;
  used: number;
  /** `null` = sınırsız; çubuk çizilmez, sayı yazılır. */
  limit: number | null;
  formatValue: (value: number) => string;
  unlimitedLabel?: string;
  /**
   * Eşik uyarısı metnini yazar. Birden çok ölçer alt alta dizildiğinde aynı
   * cümlenin tekrarlanması gürültü olduğu için ikinci ve sonrakiler için
   * kapatılır; çubuk rengi uyarıyı zaten taşır.
   */
  showThresholdNote?: boolean;
  className?: string;
}) {
  const ratio = limit === null || limit === 0 ? 0 : used / limit;
  const percent = Math.min(100, Math.round(ratio * 100));
  const tone: MetricTone = ratio >= 1 ? "danger" : ratio >= 0.8 ? "warning" : "ink";

  return (
    <div className={cn("min-w-0", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate text-sm font-medium text-ink-2">{label}</span>
        <span className="shrink-0 font-mono text-sm text-ink-1">
          {formatValue(used)}
          <span className="text-ink-3">
            {" / "}
            {limit === null ? unlimitedLabel : formatValue(limit)}
          </span>
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={limit === null ? undefined : percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label} kullanımı`}
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-2"
      >
        {limit !== null && (
          <div
            className={cn("h-full rounded-full transition-[width] duration-300", BAR[tone])}
            style={{ width: `${percent}%` }}
          />
        )}
      </div>
      {tone !== "ink" && showThresholdNote && (
        <p className={cn("mt-1.5 text-xs", QUALIFIER[tone])}>
          {ratio >= 1
            ? "Kota doldu. Yeni doküman yüklemek için planı yükseltin."
            : "Kotanın %80'i kullanıldı."}
        </p>
      )}
    </div>
  );
}

/**
 * Sıralı dağılım listesi — DESIGN.md §8.12.
 *
 * Donut'a göre her zaman daha okunaklı; 5'ten fazla kategori varsa donut
 * yerine bu kullanılır. **Sıralama her zaman büyükten küçüğe** — alfabetik
 * sıralama bu bileşenin amacını yok eder.
 */
export function DistributionList({
  items,
  formatValue,
  className,
}: {
  items: { label: string; value: number; tone?: MetricTone }[];
  formatValue: (value: number) => string;
  className?: string;
}) {
  const sorted = [...items].sort((a, b) => b.value - a.value);
  const max = sorted[0]?.value ?? 0;

  return (
    <ul className={cn("flex flex-col gap-2.5", className)}>
      {sorted.map((item) => (
        <li key={item.label} className="grid grid-cols-[minmax(0,35%)_1fr_auto] items-center gap-3">
          <span className="truncate text-sm text-ink-2" title={item.label}>
            {item.label}
          </span>
          <span className="h-1.5 overflow-hidden rounded-full bg-surface-2">
            <span
              className={cn("block h-full rounded-full", BAR[item.tone ?? "ink"])}
              style={{ width: max === 0 ? "0%" : `${Math.max(2, (item.value / max) * 100)}%` }}
            />
          </span>
          <span className="shrink-0 font-mono text-sm text-ink-1">{formatValue(item.value)}</span>
        </li>
      ))}
    </ul>
  );
}
