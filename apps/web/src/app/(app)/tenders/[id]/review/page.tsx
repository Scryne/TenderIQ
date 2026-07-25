"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, FileQuestion, FileText, X } from "lucide-react";
import dynamic from "next/dynamic";
import { use, useMemo, useState, type ReactNode } from "react";

import { EvidenceQuote } from "@/components/evidence";
import { FilterChip, ToggleChip } from "@/components/filters";
import { EditFindingDialog, type EditTarget } from "@/components/review/edit-finding-dialog";
import { ExportDialog } from "@/components/review/export-dialog";
import { FindingRow, ReviewProgress, type RailTone } from "@/components/review/finding-row";
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
import { FilterEmptyState, FindingListSkeleton, InlineError } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
  type AnyFinding,
  type ComplianceFinding,
  type DeliverableFinding,
  type FindingCategory,
  type FindingSource,
  type RequirementFinding,
  type RiskFinding,
  type TimelineFinding,
} from "@/lib/findings";
import { cn } from "@/lib/utils";

// PDF.js yalnız tarayıcıda yüklenir (worker + canvas); SSR grafiğine girmez.
const PdfViewer = dynamic(() => import("@/components/review/pdf-viewer").then((m) => m.PdfViewer), {
  ssr: false,
  loading: () => <Skeleton className="h-full w-full rounded-none" />,
});

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
      if (error !== undefined) throw new Error("İstenen belgeler yüklenemedi.");
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

const EMPTY_BY_CATEGORY: Record<FindingCategory, string> = {
  requirements: "Bu filtreyle gereksinim yok.",
  deliverables: "Bu filtreyle istenen belge yok.",
  risks: "Bu filtreyle risk maddesi yok.",
  timeline: "Bu filtreyle takvim öğesi yok.",
  compliance: "Bu filtreyle uygunluk sonucu yok.",
};

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

  const findings = useTenderFindings(tenderId);
  const active = findings[category];

  const documentById = useMemo(
    () => new Map(documents.data?.map((d) => [d.id, d]) ?? []),
    [documents.data],
  );
  const pdfDocuments = useMemo(
    () =>
      documents.data?.filter((d) => d.content_type === "application/pdf" && d.status === "uploaded") ??
      [],
    [documents.data],
  );

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

  function selectFinding(finding: { id: string; document_id: string; source: FindingSource }) {
    setSelection((previous) => ({
      findingId: finding.id,
      documentId: finding.document_id,
      page: finding.source.page,
      bbox: sourceBbox(finding.source),
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
    setReviewFilter("all");
    setMandatoryOnly(false);
    setChecked(new Set());
  }

  function resetFilters() {
    setKindFilter("all");
    setReviewFilter("all");
    setMandatoryOnly(false);
  }

  const counts: Record<FindingCategory, number | undefined> = {
    requirements: findings.requirements.data?.length,
    deliverables: findings.deliverables.data?.length,
    risks: findings.risks.data?.length,
    timeline: findings.timeline.data?.length,
    compliance: findings.compliance.data?.length,
  };

  const highlight =
    selection !== null && selection.documentId === activeDocId && selection.page === viewerPage
      ? selection.bbox
      : null;
  const highlightKey =
    highlight !== null && selection !== null ? `${selection.findingId}:${selection.nonce}` : null;
  const selectedDocIsPdf =
    selection !== null && documentById.get(selection.documentId)?.content_type === "application/pdf";

  const kindOptions: { value: string; label: string }[] = useMemo(() => {
    switch (category) {
      case "requirements":
        return Object.entries(REQUIREMENT_KIND_LABELS).map(([value, label]) => ({ value, label }));
      case "deliverables":
        return Object.entries(DELIVERABLE_KIND_LABELS).map(([value, label]) => ({ value, label }));
      case "risks":
        return Object.entries(RISK_SEVERITY).map(([value, meta]) => ({ value, label: meta.label }));
      case "timeline":
        return Object.entries(TIMELINE_KIND_LABELS).map(([value, label]) => ({ value, label }));
      case "compliance":
        return Object.entries(COMPLIANCE_STATUS).map(([value, meta]) => ({
          value,
          label: meta.label,
        }));
    }
  }, [category]);

  const showMandatoryFilter = category === "requirements" || category === "deliverables";
  // `?? []` her render'da yeni dizi üretir ve aşağıdaki useMemo'yu boşuna
  // tetiklerdi; kimlik sabitlenir.
  const allRows: AnyFinding[] = useMemo(
    () => (active.data ?? []) as AnyFinding[],
    [active.data],
  );

  const filteredRows: AnyFinding[] = useMemo(() => {
    const matchesReview = (finding: AnyFinding) =>
      reviewFilter === "all" || finding.review?.status === reviewFilter;
    const matchesKind = (finding: AnyFinding) => {
      if (kindFilter === "all") return true;
      if ("kind" in finding) return finding.kind === kindFilter;
      if ("severity" in finding) return finding.severity === kindFilter;
      if ("status" in finding) return finding.status === kindFilter;
      return true;
    };
    const matchesMandatory = (finding: AnyFinding) =>
      !mandatoryOnly || !("is_mandatory" in finding) || finding.is_mandatory;

    return allRows.filter(
      (row) => matchesReview(row) && matchesKind(row) && matchesMandatory(row),
    );
  }, [allRows, kindFilter, reviewFilter, mandatoryOnly]);

  const decided = allRows.filter(
    (row) => row.review !== undefined && row.review.status !== "pending",
  ).length;

  const allVisibleChecked =
    filteredRows.length > 0 && filteredRows.every((row) => checked.has(row.id));
  const filtersDirty = kindFilter !== "all" || reviewFilter !== "all" || mandatoryOnly;

  function toggleChecked(id: string, value: boolean) {
    setChecked((previous) => {
      const next = new Set(previous);
      if (value) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function bulkAct(action: "approve" | "reject") {
    bulk.mutate({ category, ids: [...checked], action }, { onSettled: () => setChecked(new Set()) });
  }

  function rowFor(finding: AnyFinding, title: string, tags: ReactNode, railTone: RailTone) {
    const kind = CATEGORY_TO_KIND[category];
    return (
      <FindingRow
        key={finding.id}
        title={title}
        page={finding.source.page}
        section={finding.source.section ?? null}
        tags={tags}
        railTone={railTone}
        selected={selection?.findingId === finding.id}
        onSelect={() => selectFinding(finding)}
        // Sigorta: API bayat kod servis ederse review alanı gelmez — sayfa
        // çökmesin, bulgu "onay bekliyor" görünsün.
        reviewStatus={finding.review?.status ?? "pending"}
        checked={checked.has(finding.id)}
        onCheckedChange={(value) => toggleChecked(finding.id, value)}
        actions={{
          onApprove: () => act.mutate({ category, id: finding.id, action: "approve" }),
          onReject: () => act.mutate({ category, id: finding.id, action: "reject" }),
          onReset: () => act.mutate({ category, id: finding.id, action: "reset" }),
          onEdit: () => setEditTarget({ category, finding } as EditTarget),
          onComments: () => setCommentsTarget({ kind, findingId: finding.id, title }),
          onHistory: () => setHistoryTarget({ kind, findingId: finding.id, title }),
        }}
      />
    );
  }

  function renderList(): ReactNode {
    if (active.isPending) return <FindingListSkeleton />;
    if (active.isError) {
      return <InlineError message={active.error.message} onRetry={() => void active.refetch()} />;
    }
    if (allRows.length === 0) {
      return (
        <div className="rounded-lg border border-dashed border-border-strong px-6 py-12 text-center">
          <FileQuestion aria-hidden className="mx-auto size-5 text-ink-3" strokeWidth={1.5} />
          <p className="mt-3 text-sm font-medium text-ink-1">
            {CATEGORY_LABELS[category]} bulgusu çıkarılmadı
          </p>
          <p className="mt-1 text-sm text-ink-2">
            {category === "compliance"
              ? "Uygunluk analizi için yetkinlik profilinizin tanımlı olması gerekir."
              : "Bu şartnamede bu türden bir madde bulunamadı."}
          </p>
        </div>
      );
    }
    if (filteredRows.length === 0) {
      return <FilterEmptyState onReset={resetFilters} />;
    }

    switch (category) {
      case "requirements":
        return (filteredRows as RequirementFinding[]).map((row) =>
          rowFor(
            row,
            row.text,
            <>
              <Badge tone="outline">{REQUIREMENT_KIND_LABELS[row.kind] ?? row.kind}</Badge>
              {row.is_mandatory && <Badge tone="warning">Zorunlu</Badge>}
            </>,
            row.is_mandatory ? "warning" : "ink",
          ),
        );
      case "deliverables":
        return (filteredRows as DeliverableFinding[]).map((row) =>
          rowFor(
            row,
            row.name,
            <>
              <Badge tone="outline">{DELIVERABLE_KIND_LABELS[row.kind] ?? row.kind}</Badge>
              {row.is_mandatory && <Badge tone="warning">Zorunlu</Badge>}
            </>,
            row.is_mandatory ? "warning" : "ink",
          ),
        );
      case "risks":
        return (filteredRows as RiskFinding[]).map((row) => {
          const severity = RISK_SEVERITY[row.severity];
          return rowFor(
            row,
            row.text,
            <>
              {severity !== undefined && (
                <Badge tone={severity.tone} dot>
                  {severity.label}
                </Badge>
              )}
              <Badge tone="outline">{RISK_CATEGORY_LABELS[row.category] ?? row.category}</Badge>
            </>,
            row.severity === "high" ? "danger" : row.severity === "medium" ? "warning" : "ink",
          );
        });
      case "timeline":
        return (filteredRows as TimelineFinding[]).map((row) =>
          rowFor(
            row,
            `${row.label}: ${row.value_text}`,
            <Badge tone="outline">{TIMELINE_KIND_LABELS[row.kind] ?? row.kind}</Badge>,
            "ink",
          ),
        );
      case "compliance":
        return (filteredRows as ComplianceFinding[]).map((row) => {
          const status = COMPLIANCE_STATUS[row.status];
          return rowFor(
            row,
            row.requirement_text,
            status !== undefined ? (
              <Badge tone={status.tone} dot>
                {status.label}
              </Badge>
            ) : null,
            row.status === "unmet" ? "danger" : row.status === "partial" ? "warning" : "success",
          );
        });
    }
  }

  return (
    <div className="flex h-[calc(100vh-6.5rem)] min-h-[560px] flex-col">
      {/* ── Başlık: ne inceliyorum + ne kadarı bitti + çıktı ─────────────── */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="truncate font-display text-2xl font-semibold text-ink-1">
            {tender.data?.title ?? "İhale"}
          </h1>
          <p className="mt-1 text-sm text-ink-2">
            Her bulguyu kaynağında doğrulayın: onaylayın, düzeltin ya da reddedin.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-4">
          <ReviewProgress decided={decided} total={allRows.length} />
          <ExportDialog tenderId={tenderId} />
        </div>
      </div>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-12">
        {/* ── Sol bölme: bulgu listesi ───────────────────────────────────── */}
        <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-surface lg:col-span-5 xl:col-span-4">
          <div className="shrink-0 border-b border-border p-3">
            <Tabs value={category} onValueChange={switchCategory} className="gap-3">
              <TabsList variant="segment" className="w-full">
                {(Object.keys(CATEGORY_LABELS) as FindingCategory[]).map((key) => (
                  <TabsTrigger key={key} value={key} className="min-w-0 flex-1 px-1.5 text-xs">
                    <span className="truncate">{CATEGORY_LABELS[key]}</span>
                    <span className="font-mono text-[10px] text-ink-3">{counts[key] ?? "·"}</span>
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <FilterChip
                label={category === "risks" ? "Tüm şiddetler" : "Tüm türler"}
                value={kindFilter}
                options={kindOptions}
                onChange={setKindFilter}
              />
              <FilterChip
                label="İnceleme: tümü"
                value={reviewFilter}
                options={Object.entries(REVIEW_STATUS).map(([value, meta]) => ({
                  value,
                  label: meta.label,
                }))}
                onChange={setReviewFilter}
              />
              {showMandatoryFilter && (
                <ToggleChip
                  label="Yalnız zorunlu"
                  pressed={mandatoryOnly}
                  onPressedChange={setMandatoryOnly}
                />
              )}
              {filtersDirty && (
                <Button variant="ghost" size="sm" className="text-ink-3" onClick={resetFilters}>
                  Sıfırla
                </Button>
              )}
            </div>

            {/* Toplu seçim araç çubuğu YERİNDE değişir, yeni bar açılmaz (§9.3). */}
            {checked.size > 0 ? (
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-sm bg-accent px-3 py-2">
                <span className="text-sm font-medium text-ink-on-accent">
                  {checked.size} bulgu seçili
                </span>
                <div className="flex items-center gap-1">
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => bulkAct("approve")}
                    disabled={bulk.isPending}
                  >
                    <Check strokeWidth={2.5} /> Onayla
                  </Button>
                  <Button
                    size="xs"
                    variant="secondary"
                    className="text-danger"
                    onClick={() => bulkAct("reject")}
                    disabled={bulk.isPending}
                  >
                    <X strokeWidth={2.5} /> Reddet
                  </Button>
                  <Button
                    size="xs"
                    variant="ghost"
                    className="text-ink-on-accent hover:bg-white/10 hover:text-ink-on-accent"
                    onClick={() => setChecked(new Set())}
                  >
                    Vazgeç
                  </Button>
                </div>
              </div>
            ) : (
              filteredRows.length > 0 && (
                <label className="mt-3 flex w-fit cursor-pointer items-center gap-2 text-xs text-ink-3">
                  <Checkbox
                    checked={allVisibleChecked}
                    onCheckedChange={(value) =>
                      setChecked(value === true ? new Set(filteredRows.map((r) => r.id)) : new Set())
                    }
                  />
                  Görünen {filteredRows.length} bulgunun tümünü seç
                </label>
              )
            )}
          </div>

          <ScrollArea className="scroll-slim min-h-0 flex-1">
            <div className="flex flex-col gap-2 p-3">{renderList()}</div>
          </ScrollArea>

          <div className="shrink-0 border-t border-border px-3 py-2">
            <p className="text-xs text-ink-3">
              {EMPTY_BY_CATEGORY[category].startsWith("Bu") && filteredRows.length > 0
                ? `${filteredRows.length} / ${allRows.length} bulgu gösteriliyor`
                : `${allRows.length} bulgu`}
            </p>
          </div>
        </section>

        {/* ── Sağ bölme: doküman tuvali ──────────────────────────────────── */}
        <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-surface lg:col-span-7 xl:col-span-8">
          <div className="flex h-11 shrink-0 items-center gap-2 border-b border-border px-3">
            <FileText aria-hidden className="size-4 shrink-0 text-ink-3" strokeWidth={1.5} />
            {pdfDocuments.length > 0 ? (
              <Select
                value={activeDocId ?? undefined}
                onValueChange={(id) => {
                  setViewerDocId(id);
                  setViewerPage(1);
                }}
              >
                <SelectTrigger
                  size="sm"
                  aria-label="Görüntülenen doküman"
                  className="max-w-96 border-0 px-1 hover:bg-surface-2"
                >
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

          {/* Konumsuz format (DOCX/XLSX): sayfa yok ama ALINTI var — kırmızı
              çizgi gereği kaynak yine de gösterilir. */}
          {selection !== null && !selectedDocIsPdf && (
            <div className="border-b border-border p-4">
              <p className="mb-2.5 text-xs text-ink-3">
                Bu doküman türünde sayfa görüntüsü yok. Şartnamedeki alıntı:
              </p>
              <EvidenceQuote
                quote={selection.quote}
                page={selection.page}
                section={selection.section}
              />
            </div>
          )}

          <div className={cn("min-h-0 flex-1", !activeDocIsPdf && "grid place-items-center")}>
            {activeDocIsPdf === true && documentFile.data !== undefined ? (
              <PdfViewer
                fileUrl={documentFile.data.url}
                page={viewerPage}
                onPageChange={setViewerPage}
                highlight={highlight}
                highlightKey={highlightKey}
              />
            ) : activeDocIsPdf === true && documentFile.isPending ? (
              <div className="h-full p-4">
                <Skeleton className="h-full w-full" />
              </div>
            ) : activeDocIsPdf === true && documentFile.isError ? (
              <InlineError
                className="m-4"
                message={documentFile.error.message}
                onRetry={() => void documentFile.refetch()}
              />
            ) : (
              selection === null && (
                <div className="px-6 py-10 text-center">
                  <FileText aria-hidden className="mx-auto size-6 text-ink-3" strokeWidth={1.5} />
                  <p className="mt-3 text-sm font-medium text-ink-1">Kaynak burada açılır</p>
                  <p className="mt-1 max-w-[38ch] text-sm text-ink-2">
                    Soldan bir bulgu seçin; dokümandaki tam yeri vurgulanır.
                  </p>
                </div>
              )
            )}
          </div>
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
