"use client";

import { FileStack, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";

import { FilterEmptyState, EmptyState, ErrorState, TableSkeleton } from "@/components/states";
import { StatusPill } from "@/components/status-pill";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatNumber } from "@/lib/format";
import { tenderStatusMeta } from "@/lib/tenders";
import { cn } from "@/lib/utils";

export type TenderRow = {
  id: string;
  title: string;
  status: string;
};

const SEGMENTS = [
  { value: "all", label: "Tümü" },
  { value: "review_ready", label: "İncelemeye hazır" },
  { value: "analyzing", label: "Analiz ediliyor" },
  { value: "draft", label: "Taslak" },
  { value: "archived", label: "Arşiv" },
] as const;

/**
 * İhale listesi — DESIGN.md §9.3 liste/tablo şablonu.
 *
 * Sunum bileşeni: veri çekmez, yalnız gösterir. `/design/preview/tenders`
 * bunu mock veriyle beş durumda render eder (§14 doğrulama döngüsü backend'e
 * bağımlı kalmasın diye).
 */
export function TenderListView({
  tenders,
  state,
  errorMessage,
  onRetry,
  newTenderAction,
}: {
  tenders: TenderRow[];
  state: "ready" | "loading" | "error";
  errorMessage?: string;
  onRetry?: () => void;
  /** Birincil eylem — sayfada tek primary buton (§8.5). */
  newTenderAction: ReactNode;
}) {
  const [segment, setSegment] = useState<string>("all");
  const [query, setQuery] = useState("");

  const counts = useMemo(() => {
    const base: Record<string, number> = { all: tenders.length };
    for (const tender of tenders) {
      base[tender.status] = (base[tender.status] ?? 0) + 1;
    }
    return base;
  }, [tenders]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("tr-TR");
    return tenders.filter((tender) => {
      if (segment !== "all" && tender.status !== segment) return false;
      if (needle === "") return true;
      return tender.title.toLocaleLowerCase("tr-TR").includes(needle);
    });
  }, [tenders, segment, query]);

  const dirty = segment !== "all" || query.trim() !== "";

  if (state === "loading") return <TableSkeleton rows={5} columns={3} />;

  if (state === "error") {
    return (
      <ErrorState
        title="İhaleler yüklenemedi"
        description={errorMessage ?? "Sunucuya ulaşılamıyor. Bağlantınızı kontrol edip yeniden deneyin."}
        onRetry={onRetry}
      />
    );
  }

  // §10.1 — hiç kayıt yokken filtre çubuğu bile gösterilmez; boş durum bir
  // davettir, boş bir tablo iskeleti değil.
  if (tenders.length === 0) {
    return (
      <EmptyState
        icon={FileStack}
        title="Henüz ihale projesi yok"
        description="Bir proje açıp şartnameyi yükleyin; gereksinim, belge, risk ve takvim analizi kendiliğinden başlar."
        action={newTenderAction}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={segment} onValueChange={setSegment} className="gap-0">
          <TabsList variant="segment">
            {SEGMENTS.map((item) => (
              <TabsTrigger key={item.value} value={item.value}>
                {item.label}
                <span
                  className={cn(
                    "font-mono text-[11px]",
                    segment === item.value ? "text-ink-2" : "text-ink-3",
                  )}
                >
                  {formatNumber(counts[item.value] ?? 0)}
                </span>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <div className="relative w-full sm:w-72">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-3"
            strokeWidth={1.75}
          />
          <Input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="İhale başlığında ara"
            aria-label="İhale başlığında ara"
            className="pl-8"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <FilterEmptyState
          query={query.trim() === "" ? undefined : query.trim()}
          onReset={() => {
            setSegment("all");
            setQuery("");
          }}
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          {/* §7.4 — tablo mobilde yatay kaydırmaya bırakılmaz, kart listesine
              döner. 375px'de üç sütun sıkışınca başlıklar "20…" diye kırpılıyordu. */}
          <ul className="divide-y divide-border md:hidden">
            {filtered.map((tender) => {
              const meta = tenderStatusMeta(tender.status);
              const ready = tender.status === "review_ready";
              return (
                <li key={tender.id}>
                  <Link
                    href={ready ? `/tenders/${tender.id}/review` : `/tenders/${tender.id}`}
                    className="flex flex-col gap-2.5 px-4 py-3.5 transition-colors duration-100 active:bg-surface-2"
                  >
                    <span className="text-sm font-medium text-ink-1">{tender.title}</span>
                    <span className="flex flex-wrap items-center gap-2">
                      <StatusPill tone={meta.tone} label={meta.label} />
                      <span className="text-xs text-ink-3">
                        {ready ? "Bulguları incele →" : "Aç →"}
                      </span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>

          <div className="hidden md:block">
          <Table>
            <TableHeader>
              <TableRow className="border-b-0 hover:bg-transparent">
                <TableHead>İHALE</TableHead>
                <TableHead className="w-48">DURUM</TableHead>
                <TableHead className="w-40 text-right">İŞLEM</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((tender) => {
                const meta = tenderStatusMeta(tender.status);
                const ready = tender.status === "review_ready";
                return (
                  <TableRow key={tender.id} interactive className="group">
                    <TableCell className="max-w-0">
                      <Link
                        href={`/tenders/${tender.id}`}
                        className="block min-w-0 focus-visible:outline-none"
                      >
                        {/* UUID parçası gösterilmez: kullanıcıya hiçbir şey
                            söylemez ve ihale kayıt numarası zaten başlıkta. */}
                        <span className="block truncate font-medium text-ink-1">
                          {tender.title}
                        </span>
                        <span className="mt-0.5 block truncate text-xs text-ink-3">
                          {meta.hint}
                        </span>
                      </Link>
                    </TableCell>
                    <TableCell>
                      <StatusPill tone={meta.tone} label={meta.label} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        asChild
                        variant={ready ? "secondary" : "ghost"}
                        size="sm"
                        className={cn(!ready && "text-ink-3")}
                      >
                        <Link href={ready ? `/tenders/${tender.id}/review` : `/tenders/${tender.id}`}>
                          {ready ? "Bulguları incele" : "Aç"}
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          </div>
          <div className="flex items-center justify-between border-t border-border px-3 py-2.5">
            <p className="text-xs text-ink-3">
              {formatNumber(tenders.length)} kayıttan {formatNumber(filtered.length)} tanesi
              gösteriliyor
            </p>
            {dirty && (
              <Button
                variant="ghost"
                size="xs"
                className="text-ink-3"
                onClick={() => {
                  setSegment("all");
                  setQuery("");
                }}
              >
                Filtreleri temizle
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
