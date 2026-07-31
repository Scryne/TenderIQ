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
  noteFull,
  noteNear,
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
  /** Kota dolduğunda yazılan cümle. Çıkış yolu boyuta göre değişir. */
  noteFull?: string;
  /** Eşiğe yaklaşıldığında yazılan cümle. */
  noteNear?: string;
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
            ? (noteFull ?? "Kota doldu. Yeni doküman yüklemek için planı yükseltin.")
            : (noteNear ?? "Kotanın %80'i kullanıldı.")}
        </p>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
 * BÜTÇE ÖLÇERİ — bu ekranın imza öğesi.
 *
 * Ürüne özgü tek karar şu: **rezerve tutar ne "harcanmış" ne de "kalan"dır.**
 * Süren analizler için ayrılmıştır; iş bitince serbest kalır ve yerine gerçek
 * maliyet yazılır — yani harcanmadı. Ama o parayla yeni iş de başlatılamaz
 * (kabul sınırı `tavan − rezervasyon`) — yani kalan da değil. İki uçtan birine
 * yuvarlamak yanlış bilgi olurdu: harcamaya katmak "param bitti" dedirtir,
 * kalana katmak olmayan bir hakkı vadeder.
 *
 * Çözüm ayrı SEGMENT + ayrı DOKU: birincil seri (harcanan) düz dolgu, ikincil
 * seri (ayrılan) 45° taralı dolgu — DESIGN.md §8.26.2'nin "tahmin / geçen dönem
 * / hedef gibi ikincil serilerde tarama kullan" kuralı. Doku aynı zamanda renk
 * körü güvenliği sağlar (§12): iki segment yalnız tonla değil dokuyla ayrışır.
 * Ve §8.13 gereği açıklama listesi HER ZAMAN yazılır — çubuk tek başına okunmaz.
 *
 * §13.6 sinyal testi: bu kararı herhangi bir dashboard için de verir miydim? —
 * Hayır. Çoğu üründe "rezerve" kavramı yok; olsa da harcamaya katılır. Buradaki
 * ayrım, tavanın nasıl uygulandığının doğrudan görsel karşılığı.
 * ═══════════════════════════════════════════════════════════════════════════ */

/** Taralı ikincil segment: 45°, 1,5px çizgi, 5px aralık; çizgi rengi `currentColor`. */
const HATCH_IMAGE = "repeating-linear-gradient(45deg, currentColor 0 1.5px, transparent 1.5px 5px)";

const HATCH: Record<MetricTone, string> = {
  ink: "text-accent bg-accent/12",
  success: "text-success bg-success/12",
  warning: "text-warning bg-warning/12",
  danger: "text-danger bg-danger/12",
  info: "text-info bg-info/12",
};

export function BudgetMeter({
  label,
  spent,
  reserved,
  limit,
  remaining,
  tone = "ink",
  formatValue,
  splitValue,
  unlimitedLabel = "Sınırsız",
  className,
}: {
  label: string;
  spent: number;
  /** Süren işler için AYRILMIŞ tutar — harcanmış DEĞİL. */
  reserved: number;
  /** `null` = sınırsız kademe; çubuk çizilmez. */
  limit: number | null;
  /** `tavan − harcanan − ayrılan`; sınırsız kademede `null`. */
  remaining: number | null;
  tone?: Extract<MetricTone, "ink" | "warning" | "danger">;
  formatValue: (value: number) => string;
  /** Ana sayıyı birim/rakam olarak ayırır (§6.5: birim küçük ve muted). */
  splitValue: (value: number) => { symbol: string; amount: string };
  unlimitedLabel?: string;
  className?: string;
}) {
  const hero = splitValue(spent);
  const scale = limit === null || limit <= 0 ? 0 : 100 / limit;
  const spentPercent = Math.min(100, spent * scale);
  const reservedPercent = Math.min(100 - spentPercent, reserved * scale);
  const usedPercent = Math.round(spentPercent + reservedPercent);

  return (
    <div className={cn("min-w-0", className)}>
      <span className="text-overline text-ink-3">{label}</span>

      {/* Tavan hero'nun YANINDA durur, kartın sağ ucunda değil. 1440'ta sağ uca
          yaslanmış bir "₺25,00 tavan", harcamadan ~1000px uzağa düşüyordu:
          iki sayı arasındaki ilişki mesafeyle anlatılmaz. §6.5: birim sayıdan
          küçük ve muted. */}
      <p className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="flex items-baseline gap-1">
          <span className="text-base font-medium text-ink-3">{hero.symbol}</span>
          <span className="font-display text-3xl leading-none font-semibold text-ink-1 tabular-nums">
            {hero.amount}
          </span>
        </span>
        <span className="text-sm text-ink-2">harcandı</span>
        <span className="font-mono text-xs text-ink-3">
          {limit === null ? `· ${unlimitedLabel}` : `· ${formatValue(limit)} tavan`}
        </span>
      </p>

      {limit !== null && (
        <div
          role="progressbar"
          aria-valuenow={usedPercent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={label}
          aria-valuetext={`${formatValue(spent)} harcandı, ${formatValue(reserved)} ayrıldı, tavan ${formatValue(limit)}`}
          className="mt-3 flex h-2 overflow-hidden rounded-full bg-surface-2"
        >
          <span className={cn("h-full", BAR[tone])} style={{ width: `${spentPercent}%` }} />
          <span
            className={cn("h-full", HATCH[tone])}
            style={{ width: `${reservedPercent}%`, backgroundImage: HATCH_IMAGE }}
          />
        </div>
      )}

      {/* §8.13: açıklama listesi her zaman yazılır — bilgi yalnız renge/dokuya
          bırakılmaz. Ayrılan tutar SIFIRSA satır yazılmaz; olmayan bir kavramı
          her açılışta açıklamak gürültüdür. */}
      <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs">
        <LegendItem swatch={<span className={cn("block h-2 w-3 rounded-sm", BAR[tone])} />} term="Harcanan">
          {formatValue(spent)}
        </LegendItem>
        {reserved > 0 && (
          <LegendItem
            swatch={
              <span
                className={cn("block h-2 w-3 rounded-sm", HATCH[tone])}
                style={{ backgroundImage: HATCH_IMAGE }}
              />
            }
            term="Ayrılan"
          >
            {formatValue(reserved)}
          </LegendItem>
        )}
        {/* Kalan örneği `border` ile çizilirken 12×8'lik kutu ince bir dikey
            çizgiye dönüşüyor ve açıklama listesinde AYIRICI gibi okunuyordu
            (375'te satır başında yalnız bir "|" kalıyor). `border-strong`
            WCAG 1.4.11'in istediği 3:1'i de sağlar. */}
        <LegendItem
          swatch={
            <span className="block h-2 w-3 rounded-sm border border-border-strong bg-surface-2" />
          }
          term="Kalan"
        >
          {remaining === null ? unlimitedLabel : formatValue(remaining)}
        </LegendItem>
      </dl>
    </div>
  );
}

function LegendItem({
  swatch,
  term,
  children,
}: {
  swatch: ReactNode;
  term: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center gap-1.5">
      {/* `flex` — sarmalayıcı `inline` kalırsa içindeki 12×8'lik örnek satır içi
          bir kutuya düşer, genişliği YOK SAYILIR ve üç örnek de ince bir dikey
          çizgi olarak çizilir (tur 2 çekiminde böyleydi: §8.13'ün zorunlu
          kıldığı açıklama listesi fiilen yoktu). */}
      <span aria-hidden className="flex shrink-0">
        {swatch}
      </span>
      <dt className="text-ink-2">{term}</dt>
      <dd className="font-mono text-ink-1 tabular-nums">{children}</dd>
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
