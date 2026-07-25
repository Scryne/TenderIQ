"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { use, useRef, useState } from "react";
import { toast } from "sonner";

import {
  SideNote,
  TenderDetailView,
  UploadCard,
  type DocumentRow,
} from "@/components/tenders/tender-detail-view";
import { api } from "@/lib/api";
import { useTenderStream } from "@/lib/tender-stream";

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

  const retryJob = useMutation({
    mutationFn: async (jobId: string) => {
      const { error } = await api.POST("/api/v1/jobs/{job_id}/retry", {
        params: { path: { job_id: jobId } },
      });
      if (error !== undefined) throw new Error("İşleme yeniden başlatılamadı.");
    },
    onSuccess: () => {
      toast.success("İşleme yeniden başlatıldı.");
      void queryClient.invalidateQueries({ queryKey: ["documents", tenderId] });
    },
    onError: (error: Error) => toast.error(error.message),
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
          apiErrorMessage(
            completed.error,
            "Dosya doğrulamadan geçmedi. Tür ve boyutu kontrol edin.",
          ),
        );
      }
      return completed.data;
    },
    onSuccess: () => {
      if (fileInputRef.current !== null) fileInputRef.current.value = "";
      void queryClient.invalidateQueries({ queryKey: ["documents", tenderId] });
    },
  });

  const restRows: DocumentRow[] =
    documents.data?.map((document) => ({
      id: document.id,
      filename: document.filename,
      status: document.status,
      kind: document.kind,
      sizeBytes: document.size_bytes,
      job: null,
    })) ?? [];

  // SSE snapshot'ı geldiyse onu esas al; dosya boyutu/türü REST'ten tamamlanır.
  const restById = new Map(restRows.map((row) => [row.id, row]));
  const rows: DocumentRow[] =
    snapshot?.documents.map((document) => ({
      id: document.id,
      filename: document.filename,
      status: document.status,
      kind: restById.get(document.id)?.kind ?? null,
      sizeBytes: restById.get(document.id)?.sizeBytes ?? null,
      job: document.job,
    })) ?? restRows;

  const reviewReady = rows.some((row) => row.job?.status === "review_ready");

  return (
    <TenderDetailView
      title={tender.data?.title ?? "İhale"}
      documents={rows}
      documentsState={
        documents.isPending && snapshot === null
          ? "loading"
          : documents.isError
            ? "error"
            : "ready"
      }
      errorMessage={documents.error?.message}
      onRetry={() => void documents.refetch()}
      connected={connected}
      reviewHref={`/tenders/${tenderId}/review`}
      reviewReady={reviewReady}
      onRetryJob={(jobId) => retryJob.mutate(jobId)}
      retryingJobId={retryJob.isPending ? retryJob.variables : null}
      uploader={
        <>
          <UploadCard
            kind={kind}
            onKindChange={setKind}
            onSubmit={(file) => upload.mutate(file)}
            pending={upload.isPending}
            error={upload.isError ? upload.error.message : null}
            fileInputRef={fileInputRef}
          />
          <SideNote title="İpucu">
            Teknik ve idari şartnameyi ayrı ayrı yükleyin. Zeyilname varsa onu da ekleyin —
            uygunluk analizi en güncel maddeyi esas alır.
          </SideNote>
        </>
      }
    />
  );
}
