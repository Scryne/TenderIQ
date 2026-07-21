"use client";

/**
 * İnsan-döngüde inceleme veri katmanı (Sprint 3.2, §4.3).
 *
 * Onay/red/geri alma ve içerik düzeltmesi optimistic çalışır: önbellek anında
 * güncellenir, hata olursa geri alınır (rollback + toast). Beş bulgu kategorisi
 * aynı önbellek anahtarı düzenini kullanır: `[category, tenderId]`.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "@tenderiq/api-client";
import { toast } from "sonner";

import { api } from "@/lib/api";
import {
  CATEGORY_TO_KIND,
  type AnyFinding,
  type FindingCategory,
  type FindingKind,
  type ReviewAction,
  type ReviewStatus,
} from "@/lib/findings";

type Schemas = components["schemas"];

/** Kategoriye özgü düzeltilebilir alanlar (action hariç PATCH gövdesi). */
export type EditFieldsFor = {
  requirements: Omit<Schemas["RequirementPatch"], "action">;
  deliverables: Omit<Schemas["DeliverablePatch"], "action">;
  risks: Omit<Schemas["RiskPatch"], "action">;
  timeline: Omit<Schemas["TimelineEventPatch"], "action">;
  compliance: Omit<Schemas["ComplianceResultPatch"], "action">;
};

/** Düzeltme mutasyonunun değişkenleri: kategori + alanlar birlikte daralır. */
export type EditVariables = {
  [C in FindingCategory]: { category: C; id: string; fields: EditFieldsFor[C] };
}[FindingCategory];

const ACTION_STATUS: Record<ReviewAction, ReviewStatus> = {
  approve: "approved",
  reject: "rejected",
  reset: "pending",
};

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { error?: { message?: string } } | undefined)?.error?.message;
  return typeof message === "string" && message !== "" ? message : fallback;
}

async function patchFinding(
  category: FindingCategory,
  id: string,
  body: Record<string, unknown>,
): Promise<AnyFinding> {
  const params = { params: { path: { finding_id: id } } };
  switch (category) {
    case "requirements": {
      const { data, error } = await api.PATCH("/api/v1/requirements/{finding_id}", {
        ...params,
        body: body as Schemas["RequirementPatch"],
      });
      if (error !== undefined) throw new Error(errorMessage(error, "Gereksinim güncellenemedi."));
      return data;
    }
    case "deliverables": {
      const { data, error } = await api.PATCH("/api/v1/deliverables/{finding_id}", {
        ...params,
        body: body as Schemas["DeliverablePatch"],
      });
      if (error !== undefined) throw new Error(errorMessage(error, "Belge güncellenemedi."));
      return data;
    }
    case "risks": {
      const { data, error } = await api.PATCH("/api/v1/risks/{finding_id}", {
        ...params,
        body: body as Schemas["RiskPatch"],
      });
      if (error !== undefined) throw new Error(errorMessage(error, "Risk güncellenemedi."));
      return data;
    }
    case "timeline": {
      const { data, error } = await api.PATCH("/api/v1/timeline-events/{finding_id}", {
        ...params,
        body: body as Schemas["TimelineEventPatch"],
      });
      if (error !== undefined)
        throw new Error(errorMessage(error, "Takvim öğesi güncellenemedi."));
      return data;
    }
    case "compliance": {
      const { data, error } = await api.PATCH("/api/v1/compliance-results/{finding_id}", {
        ...params,
        body: body as Schemas["ComplianceResultPatch"],
      });
      if (error !== undefined)
        throw new Error(errorMessage(error, "Uygunluk sonucu güncellenemedi."));
      return data;
    }
  }
}

/** Onay/red/geri alma + içerik düzeltme + toplu onay/red mutasyonları. */
export function useFindingReview(tenderId: string) {
  const queryClient = useQueryClient();

  function cacheKey(category: FindingCategory): [FindingCategory, string] {
    return [category, tenderId];
  }

  async function snapshot(category: FindingCategory) {
    const key = cacheKey(category);
    await queryClient.cancelQueries({ queryKey: key });
    return { key, previous: queryClient.getQueryData<AnyFinding[]>(key) };
  }

  function patchCache(
    key: readonly unknown[],
    id: string,
    apply: (finding: AnyFinding) => AnyFinding,
  ) {
    queryClient.setQueryData<AnyFinding[]>(key as [FindingCategory, string], (old) =>
      old?.map((finding) => (finding.id === id ? apply(finding) : finding)),
    );
  }

  const act = useMutation({
    mutationFn: ({
      category,
      id,
      action,
    }: {
      category: FindingCategory;
      id: string;
      action: ReviewAction;
    }) => patchFinding(category, id, { action }),
    onMutate: async ({ category, id, action }) => {
      const context = await snapshot(category);
      patchCache(context.key, id, (finding) => ({
        ...finding,
        review: { ...finding.review, status: ACTION_STATUS[action] },
      }));
      return context;
    },
    onError: (error, _variables, context) => {
      if (context !== undefined) queryClient.setQueryData(context.key, context.previous);
      toast.error(error.message);
    },
    onSuccess: (data, { category, id }) => {
      patchCache(cacheKey(category), id, () => data);
    },
  });

  const edit = useMutation({
    mutationFn: ({ category, id, fields }: EditVariables) =>
      patchFinding(category, id, fields as Record<string, unknown>),
    onMutate: async ({ category, id, fields }) => {
      const context = await snapshot(category);
      patchCache(
        context.key,
        id,
        (finding) =>
          ({
            ...finding,
            ...(fields as Record<string, unknown>),
            review: { ...finding.review, status: "edited" as const },
          }) as AnyFinding,
      );
      return context;
    },
    onError: (error, _variables, context) => {
      if (context !== undefined) queryClient.setQueryData(context.key, context.previous);
      toast.error(error.message);
    },
    onSuccess: (data, { category, id }) => {
      patchCache(cacheKey(category), id, () => data);
      toast.success("Bulgu düzeltildi.");
    },
  });

  const bulk = useMutation({
    mutationFn: async ({
      category,
      ids,
      action,
    }: {
      category: FindingCategory;
      ids: string[];
      action: "approve" | "reject";
    }) => {
      const { data, error } = await api.POST("/api/v1/tenders/{tender_id}/findings/bulk-review", {
        params: { path: { tender_id: tenderId } },
        body: {
          action,
          items: ids.map((id) => ({ kind: CATEGORY_TO_KIND[category], id })),
        },
      });
      if (error !== undefined) throw new Error(errorMessage(error, "Toplu işlem başarısız."));
      return data;
    },
    onMutate: async ({ category, ids, action }) => {
      const context = await snapshot(category);
      const idSet = new Set(ids);
      queryClient.setQueryData<AnyFinding[]>(
        context.key as [FindingCategory, string],
        (old) =>
          old?.map((finding) => {
            if (!idSet.has(finding.id)) return finding;
            // Sunucu sözleşmesiyle aynı: toplu onay EDITED'ı ezmez.
            if (action === "approve" && finding.review.status === "edited") return finding;
            return {
              ...finding,
              review: { ...finding.review, status: ACTION_STATUS[action] },
            };
          }),
      );
      return context;
    },
    onError: (error, _variables, context) => {
      if (context !== undefined) queryClient.setQueryData(context.key, context.previous);
      toast.error(error.message);
    },
    onSuccess: (data, { category }) => {
      toast.success(
        data.skipped.length > 0
          ? `${data.updated} bulgu güncellendi, ${data.skipped.length} atlandı.`
          : `${data.updated} bulgu güncellendi.`,
      );
      // Sunucu gerçeğiyle hizala (EDITED atlama vb. kuralların sonucu).
      void queryClient.invalidateQueries({ queryKey: cacheKey(category) });
    },
  });

  return { act, edit, bulk };
}

/** Bulgunun ekip yorumları (dialog açıkken çekilir). */
export function useFindingComments(kind: FindingKind, findingId: string | null) {
  return useQuery({
    queryKey: ["finding-comments", kind, findingId],
    enabled: findingId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/findings/{kind}/{finding_id}/comments", {
        params: { path: { kind, finding_id: findingId ?? "" } },
      });
      if (error !== undefined) throw new Error(errorMessage(error, "Yorumlar yüklenemedi."));
      return data;
    },
  });
}

/** Yeni yorum ekler; listeyi tazeler. */
export function useAddFindingComment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      kind,
      findingId,
      body,
    }: {
      kind: FindingKind;
      findingId: string;
      body: string;
    }) => {
      const { data, error } = await api.POST("/api/v1/findings/{kind}/{finding_id}/comments", {
        params: { path: { kind, finding_id: findingId } },
        body: { body },
      });
      if (error !== undefined) throw new Error(errorMessage(error, "Yorum eklenemedi."));
      return data;
    },
    onError: (error) => toast.error(error.message),
    onSuccess: (_data, { kind, findingId }) => {
      void queryClient.invalidateQueries({ queryKey: ["finding-comments", kind, findingId] });
      void queryClient.invalidateQueries({ queryKey: ["finding-history", kind, findingId] });
    },
  });
}

/** Bulgunun düzenleme geçmişi (AuditLog; dialog açıkken çekilir). */
export function useFindingHistory(kind: FindingKind, findingId: string | null) {
  return useQuery({
    queryKey: ["finding-history", kind, findingId],
    enabled: findingId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/findings/{kind}/{finding_id}/history", {
        params: { path: { kind, finding_id: findingId ?? "" } },
      });
      if (error !== undefined) throw new Error(errorMessage(error, "Geçmiş yüklenemedi."));
      return data;
    },
  });
}

function parseAttachmentFilename(disposition: string | null): string | null {
  if (disposition === null) return null;
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (utf8?.[1] !== undefined) {
    try {
      return decodeURIComponent(utf8[1]);
    } catch {
      // düşmeye devam: ASCII fallback'e bak
    }
  }
  const ascii = /filename="([^"]+)"/i.exec(disposition);
  return ascii?.[1] ?? null;
}

/** Raporu üretir ve tarayıcı indirmesi başlatır (Word/Excel). */
export async function downloadTenderReport(
  tenderId: string,
  format: "docx" | "xlsx",
  includePending: boolean,
): Promise<void> {
  const { data, error, response } = await api.POST("/api/v1/tenders/{tender_id}/export", {
    params: { path: { tender_id: tenderId } },
    body: { format, include_pending: includePending },
    parseAs: "blob",
  });
  if (error !== undefined) throw new Error(errorMessage(error, "Rapor üretilemedi."));
  const filename =
    parseAttachmentFilename(response.headers.get("content-disposition")) ??
    `tenderiq-rapor.${format}`;
  const url = URL.createObjectURL(data as Blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
