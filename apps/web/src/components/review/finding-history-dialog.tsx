"use client";

/** Bulgu düzenleme geçmişi (Sprint 3.2, §4.3): AuditLog kayıtlarının dökümü. */

import { History } from "lucide-react";

import { useFindingHistory } from "@/components/review/use-finding-review";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  COMPLIANCE_STATUS,
  DELIVERABLE_KIND_LABELS,
  REQUIREMENT_KIND_LABELS,
  RISK_CATEGORY_LABELS,
  RISK_SEVERITY,
  TIMELINE_KIND_LABELS,
  type FindingKind,
} from "@/lib/findings";

export type HistoryTarget = { kind: FindingKind; findingId: string; title: string };

const ACTION_LABELS: Record<string, string> = {
  "finding.approved": "Onaylandı",
  "finding.rejected": "Reddedildi",
  "finding.edited": "Düzeltildi",
  "finding.review_reset": "İnceleme geri alındı",
  "finding.commented": "Yorum eklendi",
};

const FIELD_LABELS: Record<string, string> = {
  text: "Metin",
  name: "Ad",
  kind: "Tür",
  is_mandatory: "Zorunluluk",
  severity: "Önem",
  category: "Kategori",
  label: "Öğe",
  value_text: "Değer",
  status: "Durum",
  rationale: "Gerekçe",
};

/** Enum/bool değerlerini TR etikete çevirir; bilinmeyen değer olduğu gibi kalır. */
function valueLabel(value: unknown): string {
  if (value === true) return "Evet";
  if (value === false) return "Hayır";
  const key = String(value);
  const fromDicts =
    REQUIREMENT_KIND_LABELS[key] ??
    DELIVERABLE_KIND_LABELS[key] ??
    TIMELINE_KIND_LABELS[key] ??
    RISK_CATEGORY_LABELS[key] ??
    RISK_SEVERITY[key]?.label ??
    COMPLIANCE_STATUS[key]?.label;
  return fromDicts ?? key;
}

const TIME_FORMAT = new Intl.DateTimeFormat("tr-TR", {
  dateStyle: "medium",
  timeStyle: "short",
});

type Changes = Record<string, { from: unknown; to: unknown }>;

export function FindingHistoryDialog({
  target,
  onClose,
}: {
  target: HistoryTarget | null;
  onClose: () => void;
}) {
  const history = useFindingHistory(target?.kind ?? "requirement", target?.findingId ?? null);

  return (
    <Dialog open={target !== null} onOpenChange={(open) => open || onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History className="size-4 text-ink-3" strokeWidth={1.5} />
            Düzenleme geçmişi
          </DialogTitle>
          <DialogDescription className="line-clamp-2">{target?.title}</DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-80">
          <div className="flex flex-col gap-2 pr-3">
            {history.isPending && target !== null ? (
              <>
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </>
            ) : history.isError ? (
              <p className="text-sm text-danger">{history.error.message}</p>
            ) : (history.data?.length ?? 0) === 0 ? (
              <p className="rounded-lg border border-dashed p-4 text-sm text-ink-3">
                Henüz inceleme kaydı yok — bulgu çıkarımdan geldiği hâliyle duruyor.
              </p>
            ) : (
              history.data?.map((entry) => {
                const changes = (entry.meta?.changes ?? null) as Changes | null;
                return (
                  <div key={entry.id} className="rounded-lg border px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[13px] font-medium text-ink-1">
                        {ACTION_LABELS[entry.action] ?? entry.action}
                      </span>
                      <span className="font-mono text-[11px] text-ink-3">
                        {TIME_FORMAT.format(new Date(entry.created_at))}
                      </span>
                    </div>
                    {changes !== null && (
                      <ul className="mt-1.5 flex flex-col gap-0.5">
                        {Object.entries(changes).map(([field, change]) => (
                          <li key={field} className="text-xs text-ink-2">
                            <span className="font-medium">
                              {FIELD_LABELS[field] ?? field}:
                            </span>{" "}
                            <span className="text-ink-3 line-through">
                              {valueLabel(change.from)}
                            </span>{" "}
                            → {valueLabel(change.to)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
