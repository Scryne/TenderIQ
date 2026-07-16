"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { use, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api";
import { useTenderStream } from "@/lib/tender-stream";
import { cn } from "@/lib/utils";

// İşleme hattı fazları (§5.5) — ilerleme göstergesi bu sırayla çizilir.
const PIPELINE_STEPS = [
  { key: "queued", label: "Kuyrukta" },
  { key: "parsing", label: "Ayrıştırma" },
  { key: "indexing", label: "İndeksleme" },
  { key: "extracting", label: "Çıkarım" },
  { key: "review_ready", label: "İncelemeye hazır" },
] as const;

const DOCUMENT_KINDS = [
  { value: "technical", label: "Teknik şartname" },
  { value: "administrative", label: "İdari şartname" },
  { value: "contract", label: "Sözleşme" },
  { value: "addendum", label: "Zeyilname" },
  { value: "other", label: "Diğer" },
] as const;

const EXTENSION_CONTENT_TYPES: Record<string, string> = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

function resolveContentType(file: File): string {
  if (file.type !== "") return file.type;
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  return EXTENSION_CONTENT_TYPES[extension] ?? "application/octet-stream";
}

/** Backend hata zarfındaki mesajı çıkarır; yoksa verilen genel mesaja düşer. */
function apiErrorMessage(error: unknown, fallback: string): string {
  const message = (error as { error?: { message?: string } } | undefined)?.error?.message;
  return typeof message === "string" && message.length > 0 ? message : fallback;
}

function JobProgress({
  jobStatus,
  errorMessage,
}: {
  jobStatus: string;
  errorMessage: string | null;
}) {
  if (jobStatus === "failed") {
    return (
      <div className="text-sm text-destructive">
        İşleme başarısız oldu{errorMessage !== null ? `: ${errorMessage}` : "."}
      </div>
    );
  }
  const activeIndex = PIPELINE_STEPS.findIndex((step) => step.key === jobStatus);
  return (
    <ol className="flex flex-wrap items-center gap-2">
      {PIPELINE_STEPS.map((step, index) => {
        const done = index < activeIndex || jobStatus === "review_ready";
        const active = index === activeIndex && jobStatus !== "review_ready";
        return (
          <li key={step.key} className="flex items-center gap-2">
            {index > 0 && <span className="text-muted-foreground">→</span>}
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs",
                done && "bg-primary text-primary-foreground",
                active && "animate-pulse bg-primary/20 text-primary",
                !done && !active && "bg-muted text-muted-foreground",
              )}
            >
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export default function TenderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: tenderId } = use(params);
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState<string>("technical");
  const { snapshot, connected } = useTenderStream(tenderId);

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

  // İlk boya için REST listesi; canlı güncellemeler SSE snapshot'ından gelir.
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

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const contentType = resolveContentType(file);

      // 1) Doküman kaydı + imzalı yükleme URL'i (Idempotency-Key ile).
      const created = await api.POST("/api/v1/tenders/{tender_id}/documents", {
        params: { path: { tender_id: tenderId } },
        body: { filename: file.name, content_type: contentType, kind: kind as never },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      if (created.error !== undefined) {
        throw new Error(apiErrorMessage(created.error, "Doküman kaydı oluşturulamadı."));
      }

      // 2) Dosya doğrudan nesne depolamaya (imzalı URL) yüklenir.
      const putResponse = await fetch(created.data.upload_url, {
        method: "PUT",
        headers: { "content-type": contentType },
        body: file,
      });
      if (!putResponse.ok) throw new Error("Dosya depolamaya yüklenemedi.");

      // 3) Tamamlama: sunucu doğrular ve işleme hattını kuyruğa atar.
      const completed = await api.POST("/api/v1/documents/{document_id}/complete", {
        params: { path: { document_id: created.data.document.id } },
      });
      if (completed.error !== undefined) {
        throw new Error(
          apiErrorMessage(completed.error, "Dosya doğrulamadan geçemedi (tür/boyut uyuşmazlığı)."),
        );
      }
      return completed.data;
    },
    onSuccess: () => {
      if (fileInputRef.current !== null) fileInputRef.current.value = "";
      void queryClient.invalidateQueries({ queryKey: ["documents", tenderId] });
    },
  });

  // SSE snapshot'ı geldiyse onu, gelmediyse REST sonucunu göster.
  const documentRows =
    snapshot?.documents ??
    documents.data?.map((d) => ({
      id: d.id,
      filename: d.filename,
      status: d.status,
      job: null,
    })) ??
    [];

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <Link href="/tenders" className="text-sm text-muted-foreground hover:underline">
            ← İhalelerim
          </Link>
          <h1 className="text-2xl font-bold tracking-tight">
            {tender.data?.title ?? "İhale"}
          </h1>
        </div>
        <span
          className={cn(
            "rounded-full px-3 py-1 text-xs",
            connected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground",
          )}
          title={connected ? "Canlı durum akışı bağlı" : "Canlı akış yeniden bağlanıyor…"}
        >
          {connected ? "● Canlı" : "○ Bağlanıyor…"}
        </span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Şartname yükle</CardTitle>
          <CardDescription>
            PDF, DOCX veya XLSX (en fazla 100 MB). Yükleme sonrası analiz otomatik başlar.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-wrap items-center gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              const file = fileInputRef.current?.files?.[0];
              if (file !== undefined) upload.mutate(file);
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              required
              accept=".pdf,.docx,.xlsx"
              className="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-1.5 file:text-sm file:font-medium"
            />
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value)}
              className="h-9 rounded-md border border-input bg-transparent px-2 text-sm"
            >
              {DOCUMENT_KINDS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <Button type="submit" disabled={upload.isPending}>
              {upload.isPending ? "Yükleniyor…" : "Yükle ve analiz et"}
            </Button>
          </form>
          {upload.isError && (
            <p className="mt-2 text-sm text-destructive">{upload.error.message}</p>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Dokümanlar</h2>
        {documents.isPending && snapshot === null && (
          <p className="text-sm text-muted-foreground">Yükleniyor…</p>
        )}
        {documentRows.length === 0 && !documents.isPending && (
          <p className="text-sm text-muted-foreground">
            Henüz doküman yok. İlk şartnameyi yukarıdan yükleyin.
          </p>
        )}
        {documentRows.map((document) => (
          <Card key={document.id}>
            <CardContent className="space-y-3 py-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">{document.filename}</span>
                {document.status === "pending_upload" && (
                  <span className="text-xs text-muted-foreground">Yükleme bekleniyor</span>
                )}
                {document.status === "failed" && (
                  <span className="text-xs text-destructive">Yükleme başarısız</span>
                )}
              </div>
              {document.job !== null && (
                <JobProgress
                  jobStatus={document.job.status}
                  errorMessage={document.job.error_message}
                />
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
