"use client";

import {
  CalendarClock,
  FileStack,
  Gauge,
  Loader,
  ScanSearch,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { EvidenceRail, SourceRef } from "@/components/evidence";
import { MetricCard, Meter } from "@/components/metric";
import { SectionHeader } from "@/components/shell/page-header";
import { CardGridSkeleton, EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatDeadline, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export type DeadlineItem = {
  id: string;
  tenderId: string;
  tenderTitle: string;
  label: string;
  valueText: string;
  /** Serbest metinden ayrıştırılabildiyse tarih; ayrıştırılamadıysa null. */
  date: Date | null;
  page: number;
  section: string | null;
};

export type ExposureItem = {
  id: string;
  tenderId: string;
  tenderTitle: string;
  text: string;
  /** "risk" = sözleşme riski · "compliance" = karşılanmayan gereksinim. */
  source: "risk" | "compliance";
  severity: "high" | "unmet";
  page: number;
  section: string | null;
};

export type PanelData = {
  totalTenders: number;
  reviewReady: number;
  analyzing: number;
  drafts: number;
  quota: { label: string; used: number; limit: number | null }[];
  periodEnd: string | null;
  deadlines: DeadlineItem[];
  exposures: ExposureItem[];
  inProgress: { id: string; title: string }[];
  /** Toplam bulgu ve bunların kaçının kaynağa bağlı olduğu. */
  detailLoading: boolean;
};

/* ═══════════════════════════════════════════════════════════════════════════
 * PANEL — DESIGN.md §9.2
 *
 * BİRİNCİL İŞ (BRIEF): "Beni eleyecek ya da riske atacak madde hangisi ve
 * kanıtı nerede?" — 5 saniyede.
 *
 * Bu yüzden ekranın sol-üst çeyreğindeki en büyük tipografi "kaç ihalem var"
 * değil, **eleme riski taşıyan açık madde sayısıdır**; hemen altındaki liste
 * de o maddeleri kaynak koordinatıyla birlikte açar. Panelin geri kalanı
 * (kota, süren analizler) ikincil sütuna iner.
 *
 * SAPMA: §9.2 "selamlama + tarih aralığı seçici" ister. Bu üründe tarih
 * aralığı diye bir kavram yok — ihaleler kesikli olaylar, zaman serisi değil.
 * Selamlama satırı da her açılışta okunan boş bir satırdır; yerine doğrudan
 * birincil iş konur.
 * ═══════════════════════════════════════════════════════════════════════════ */

export function PanelView({
  data,
  state,
  errorMessage,
  onRetry,
  newTenderAction,
}: {
  data: PanelData;
  state: "ready" | "loading" | "error";
  errorMessage?: string;
  onRetry?: () => void;
  newTenderAction: ReactNode;
}) {
  if (state === "loading") {
    return (
      <div className="flex flex-col gap-6">
        <CardGridSkeleton count={4} />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
          <Skeleton className="h-80 rounded-lg" />
          <Skeleton className="h-80 rounded-lg" />
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <ErrorState
        title="Panel yüklenemedi"
        description={errorMessage ?? "Sunucuya ulaşılamıyor. Bağlantınızı kontrol edip yeniden deneyin."}
        onRetry={onRetry}
      />
    );
  }

  if (data.totalTenders === 0) {
    return (
      <EmptyState
        icon={FileStack}
        title="Panel ilk ihalenizle açılır"
        description="Bir ihale projesi oluşturup şartnameyi yükleyin. Son teklif tarihleri ve eleme riski taşıyan maddeler burada toplanır."
        action={newTenderAction}
      />
    );
  }

  const quotaPrimary = data.quota[0];
  const quotaPercent =
    quotaPrimary === undefined || quotaPrimary.limit === null || quotaPrimary.limit === 0
      ? undefined
      : (quotaPrimary.used / quotaPrimary.limit) * 100;

  return (
    <div className="flex flex-col gap-8">
      {/* ── Birinci seviye: dört metrik, en solda birincil iş ─────────────── */}
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
        <MetricCard
          label="ELEME RİSKİ"
          value={data.detailLoading ? "…" : formatNumber(data.exposures.length)}
          unit="madde"
          tone={data.exposures.length > 0 ? "danger" : "success"}
          icon={ShieldAlert}
          qualifier={
            data.detailLoading
              ? "Bulgular taranıyor"
              : data.exposures.length === 0
                ? "Açık madde yok"
                : `${formatNumber(new Set(data.exposures.map((item) => item.tenderId)).size)} ihalede`
          }
        />
        <MetricCard
          label="İNCELEMEYE HAZIR"
          value={formatNumber(data.reviewReady)}
          unit="ihale"
          tone={data.reviewReady > 0 ? "info" : "ink"}
          icon={ScanSearch}
          qualifier={`Toplam ${formatNumber(data.totalTenders)} proje içinde`}
        />
        <MetricCard
          label="ANALİZ SÜRÜYOR"
          value={formatNumber(data.analyzing)}
          unit="ihale"
          tone={data.analyzing > 0 ? "info" : "ink"}
          icon={Loader}
          qualifier={
            data.analyzing === 0 ? "Bekleyen işlem yok" : "Bittiğinde panelde belirir"
          }
        />
        <MetricCard
          label="AYLIK KOTA"
          value={quotaPrimary === undefined ? "—" : formatNumber(quotaPrimary.used)}
          unit={
            quotaPrimary === undefined
              ? undefined
              : `/ ${quotaPrimary.limit === null ? "sınırsız" : formatNumber(quotaPrimary.limit)}`
          }
          icon={Gauge}
          tone={quotaPercent !== undefined && quotaPercent >= 80 ? "warning" : "ink"}
          progress={quotaPercent}
          progressLabel="Doküman kotası kullanımı"
          qualifier={
            data.periodEnd === null
              ? "Dönem bilgisi yok"
              : `Dönem sonu ${formatDate(data.periodEnd)}`
          }
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
        {/* ── Sol: kanıtlı listeler ──────────────────────────────────────── */}
        <div className="flex min-w-0 flex-col gap-6">
          <section>
            <SectionHeader
              title="Eleme riski taşıyan maddeler"
              description="Karşılanmayan gereksinimler ve yüksek riskli sözleşme maddeleri — her biri kaynağıyla."
            />
            <Card>
              {data.detailLoading ? (
                <CardContent className="flex flex-col gap-4">
                  <Skeleton className="h-12" />
                  <Skeleton className="h-12" />
                  <Skeleton className="h-12" />
                </CardContent>
              ) : data.exposures.length === 0 ? (
                <CardContent className="py-10 text-center">
                  <p className="text-sm font-medium text-ink-1">Açık eleme riski yok</p>
                  <p className="mt-1 text-sm text-ink-2">
                    İncelenen ihalelerde karşılanmayan zorunlu madde bulunmuyor.
                  </p>
                </CardContent>
              ) : (
                <ul className="divide-y divide-border">
                  {data.exposures.slice(0, 6).map((item) => (
                    <li key={item.id}>
                      <Link
                        href={`/tenders/${item.tenderId}/review`}
                        className="block px-5 py-3.5 transition-colors duration-100 hover:bg-surface-2"
                      >
                        <EvidenceRail tone="danger">
                          <p className="line-clamp-2 text-sm leading-5 text-ink-1">{item.text}</p>
                          <div className="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
                            <Badge tone="danger" dot>
                              {item.source === "compliance" ? "Karşılanmıyor" : "Yüksek risk"}
                            </Badge>
                            <SourceRef page={item.page} section={item.section} />
                            <span className="truncate text-xs text-ink-3">
                              {item.tenderTitle}
                            </span>
                          </div>
                        </EvidenceRail>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              {data.exposures.length > 6 && (
                <div className="border-t border-border px-5 py-2.5">
                  <p className="text-xs text-ink-3">
                    {formatNumber(data.exposures.length - 6)} madde daha var — ilgili ihalenin
                    inceleme ekranından görün.
                  </p>
                </div>
              )}
            </Card>
          </section>

          <section>
            <SectionHeader
              title="Son teklif takvimi"
              description="Şartnameden çıkarılan tarihler. Metin ayrıştırılamadıysa dokümandaki hali gösterilir."
            />
            <Card>
              {data.detailLoading ? (
                <CardContent className="flex flex-col gap-4">
                  <Skeleton className="h-12" />
                  <Skeleton className="h-12" />
                </CardContent>
              ) : data.deadlines.length === 0 ? (
                <CardContent className="py-10 text-center">
                  <p className="text-sm font-medium text-ink-1">Takvim maddesi çıkarılmadı</p>
                  <p className="mt-1 text-sm text-ink-2">
                    İncelemeye hazır ihalelerde tarih içeren bir madde bulunamadı.
                  </p>
                </CardContent>
              ) : (
                <ul className="divide-y divide-border">
                  {data.deadlines.slice(0, 6).map((item) => (
                    <li key={item.id}>
                      <Link
                        href={`/tenders/${item.tenderId}/review`}
                        className="flex items-start gap-4 px-5 py-3.5 transition-colors duration-100 hover:bg-surface-2"
                      >
                        <DateBlock date={item.date} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-ink-1">{item.label}</p>
                          <p className="mt-0.5 truncate text-sm text-ink-2">{item.valueText}</p>
                          <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1">
                            <SourceRef page={item.page} section={item.section} />
                            <span className="truncate text-xs text-ink-3">{item.tenderTitle}</span>
                          </div>
                        </div>
                        {item.date !== null && <DeadlineBadge date={item.date} />}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </section>
        </div>

        {/* ── Sağ: hesap ve süreç durumu ─────────────────────────────────── */}
        <div className="flex min-w-0 flex-col gap-6">
          <Card>
            <CardHeader className="block">
              <CardTitle>Bu dönemki kullanım</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-5 pt-0">
              {data.quota.map((quota, index) => (
                <Meter
                  key={quota.label}
                  label={quota.label}
                  used={quota.used}
                  limit={quota.limit}
                  formatValue={formatNumber}
                  showThresholdNote={index === 0}
                />
              ))}
              <Button asChild variant="secondary" size="sm" className="w-full">
                <Link href="/usage">Planı yönet</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="block">
              <CardTitle>Devam eden analizler</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {data.inProgress.length === 0 ? (
                <p className="py-2 text-sm text-ink-2">Şu anda işlenen doküman yok.</p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {data.inProgress.map((tender) => (
                    <li key={tender.id}>
                      <Link
                        href={`/tenders/${tender.id}`}
                        title={tender.title}
                        className="flex items-start gap-2.5 text-sm text-ink-1 hover:underline"
                      >
                        <span
                          aria-hidden
                          className="animate-live mt-1.5 size-1.5 shrink-0 rounded-full bg-info"
                        />
                        {/* Dar sütunda tek satır kırpma bilgi kaybettiriyordu. */}
                        <span className="line-clamp-2 min-w-0">{tender.title}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

/** Tarih bloğu — §8.20. Ayrıştırılamayan tarihte soru işareti değil, tire. */
function DateBlock({ date }: { date: Date | null }) {
  if (date === null) {
    return (
      <span className="grid size-11 shrink-0 place-items-center rounded-md bg-surface-2 text-ink-3">
        <CalendarClock aria-hidden className="size-4" strokeWidth={1.5} />
      </span>
    );
  }
  return (
    <span className="grid size-11 shrink-0 place-items-center rounded-md bg-surface-2 leading-none">
      <span className="font-display text-base font-semibold text-ink-1">{date.getDate()}</span>
      <span className="mt-0.5 text-[11px] text-ink-3">
        {new Intl.DateTimeFormat("tr-TR", { month: "short" }).format(date)}
      </span>
    </span>
  );
}

/** Kalan süre rozeti — renk yöne değil ANLAMA bağlı (§8.21): yaklaşan = kötü. */
function DeadlineBadge({ date }: { date: Date }) {
  const days = Math.round((date.getTime() - Date.now()) / 86_400_000);
  const tone = days < 0 ? "neutral" : days <= 3 ? "danger" : days <= 10 ? "warning" : "neutral";
  return (
    <Badge tone={tone} className={cn("shrink-0", tone === "danger" && "gap-1")}>
      {tone === "danger" && <TriangleAlert aria-hidden strokeWidth={2} />}
      {formatDeadline(date)}
    </Badge>
  );
}
