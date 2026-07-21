"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Check,
  FileQuestion,
  FileText,
  History,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Undo2,
  X,
} from "lucide-react";
import dynamic from "next/dynamic";
import { use, useMemo, useState, type CSSProperties, type ReactNode } from "react";

import { EditFindingDialog, type EditTarget } from "@/components/review/edit-finding-dialog";
import { ExportDialog } from "@/components/review/export-dialog";
import {
  FindingCommentsDialog,
  type CommentsTarget,
} from "@/components/review/finding-comments-dialog";
import {
  FindingHistoryDialog,
  type HistoryTarget,
} from "@/components/review/finding-history-dialog";
import type { HighlightBox } from "@/components/review/pdf-viewer";
import { useFindingReview } from "@/components/review/use-finding-review";
import { StatusPill } from "@/components/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import {
  CATEGORY_LABELS,
  CATEGORY_TO_KIND,
  COMPLIANCE_STATUS,
  DELIVERABLE_KIND_LABELS,
  REQUIREMENT_KIND_LABELS,
  REVIEW_STATUS,
  RISK_CATEGORY_LABELS,
  RISK_SEVERITY,
  TIMELINE_KIND_LABELS,
  sourceBbox,
  sourceRef,
  type AnyFinding,
  type ComplianceFinding,
  type DeliverableFinding,
  type FindingCategory,
  type FindingSource,
  type RequirementFinding,
  type ReviewStatus,
  type RiskFinding,
  type TimelineFinding,
} from "@/lib/findings";
import { cn } from "@/lib/utils";

// PDF.js yalnız tarayıcıda yüklenir (worker + canvas); SSR grafiğine girmez.
const PdfViewer = dynamic(
  () => import("@/components/review/pdf-viewer").then((m) => m.PdfViewer),
  { ssr: false, loading: () => <Skeleton className="h-full w-full" /> },
);

/** Sol listedeki seçim; sağ paneli (doküman + sayfa + vurgu) sürer. */
type Selection = {
  findingId: string;
  documentId: string;
  page: number;
  bbox: HighlightBox | null;
  quote: string;
  section: string | null;
  nonce: number;
};

/** Satır aksiyonları (onay/red/düzelt/geri al/yorum/geçmiş) — sayfa kablolar. */
type RowActions = {
  onApprove: () => void;
  onReject: () => void;
  onReset: () => void;
  onEdit: () => void;
  onComments: () => void;
  onHistory: () => void;
};

function useTenderFindings(tenderId: string) {
  const path = { params: { path: { tender_id: tenderId } } };
  const requirements = useQuery({
    queryKey: ["requirements", tenderId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/tenders/{tender_id}/requirements", path);
      if (error !== undefined) throw new Error("Gereksinimler yüklenemedi.");
      return data;
    },
  });
  const deliverables = useQuery({
    queryKey: ["deliverables", tenderId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/tenders/{tender_id}/deliverables", path);
      if (error !== undefined) throw new Error("Belgeler yüklenemedi.");
      return data;
    },
  });
  const risks = useQuery({
    queryKey: ["risks", tenderId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/tenders/{tender_id}/risks", path);
      if (error !== undefined) throw new Error("Riskler yüklenemedi.");
      return data;
    },
  });
  const timeline = useQuery({
    queryKey: ["timeline", tenderId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/tenders/{tender_id}/timeline", path);
      if (error !== undefined) throw new Error("Takvim yüklenemedi.");
      return data;
    },
  });
  const compliance = useQuery({
    queryKey: ["compliance", tenderId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/tenders/{tender_id}/compliance", path);
      if (error !== undefined) throw new Error("Uygunluk sonuçları yüklenemedi.");
      return data;
    },
  });
  return { requirements, deliverables, risks, timeline, compliance };
}

/** Tek bulgu satırı: seçim kutusu + metin/meta + inceleme aksiyonları (§4.3). */
function FindingRow({
  title,
  source,
  pills,
  selected,
  railColor,
  onClick,
  review,
  checked,
  onCheckedChange,
  actions,
}: {
  title: string;
  source: FindingSource;
  pills: ReactNode;
  selected: boolean;
  /** İmza öğesi yankısı: risk/uygunluk satırlarında semantik sol ray (§9). */
  railColor?: string;
  onClick: () => void;
  review: { status: ReviewStatus };
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  actions: RowActions;
}) {
  const reviewMeta = REVIEW_STATUS[review.status];
  const isApprovedish = review.status === "approved" || review.status === "edited";
  return (
    <div
      style={railColor !== undefined ? ({ "--rail-color": railColor } as CSSProperties) : undefined}
      className={cn(
        "group w-full rounded-lg border bg-surface transition-colors",
        railColor !== undefined && "rail-active",
        review.status === "rejected" && "opacity-60",
        selected
          ? "border-brand ring-2 ring-brand/20"
          : "hover:border-border-strong hover:bg-surface-2/50",
      )}
    >
      <div className="flex items-start gap-2.5 px-3.5 py-3">
        <Checkbox
          className="mt-0.5"
          checked={checked}
          onCheckedChange={(value) => onCheckedChange(value === true)}
          aria-label="Bulguyu seç"
        />
        <button type="button" onClick={onClick} className="min-w-0 flex-1 text-left">
          <p
            className={cn(
              "text-[13.5px] leading-5 text-ink-1",
              review.status === "rejected" && "line-through decoration-ink-3",
            )}
          >
            {title}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[11px] text-ink-3">{sourceRef(source)}</span>
            {pills}
            {reviewMeta !== undefined && (
              <StatusPill tone={reviewMeta.tone} label={reviewMeta.label} />
            )}
          </div>
        </button>
        <div
          className={cn(
            "flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity",
            "group-focus-within:opacity-100 group-hover:opacity-100",
            selected && "opacity-100",
          )}
        >
          {!isApprovedish && (
            <Button
              size="icon-xs"
              variant="ghost"
              className="text-success hover:bg-success-weak hover:text-success"
              title="Onayla"
              onClick={actions.onApprove}
            >
              <Check />
            </Button>
          )}
          {review.status !== "rejected" && (
            <Button
              size="icon-xs"
              variant="ghost"
              className="text-danger hover:bg-danger-weak hover:text-danger"
              title="Reddet"
              onClick={actions.onReject}
            >
              <X />
            </Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="icon-xs" variant="ghost" title="Diğer işlemler">
                <MoreHorizontal />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuItem onClick={actions.onEdit}>
                <Pencil /> Düzelt
              </DropdownMenuItem>
              {review.status !== "pending" && (
                <DropdownMenuItem onClick={actions.onReset}>
                  <Undo2 /> İncelemeyi geri al
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={actions.onComments}>
                <MessageSquare /> Yorumlar
              </DropdownMenuItem>
              <DropdownMenuItem onClick={actions.onHistory}>
                <History /> Geçmiş
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}

function EmptyList({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-10">
      <FileQuestion className="size-5 text-ink-3" strokeWidth={1.5} />
      <p className="text-sm text-ink-2">{message}</p>
    </div>
  );
}

export default function TenderReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: tenderId } = use(params);
  const [category, setCategory] = useState<FindingCategory>("requirements");
  const [mandatoryOnly, setMandatoryOnly] = useState(false);
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [reviewFilter, setReviewFilter] = useState<string>("all");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [viewerDocId, setViewerDocId] = useState<string | null>(null);
  const [viewerPage, setViewerPage] = useState(1);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [editTarget, setEditTarget] = useState<EditTarget | null>(null);
  const [commentsTarget, setCommentsTarget] = useState<CommentsTarget | null>(null);
  const [historyTarget, setHistoryTarget] = useState<HistoryTarget | null>(null);

  const { act, edit, bulk } = useFindingReview(tenderId);

  const tender = useQuery({
    queryKey: ["tender", tenderId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/tenders/{tender_id}", {
        params: { path: { tender_id: tenderId } },
      });
      if (error !== undefined) throw new Error("İhale yüklenemedi.");
      return data;
    },
  });

  const documents = useQuery({
    queryKey: ["documents", tenderId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/tenders/{tender_id}/documents", {
        params: { path: { tender_id: tenderId } },
      });
      if (error !== undefined) throw new Error("Dokümanlar yüklenemedi.");
      return data;
    },
  });

  const { requirements, deliverables, risks, timeline, compliance } = useTenderFindings(tenderId);

  const documentById = useMemo(
    () => new Map(documents.data?.map((d) => [d.id, d]) ?? []),
    [documents.data],
  );
  const pdfDocuments = useMemo(
    () =>
      documents.data?.filter(
        (d) => d.content_type === "application/pdf" && d.status === "uploaded",
      ) ?? [],
    [documents.data],
  );

  // Görüntülenen doküman: seçim > kullanıcı seçimi > ilk PDF.
  const activeDocId = viewerDocId ?? pdfDocuments[0]?.id ?? null;
  const activeDoc = activeDocId !== null ? documentById.get(activeDocId) : undefined;
  const activeDocIsPdf = activeDoc?.content_type === "application/pdf";

  const documentFile = useQuery({
    queryKey: ["document-file", activeDocId],
    enabled: activeDocId !== null && activeDocIsPdf === true,
    staleTime: 30 * 60 * 1000, // imzalı URL 1 saat geçerli
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/documents/{document_id}/file", {
        params: { path: { document_id: activeDocId ?? "" } },
      });
      if (error !== undefined) throw new Error("Önizleme bağlantısı alınamadı.");
      return data;
    },
  });

  function selectFinding(finding: {
    id: string;
    document_id: string;
    source: FindingSource;
  }) {
    const bbox = sourceBbox(finding.source);
    setSelection((previous) => ({
      findingId: finding.id,
      documentId: finding.document_id,
      page: finding.source.page,
      bbox,
      quote: finding.source.quote,
      section: finding.source.section ?? null,
      nonce: (previous?.nonce ?? 0) + 1,
    }));
    const doc = documentById.get(finding.document_id);
    if (doc?.content_type === "application/pdf") {
      setViewerDocId(finding.document_id);
      setViewerPage(finding.source.page);
    }
  }

  function switchCategory(next: string) {
    setCategory(next as FindingCategory);
    setKindFilter("all");
    setChecked(new Set());
  }

  const counts: Record<FindingCategory, number | undefined> = {
    requirements: requirements.data?.length,
    deliverables: deliverables.data?.length,
    risks: risks.data?.length,
    timeline: timeline.data?.length,
    compliance: compliance.data?.length,
  };

  // Seçili bulgu vurgusu yalnız kendi dokümanı + sayfası ekrandayken çizilir.
  const highlight =
    selection !== null && selection.documentId === activeDocId && selection.page === viewerPage
      ? selection.bbox
      : null;
  const highlightKey =
    highlight !== null && selection !== null ? `${selection.findingId}:${selection.nonce}` : null;

  const selectedDocIsPdf =
    selection !== null &&
    documentById.get(selection.documentId)?.content_type === "application/pdf";

  const kindOptions: { value: string; label: string }[] = (() => {
    switch (category) {
      case "requirements":
        return Object.entries(REQUIREMENT_KIND_LABELS).map(([value, label]) => ({ value, label }));
      case "deliverables":
        return Object.entries(DELIVERABLE_KIND_LABELS).map(([value, label]) => ({ value, label }));
      case "risks":
        return Object.entries(RISK_SEVERITY).map(([value, meta]) => ({
          value,
          label: meta.label,
        }));
      case "timeline":
        return Object.entries(TIMELINE_KIND_LABELS).map(([value, label]) => ({ value, label }));
      case "compliance":
        return Object.entries(COMPLIANCE_STATUS).map(([value, meta]) => ({
          value,
          label: meta.label,
        }));
    }
  })();

  const showMandatoryFilter = category === "requirements" || category === "deliverables";

  const matchesReview = (finding: AnyFinding) =>
    reviewFilter === "all" || finding.review.status === reviewFilter;

  // Aktif sekmenin filtre-sonrası satırları: liste render'ı + toplu seçim kaynağı.
  const filteredRows: AnyFinding[] = useMemo(() => {
    switch (category) {
      case "requirements":
        return (requirements.data ?? []).filter(
          (r) =>
            (!mandatoryOnly || r.is_mandatory) &&
            (kindFilter === "all" || r.kind === kindFilter) &&
            matchesReview(r),
        );
      case "deliverables":
        return (deliverables.data ?? []).filter(
          (d) =>
            (!mandatoryOnly || d.is_mandatory) &&
            (kindFilter === "all" || d.kind === kindFilter) &&
            matchesReview(d),
        );
      case "risks":
        return (risks.data ?? []).filter(
          (r) => (kindFilter === "all" || r.severity === kindFilter) && matchesReview(r),
        );
      case "timeline":
        return (timeline.data ?? []).filter(
          (t) => (kindFilter === "all" || t.kind === kindFilter) && matchesReview(t),
        );
      case "compliance":
        return (compliance.data ?? []).filter(
          (c) => (kindFilter === "all" || c.status === kindFilter) && matchesReview(c),
        );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    category,
    requirements.data,
    deliverables.data,
    risks.data,
    timeline.data,
    compliance.data,
    mandatoryOnly,
    kindFilter,
    reviewFilter,
  ]);

  const allVisibleChecked =
    filteredRows.length > 0 && filteredRows.every((row) => checked.has(row.id));

  function toggleChecked(id: string, value: boolean) {
    setChecked((previous) => {
      const next = new Set(previous);
      if (value) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function toggleAllVisible(value: boolean) {
    setChecked(value ? new Set(filteredRows.map((row) => row.id)) : new Set());
  }

  function bulkAct(action: "approve" | "reject") {
    bulk.mutate(
      { category, ids: [...checked], action },
      { onSettled: () => setChecked(new Set()) },
    );
  }

  /** Satır aksiyonlarını kategoriyle kablolar (EditTarget eşleşmesi çağrı yerinde garanti). */
  function rowActions(finding: AnyFinding, title: string): RowActions {
    const kind = CATEGORY_TO_KIND[category];
    return {
      onApprove: () => act.mutate({ category, id: finding.id, action: "approve" }),
      onReject: () => act.mutate({ category, id: finding.id, action: "reject" }),
      onReset: () => act.mutate({ category, id: finding.id, action: "reset" }),
      onEdit: () => setEditTarget({ category, finding } as EditTarget),
      onComments: () => setCommentsTarget({ kind, findingId: finding.id, title }),
      onHistory: () => setHistoryTarget({ kind, findingId: finding.id, title }),
    };
  }

  function rowProps(finding: AnyFinding, title: string) {
    return {
      title,
      source: finding.source,
      selected: selection?.findingId === finding.id,
      onClick: () => selectFinding(finding),
      // Sigorta: API bayat kod servis ederse (ör. reload tetiklenmedi) review
      // alanı gelmez — sayfa çökmesin, bulgu "onay bekliyor" görünsün.
      review: finding.review ?? { status: "pending" as const, reviewed_by: null, reviewed_at: null },
      checked: checked.has(finding.id),
      onCheckedChange: (value: boolean) => toggleChecked(finding.id, value),
      actions: rowActions(finding, title),
    };
  }

  function renderList(): ReactNode {
    const active = {
      requirements,
      deliverables,
      risks,
      timeline,
      compliance,
    }[category];
    if (active.isPending) return <ListSkeleton />;
    if (active.isError) return <p className="text-sm text-danger">{active.error.message}</p>;

    switch (category) {
      case "requirements": {
        const rows = filteredRows as RequirementFinding[];
        if (rows.length === 0) return <EmptyList message="Bu filtreyle gereksinim yok." />;
        return rows.map((row) => (
          <FindingRow
            key={row.id}
            {...rowProps(row, row.text)}
            pills={
              <>
                <Badge variant="secondary" className="text-[11px]">
                  {REQUIREMENT_KIND_LABELS[row.kind] ?? row.kind}
                </Badge>
                {row.is_mandatory && <StatusPill tone="warning" label="Zorunlu" />}
              </>
            }
          />
        ));
      }
      case "deliverables": {
        const rows = filteredRows as DeliverableFinding[];
        if (rows.length === 0) return <EmptyList message="Bu filtreyle istenen belge yok." />;
        return rows.map((row) => (
          <FindingRow
            key={row.id}
            {...rowProps(row, row.name)}
            pills={
              <>
                <Badge variant="secondary" className="text-[11px]">
                  {DELIVERABLE_KIND_LABELS[row.kind] ?? row.kind}
                </Badge>
                {row.is_mandatory && <StatusPill tone="warning" label="Zorunlu" />}
              </>
            }
          />
        ));
      }
      case "risks": {
        const rows = filteredRows as RiskFinding[];
        if (rows.length === 0) return <EmptyList message="Bu filtreyle risk maddesi yok." />;
        return rows.map((row) => {
          const severity = RISK_SEVERITY[row.severity];
          return (
            <FindingRow
              key={row.id}
              {...rowProps(row, row.text)}
              railColor={
                row.severity === "high"
                  ? "var(--danger)"
                  : row.severity === "medium"
                    ? "var(--warning)"
                    : "var(--border-strong)"
              }
              pills={
                <>
                  {severity !== undefined && (
                    <StatusPill tone={severity.tone} label={severity.label} />
                  )}
                  <Badge variant="secondary" className="text-[11px]">
                    {RISK_CATEGORY_LABELS[row.category] ?? row.category}
                  </Badge>
                </>
              }
            />
          );
        });
      }
      case "timeline": {
        const rows = filteredRows as TimelineFinding[];
        if (rows.length === 0) return <EmptyList message="Bu filtreyle takvim öğesi yok." />;
        return rows.map((row) => (
          <FindingRow
            key={row.id}
            {...rowProps(row, `${row.label}: ${row.value_text}`)}
            pills={
              <Badge variant="secondary" className="text-[11px]">
                {TIMELINE_KIND_LABELS[row.kind] ?? row.kind}
              </Badge>
            }
          />
        ));
      }
      case "compliance": {
        const rows = filteredRows as ComplianceFinding[];
        if (rows.length === 0)
          return (
            <EmptyList message="Uygunluk sonucu yok. Yetkinlik profili tanımlı olmalıdır." />
          );
        return rows.map((row) => {
          const status = COMPLIANCE_STATUS[row.status];
          return (
            <FindingRow
              key={row.id}
              {...rowProps(row, row.requirement_text)}
              railColor={
                row.status === "unmet"
                  ? "var(--danger)"
                  : row.status === "partial"
                    ? "var(--warning)"
                    : "var(--success)"
              }
              pills={status !== undefined && <StatusPill tone={status.tone} label={status.label} />}
            />
          );
        });
      }
    }
  }

  return (
    <div className="flex h-[calc(100vh-7.5rem)] min-h-[520px] flex-col">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h1 className="truncate text-[22px] font-semibold leading-7 tracking-tight text-ink-1">
            {tender.data?.title ?? "İhale"}
          </h1>
          <p className="mt-0.5 text-sm text-ink-2">
            Bulguları inceleyin: onaylayın, düzeltin veya reddedin — sonra raporu indirin.
          </p>
        </div>
        <ExportDialog tenderId={tenderId} />
      </div>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-12">
        {/* Sol: bulgu listesi */}
        <section className="flex min-h-0 flex-col rounded-xl border bg-surface lg:col-span-5 xl:col-span-4">
          <div className="border-b p-3">
            <Tabs value={category} onValueChange={switchCategory}>
              <TabsList className="w-full">
                {(Object.keys(CATEGORY_LABELS) as FindingCategory[]).map((key) => (
                  <TabsTrigger key={key} value={key} className="flex-1 gap-1.5 px-1 text-xs">
                    {CATEGORY_LABELS[key]}
                    <span className="font-mono text-[10px] text-ink-3">{counts[key] ?? "…"}</span>
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Select value={kindFilter} onValueChange={setKindFilter}>
                <SelectTrigger size="sm" className="w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tümü</SelectItem>
                  {kindOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={reviewFilter} onValueChange={setReviewFilter}>
                <SelectTrigger size="sm" className="w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">İnceleme: tümü</SelectItem>
                  {Object.entries(REVIEW_STATUS).map(([value, meta]) => (
                    <SelectItem key={value} value={value}>
                      {meta.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {showMandatoryFilter && (
                <Label className="flex items-center gap-2 text-[13px] font-normal text-ink-2">
                  <Checkbox
                    checked={mandatoryOnly}
                    onCheckedChange={(value) => setMandatoryOnly(value === true)}
                  />
                  Yalnız zorunlu
                </Label>
              )}
              <Label className="flex items-center gap-2 text-[13px] font-normal text-ink-2">
                <Checkbox
                  checked={allVisibleChecked}
                  onCheckedChange={(value) => toggleAllVisible(value === true)}
                  disabled={filteredRows.length === 0}
                />
                Tümünü seç
              </Label>
            </div>
            {checked.size > 0 && (
              <div className="mt-3 flex items-center justify-between rounded-lg border border-brand/40 bg-brand-weak/40 px-3 py-2">
                <span className="text-[13px] font-medium text-ink-1">
                  {checked.size} bulgu seçili
                </span>
                <div className="flex items-center gap-1.5">
                  <Button size="xs" onClick={() => bulkAct("approve")} disabled={bulk.isPending}>
                    <Check /> Onayla
                  </Button>
                  <Button
                    size="xs"
                    variant="outline"
                    className="text-danger hover:text-danger"
                    onClick={() => bulkAct("reject")}
                    disabled={bulk.isPending}
                  >
                    <X /> Reddet
                  </Button>
                  <Button size="xs" variant="ghost" onClick={() => setChecked(new Set())}>
                    Vazgeç
                  </Button>
                </div>
              </div>
            )}
          </div>
          <ScrollArea className="min-h-0 flex-1">
            <div className="flex flex-col gap-2 p-3">{renderList()}</div>
          </ScrollArea>
        </section>

        {/* Sağ: doküman önizleme + kaynak vurgusu */}
        <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border bg-surface lg:col-span-7 xl:col-span-8">
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <FileText className="size-4 shrink-0 text-ink-3" strokeWidth={1.5} />
            {pdfDocuments.length > 0 ? (
              <Select
                value={activeDocId ?? undefined}
                onValueChange={(id) => {
                  setViewerDocId(id);
                  setViewerPage(1);
                }}
              >
                <SelectTrigger size="sm" className="max-w-96 border-0 shadow-none">
                  <SelectValue placeholder="Doküman seçin" />
                </SelectTrigger>
                <SelectContent>
                  {pdfDocuments.map((doc) => (
                    <SelectItem key={doc.id} value={doc.id}>
                      {doc.filename}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <span className="text-sm text-ink-3">Önizlenebilir PDF yok</span>
            )}
          </div>

          {selection !== null && !selectedDocIsPdf && (
            <div
              className="rail-active m-3 rounded-lg border bg-surface-2/60 p-4"
              style={{ "--rail-color": "var(--info)" } as CSSProperties}
            >
              <p className="text-xs font-medium text-ink-2">
                Bu doküman türünde sayfa önizlemesi yok (DOCX/XLSX) — kaynak alıntı:
              </p>
              <blockquote className="mt-2 border-l-2 pl-3 text-sm italic text-ink-1">
                “{selection.quote}”
              </blockquote>
              <p className="mt-2 font-mono text-[11px] text-ink-3">
                {selection.section !== null
                  ? `s. ${selection.page} · ${selection.section}`
                  : `s. ${selection.page}`}
              </p>
            </div>
          )}

          {activeDocIsPdf === true && documentFile.data !== undefined ? (
            <PdfViewer
              fileUrl={documentFile.data.url}
              page={viewerPage}
              onPageChange={setViewerPage}
              highlight={highlight}
              highlightKey={highlightKey}
            />
          ) : activeDocIsPdf === true && documentFile.isPending ? (
            <div className="flex-1 p-4">
              <Skeleton className="h-full w-full" />
            </div>
          ) : activeDocIsPdf === true && documentFile.isError ? (
            <p className="p-6 text-sm text-danger">{documentFile.error.message}</p>
          ) : (
            selection === null && (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6">
                <FileText className="size-6 text-ink-3" strokeWidth={1.5} />
                <p className="text-sm text-ink-2">
                  Soldan bir bulgu seçin; kaynağı burada vurgulanır.
                </p>
              </div>
            )
          )}
        </section>
      </div>

      <EditFindingDialog
        target={editTarget}
        onClose={() => setEditTarget(null)}
        onSubmit={(variables) => edit.mutate(variables)}
      />
      <FindingCommentsDialog target={commentsTarget} onClose={() => setCommentsTarget(null)} />
      <FindingHistoryDialog target={historyTarget} onClose={() => setHistoryTarget(null)} />
    </div>
  );
}
