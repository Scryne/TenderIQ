"use client";

import { Check, History, MessageSquare, MoreHorizontal, Pencil, Undo2, X } from "lucide-react";
import type { ReactNode } from "react";

import { EvidenceRail, SourceRef } from "@/components/evidence";
import { StatusPill } from "@/components/status-pill";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { REVIEW_STATUS, type ReviewStatus } from "@/lib/findings";
import { cn } from "@/lib/utils";

export type RowActions = {
  onApprove: () => void;
  onReject: () => void;
  onReset: () => void;
  onEdit: () => void;
  onComments: () => void;
  onHistory: () => void;
};

export type RailTone = "ink" | "danger" | "warning" | "success" | "info";

/* ═══════════════════════════════════════════════════════════════════════════
 * BULGU SATIRI — çekirdek ekranın atom birimi.
 *
 * ANATOMİ (üstten alta, hiyerarşi sırası):
 *   ☐  seçim kutusu
 *   ▌  kanıt şeridi — semantik tonda (yüksek risk kırmızı, karşılanan yeşil)
 *      bulgu metni ....................... 13,5px, okunabilir uzunluk
 *      s.42 · 4.3.1  [Zorunlu] [Onaylandı] . kaynak ÖNCE, sonra sınıflandırma
 *   ⋯  satır aksiyonları (hover/focus'ta belirir, seçiliyken sabit)
 *
 * Kaynak referansı meta satırının BAŞINDA durur, sonunda değil: kırmızı çizgi
 * "bulgu kaynağından koparılmaz" der; okuma sırası bunu yansıtmalı.
 * ═══════════════════════════════════════════════════════════════════════════ */
export function FindingRow({
  title,
  page,
  section,
  tags,
  selected,
  railTone = "ink",
  onSelect,
  reviewStatus,
  checked,
  onCheckedChange,
  actions,
}: {
  title: string;
  page: number;
  section: string | null;
  /** Sınıflandırma rozetleri (tür, zorunluluk, şiddet). */
  tags: ReactNode;
  selected: boolean;
  railTone?: RailTone;
  onSelect: () => void;
  reviewStatus: ReviewStatus;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  actions: RowActions;
}) {
  const meta = REVIEW_STATUS[reviewStatus];
  const settled = reviewStatus === "approved" || reviewStatus === "edited";
  const rejected = reviewStatus === "rejected";

  return (
    <div
      data-selected={selected ? "" : undefined}
      className={cn(
        "group rounded-lg border bg-surface transition-colors duration-100",
        // Reddedilen bulgu geri plana düşer ama OKUNUR kalır: opaklık + üstü
        // çizili + soluk dekorasyon üst üste binince metin kayboluyordu.
        rejected && "bg-surface-2",
        selected
          ? "border-accent ring-1 ring-accent"
          : "border-border hover:border-border-strong hover:bg-surface-2",
      )}
    >
      <div className="flex items-start gap-2.5 p-3.5">
        <Checkbox
          className="mt-0.5 shrink-0"
          checked={checked}
          onCheckedChange={(value) => onCheckedChange(value === true)}
          aria-label={`Bulguyu seç: ${title}`}
        />

        <button
          type="button"
          onClick={onSelect}
          className="min-w-0 flex-1 text-left focus-visible:outline-none"
        >
          <EvidenceRail tone={railTone}>
            <p
              className={cn(
                "text-[13.5px] leading-5 text-ink-1",
                rejected && "text-ink-2 line-through decoration-border-strong",
              )}
            >
              {title}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1.5">
              <SourceRef page={page} section={section} />
              {tags}
              {meta !== undefined && reviewStatus !== "pending" && (
                <StatusPill tone={meta.tone} label={meta.label} />
              )}
            </div>
          </EvidenceRail>
        </button>

        <div
          className={cn(
            "flex shrink-0 items-center gap-0.5 transition-opacity",
            "opacity-0 group-focus-within:opacity-100 group-hover:opacity-100",
            selected && "opacity-100",
          )}
        >
          {!settled && (
            <Button
              size="icon-xs"
              variant="ghost"
              className="text-ink-3 hover:bg-success-weak hover:text-success"
              aria-label="Bulguyu onayla"
              title="Onayla"
              onClick={actions.onApprove}
            >
              <Check strokeWidth={2.5} />
            </Button>
          )}
          {!rejected && (
            <Button
              size="icon-xs"
              variant="ghost"
              className="text-ink-3 hover:bg-danger-weak hover:text-danger"
              aria-label="Bulguyu reddet"
              title="Reddet"
              onClick={actions.onReject}
            >
              <X strokeWidth={2.5} />
            </Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon-xs"
                variant="ghost"
                className="text-ink-3"
                aria-label="Diğer işlemler"
              >
                <MoreHorizontal strokeWidth={2} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={actions.onEdit}>
                <Pencil strokeWidth={1.75} /> Düzelt
              </DropdownMenuItem>
              {reviewStatus !== "pending" && (
                <DropdownMenuItem onClick={actions.onReset}>
                  <Undo2 strokeWidth={1.75} /> İncelemeyi geri al
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={actions.onComments}>
                <MessageSquare strokeWidth={1.75} /> Yorumlar
              </DropdownMenuItem>
              <DropdownMenuItem onClick={actions.onHistory}>
                <History strokeWidth={1.75} /> Geçmiş
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
}

/**
 * İnceleme ilerlemesi — "N bulgunun M'si karara bağlandı".
 * §8.1 varyant D'nin çubuk mantığı, başlık çubuğuna sıkıştırılmış hali.
 */
export function ReviewProgress({
  decided,
  total,
  className,
}: {
  decided: number;
  total: number;
  className?: string;
}) {
  const percent = total === 0 ? 0 : Math.round((decided / total) * 100);
  const complete = total > 0 && decided === total;

  return (
    <div className={cn("flex min-w-0 items-center gap-2.5", className)}>
      <span
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="İnceleme ilerlemesi"
        className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-2"
      >
        <span
          className={cn(
            "block h-full rounded-full transition-[width] duration-300",
            complete ? "bg-success" : "bg-accent",
          )}
          style={{ width: `${percent}%` }}
        />
      </span>
      <span className="shrink-0 font-mono text-xs text-ink-2">
        {decided}/{total}
      </span>
    </div>
  );
}
