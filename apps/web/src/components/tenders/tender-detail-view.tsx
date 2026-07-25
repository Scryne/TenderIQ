"use client";

import { FileText, ScanSearch, UploadCloud } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode, type RefObject } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { PipelineProgress } from "@/components/tenders/pipeline";
import { EmptyState, ErrorState, InlineError } from "@/components/states";
import { StatusPill } from "@/components/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { formatBytes } from "@/lib/format";
import { DOCUMENT_KINDS, DOCUMENT_KIND_LABELS } from "@/lib/tenders";
import { cn } from "@/lib/utils";

export type DocumentRow = {
  id: string;
  filename: string;
  status: string;
  kind?: string | null;
  sizeBytes?: number | null;
  job: { id: string; status: string; error_message: string | null; attempts: number } | null;
};

/**
 * İhale detayı — DESIGN.md §9.4.
 *
 * Sayfanın tek işi: "analiz nerede kaldı, incelemeye geçebilir miyim?"
 * O yüzden en belirgin öğe doküman listesi değil, her dokümanın hangi fazda
 * olduğunu gösteren ilerleme çizgisidir.
 */
export function TenderDetailView({
  title,
  documents,
  documentsState,
  errorMessage,
  onRetry,
  connected,
  reviewHref,
  reviewReady,
  uploader,
  onRetryJob,
  retryingJobId,
}: {
  title: string;
  documents: DocumentRow[];
  documentsState: "ready" | "loading" | "error";
  errorMessage?: string;
  onRetry?: () => void;
  connected: boolean;
  reviewHref: string;
  reviewReady: boolean;
  uploader: ReactNode;
  onRetryJob?: (jobId: string) => void;
  retryingJobId?: string | null;
}) {
  return (
    <>
      <PageHeader
        title={title}
        description="Şartname yükleyin; analiz bittiğinde bulguları kaynaklarıyla birlikte inceleyin."
        meta={
          <StatusPill
            tone={connected ? "success" : "neutral"}
            label={connected ? "Canlı" : "Bağlanıyor"}
          />
        }
        actions={
          reviewReady ? (
            <Button asChild>
              <Link href={reviewHref}>
                <ScanSearch strokeWidth={1.75} />
                Bulguları incele
              </Link>
            </Button>
          ) : (
            // Devre dışı buton yerine nedenini söyleyen metin (§10.5 ruhu):
            // kullanıcı neden tıklayamadığını bilmeli.
            <p className="text-sm text-ink-3">Analiz bitince inceleme açılır</p>
          )
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <div className="flex min-w-0 flex-col gap-4">
          {documentsState === "loading" && (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-24 rounded-lg" />
              <Skeleton className="h-24 rounded-lg" />
            </div>
          )}

          {documentsState === "error" && (
            <ErrorState
              title="Dokümanlar yüklenemedi"
              description={errorMessage ?? "Sunucuya ulaşılamıyor. Yeniden deneyin."}
              onRetry={onRetry}
              compact
            />
          )}

          {documentsState === "ready" && documents.length === 0 && (
            <EmptyState
              icon={FileText}
              title="Henüz doküman yok"
              description="Teknik ve idari şartnameyi yükleyin. Analiz yükleme biter bitmez kendiliğinden başlar."
              compact
            />
          )}

          {documentsState === "ready" &&
            documents.map((document) => (
              <article
                key={document.id}
                className="rounded-lg border border-border bg-surface p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="grid size-9 shrink-0 place-items-center rounded-md bg-surface-2">
                      <FileText aria-hidden className="size-4 text-ink-2" strokeWidth={1.5} />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink-1" title={document.filename}>
                        {document.filename}
                      </p>
                      <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-ink-3">
                        {document.kind != null && (
                          <span>{DOCUMENT_KIND_LABELS[document.kind] ?? document.kind}</span>
                        )}
                        {document.sizeBytes != null && (
                          <>
                            <span aria-hidden className="text-border-strong">
                              ·
                            </span>
                            <span>{formatBytes(document.sizeBytes)}</span>
                          </>
                        )}
                      </p>
                    </div>
                  </div>
                  {document.status === "pending_upload" && (
                    <StatusPill tone="neutral" label="Yükleme bekleniyor" />
                  )}
                  {document.status === "failed" && (
                    <StatusPill tone="danger" label="Yükleme başarısız" />
                  )}
                  {document.status === "uploaded" && document.job === null && (
                    <StatusPill tone="info" label="Kuyruğa alınıyor" />
                  )}
                </div>

                {document.job !== null && (
                  <PipelineProgress
                    status={document.job.status}
                    errorMessage={document.job.error_message}
                    attempts={document.job.attempts}
                    onRetry={
                      onRetryJob === undefined || document.job === null
                        ? undefined
                        : () => onRetryJob(document.job!.id)
                    }
                    retrying={retryingJobId === document.job.id}
                    className="mt-5"
                  />
                )}
              </article>
            ))}
        </div>

        <div className="flex min-w-0 flex-col gap-4">{uploader}</div>
      </div>
    </>
  );
}

/**
 * Yükleme kartı. Dosya seçimi + tür + gönder. Sürükle-bırak alanı, dosya
 * seçicinin görsel karşılığıdır; ikisi aynı `input`'u kullanır.
 */
export function UploadCard({
  kind,
  onKindChange,
  onSubmit,
  pending,
  error,
  fileInputRef,
}: {
  kind: string;
  onKindChange: (kind: string) => void;
  onSubmit: (file: File) => void;
  pending: boolean;
  error?: string | null;
  fileInputRef: RefObject<HTMLInputElement | null>;
}) {
  const [fileName, setFileName] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  return (
    <Card>
      <CardHeader className="block">
        <CardTitle>Şartname yükle</CardTitle>
        <CardDescription>
          PDF, DOCX veya XLSX · en fazla 100 MB. Yükleme sonrası analiz kendiliğinden başlar.
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            const file = fileInputRef.current?.files?.[0];
            if (file !== undefined) onSubmit(file);
          }}
        >
          <label
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              const dropped = event.dataTransfer.files[0];
              if (dropped !== undefined && fileInputRef.current !== null) {
                fileInputRef.current.files = event.dataTransfer.files;
                setFileName(dropped.name);
              }
            }}
            className={cn(
              "flex cursor-pointer flex-col items-center gap-2 rounded-md border border-dashed px-4 py-7 text-center transition-colors duration-[120ms]",
              dragging ? "border-accent bg-surface-2" : "border-border-strong hover:bg-surface-2",
            )}
          >
            <UploadCloud aria-hidden className="size-5 text-ink-3" strokeWidth={1.5} />
            <span className="text-sm font-medium text-ink-1">
              {fileName ?? "Dosyayı sürükleyin veya seçin"}
            </span>
            <span className="text-xs text-ink-3">PDF · DOCX · XLSX</span>
            <input
              ref={fileInputRef}
              type="file"
              required
              accept=".pdf,.docx,.xlsx"
              className="sr-only"
              onChange={(event) => setFileName(event.target.files?.[0]?.name ?? null)}
            />
          </label>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="document-kind">Doküman türü</Label>
            <Select value={kind} onValueChange={onKindChange}>
              <SelectTrigger id="document-kind" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DOCUMENT_KINDS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-ink-3">
              Tür, çıkarım ajanlarının hangi bulguları arayacağını belirler.
            </p>
          </div>

          {error != null && error !== "" && <InlineError message={error} />}

          <Button type="submit" variant="secondary" loading={pending} className="w-full">
            <UploadCloud strokeWidth={1.75} />
            Yükle ve analiz et
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

/** Yan panelde küçük bilgi kartı — hatırlatma, ipucu, kota uyarısı. */
export function SideNote({
  title,
  children,
  tone = "neutral",
}: {
  title: string;
  children: ReactNode;
  tone?: "neutral" | "warning";
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-4",
        tone === "warning" ? "border-warning/30 bg-warning-weak" : "border-border bg-surface",
      )}
    >
      <div className="flex items-center gap-2">
        <Badge tone={tone === "warning" ? "warning" : "neutral"}>{title}</Badge>
      </div>
      <div className="mt-2.5 text-sm leading-5 text-ink-2">{children}</div>
    </div>
  );
}
