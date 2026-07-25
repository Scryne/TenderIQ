import { FileText, Quote } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════════════════════
 * İMZA ÖĞESİ — KAYNAK ŞERİDİ
 *
 * TenderIQ'nun tek ürün vaadi: hiçbir bulgu kaynağından koparılmaz. Tasarımın
 * bunu söylemesi gerekir, sayfa dipnotu olarak değil, ekranın taşıyıcı motifi
 * olarak. Motif üç parçadan oluşur ve HER ekranda aynı biçimde görünür:
 *
 *   ▌  2px mürekkep şerit ....... bulguyu kanıtına bağlayan dikey çizgi
 *   s.42 · md.4.3.1 ............. mono koordinat — dokümandaki tam yer
 *   ▁▁▁▁ ........................ kanıt yıkaması — PDF'te ve alıntıda aynı ton
 *
 * KURAL: şerit yalnız kanıt bağı olan yerde çizilir. Navigasyonda, kart
 * süslemesinde, "biraz hareket olsun" diye ASLA — anlamı seyrekliğinden gelir.
 * (DESIGN.md §7.2 zaten nav'da aktif öğeye ray + zemin birlikte vermeyi yasaklar.)
 * ═══════════════════════════════════════════════════════════════════════════ */

type RailTone = "ink" | "danger" | "warning" | "success" | "info";

const RAIL_COLOR: Record<RailTone, string> = {
  ink: "var(--ink-1)",
  danger: "var(--danger)",
  warning: "var(--warning)",
  success: "var(--success)",
  info: "var(--info)",
};

/**
 * Kanıt şeridi kabı. `tone` bulgunun semantiğini yankılar (yüksek risk →
 * danger); varsayılan mürekkeptir.
 */
export function EvidenceRail({
  tone = "ink",
  tight = false,
  className,
  children,
  ...props
}: {
  tone?: RailTone;
  /** Liste satırlarında şerit satır yüksekliğinin tamamını kaplar. */
  tight?: boolean;
  className?: string;
  children: ReactNode;
} & Omit<React.ComponentProps<"div">, "children">) {
  return (
    <div
      className={cn("rail", tight && "rail-tight", className)}
      style={{ "--rail": RAIL_COLOR[tone] } as CSSProperties}
      {...props}
    >
      {children}
    </div>
  );
}

/**
 * Kaynak koordinatı — `s. 42 · 4.3.1`. Mono dizilir çünkü bu bir *konum*dur,
 * cümle değil; sütun halinde alt alta geldiğinde hizalanması gerekir.
 * Doküman adı verildiyse önüne eklenir ve uzun adlar kırpılır.
 */
export function SourceRef({
  page,
  section,
  documentName,
  className,
  as: Tag = "span",
}: {
  page: number;
  section?: string | null;
  documentName?: string | null;
  className?: string;
  as?: "span" | "div";
}) {
  const hasSection = section != null && section.trim() !== "";
  const label = hasSection
    ? `Sayfa ${page}, madde ${section.trim()}`
    : `Sayfa ${page}`;

  return (
    <Tag
      title={documentName != null ? `${documentName} · ${label}` : label}
      className={cn(
        "inline-flex min-w-0 items-center gap-1.5 font-mono text-[11px] leading-4 text-ink-3",
        className,
      )}
    >
      <FileText aria-hidden className="size-3 shrink-0" strokeWidth={1.75} />
      {documentName != null && documentName !== "" && (
        <>
          <span className="max-w-32 truncate">{documentName}</span>
          <span aria-hidden className="text-border-strong">
            ·
          </span>
        </>
      )}
      <span className="whitespace-nowrap">s.{page}</span>
      {hasSection && (
        <>
          <span aria-hidden className="text-border-strong">
            ·
          </span>
          <span className="max-w-40 truncate">{section.trim()}</span>
        </>
      )}
    </Tag>
  );
}

/**
 * Kanıt alıntısı. Şartnamenin kendi cümlesi — parafraz değil. Kanıt yıkaması
 * PDF katmanındaki vurguyla **aynı** tonu kullanır; kullanıcı iki yüzey
 * arasında gidip gelirken aynı işareti arar.
 */
export function EvidenceQuote({
  quote,
  page,
  section,
  documentName,
  className,
}: {
  quote: string;
  page: number;
  section?: string | null;
  documentName?: string | null;
  className?: string;
}) {
  return (
    <figure className={cn("min-w-0", className)}>
      <EvidenceRail>
        <Quote aria-hidden className="mb-1.5 size-3.5 text-ink-3" strokeWidth={1.75} />
        <blockquote className="text-sm leading-5 text-ink-1">
          <span className="evidence-mark box-decoration-clone px-0.5">{quote}</span>
        </blockquote>
        <figcaption className="mt-2">
          <SourceRef page={page} section={section} documentName={documentName} />
        </figcaption>
      </EvidenceRail>
    </figure>
  );
}

/**
 * Kanıt sayacı — "9 bulgunun 9'u kaynağa bağlı". Ürün vaadinin ölçülebilir
 * hali; panelde ve inceleme başlığında görünür.
 */
export function EvidenceCoverage({
  grounded,
  total,
  className,
}: {
  grounded: number;
  total: number;
  className?: string;
}) {
  const complete = total > 0 && grounded === total;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono text-[11px] leading-4",
        complete ? "text-ink-3" : "text-warning",
        className,
      )}
      title={
        complete
          ? "Her bulgu dokümandaki bir sayfa ve maddeye bağlı."
          : "Bazı bulguların kaynak bağı eksik; inceleme sırasında doğrulayın."
      }
    >
      <span
        aria-hidden
        className={cn(
          "size-1.5 rounded-full",
          complete ? "bg-success" : "bg-warning",
        )}
      />
      {grounded}/{total} kaynağa bağlı
    </span>
  );
}
