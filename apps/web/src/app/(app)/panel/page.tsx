"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import {
  PanelView,
  type DeadlineItem,
  type ExposureItem,
  type PanelData,
} from "@/components/panel/panel-view";
import { PageHeader } from "@/components/shell/page-header";
import { NewTenderDialog } from "@/components/tenders/new-tender-dialog";
import { api } from "@/lib/api";
import { parseTrDate } from "@/lib/format";

/**
 * Panel verisi ÇOKLU uçtan birleştirilir; sunucuda toplu bir "panel" ucu yok.
 * İstek sayısını sınırlamak için ayrıntılı bulgular yalnız incelemeye hazır
 * ilk `DETAIL_LIMIT` ihale için çekilir.
 *
 * TODO(backend): `GET /api/v1/panel` — tek çağrıda özet. Kapalı beta ölçeğinde
 * (onlarca ihale) mevcut yaklaşım yeterli; müşteri sayısı artınca N+1 olur.
 */
const DETAIL_LIMIT = 5;

export default function PanelPage() {
  const tenders = useQuery({
    queryKey: ["tenders"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/tenders");
      if (error !== undefined) throw new Error("İhaleler yüklenemedi.");
      return data;
    },
  });

  const usage = useQuery({
    queryKey: ["usage"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/usage");
      if (error !== undefined) throw new Error("Kullanım bilgisi alınamadı.");
      return data;
    },
  });

  const readyTenders = useMemo(
    () => (tenders.data ?? []).filter((tender) => tender.status === "review_ready").slice(0, DETAIL_LIMIT),
    [tenders.data],
  );

  const timelineQueries = useQueries({
    queries: readyTenders.map((tender) => ({
      queryKey: ["timeline", tender.id],
      queryFn: async () => {
        const { data, error } = await api.GET("/api/v1/tenders/{tender_id}/timeline", {
          params: { path: { tender_id: tender.id } },
        });
        if (error !== undefined) throw new Error("Takvim yüklenemedi.");
        return data;
      },
    })),
  });

  const riskQueries = useQueries({
    queries: readyTenders.map((tender) => ({
      queryKey: ["risks", tender.id],
      queryFn: async () => {
        const { data, error } = await api.GET("/api/v1/tenders/{tender_id}/risks", {
          params: { path: { tender_id: tender.id } },
        });
        if (error !== undefined) throw new Error("Riskler yüklenemedi.");
        return data;
      },
    })),
  });

  const complianceQueries = useQueries({
    queries: readyTenders.map((tender) => ({
      queryKey: ["compliance", tender.id],
      queryFn: async () => {
        const { data, error } = await api.GET("/api/v1/tenders/{tender_id}/compliance", {
          params: { path: { tender_id: tender.id } },
        });
        if (error !== undefined) throw new Error("Uygunluk sonuçları yüklenemedi.");
        return data;
      },
    })),
  });

  const detailLoading =
    [...timelineQueries, ...riskQueries, ...complianceQueries].some((query) => query.isPending) &&
    readyTenders.length > 0;

  const data: PanelData = useMemo(() => {
    const list = tenders.data ?? [];

    const deadlines: DeadlineItem[] = [];
    const exposures: ExposureItem[] = [];

    readyTenders.forEach((tender, index) => {
      for (const event of timelineQueries[index]?.data ?? []) {
        // Reddedilmiş bulgular panelde görünmez — kullanıcı zaten eledi.
        if (event.review?.status === "rejected") continue;
        deadlines.push({
          id: event.id,
          tenderId: tender.id,
          tenderTitle: tender.title,
          label: event.label,
          valueText: event.value_text,
          date: parseTrDate(event.value_text),
          page: event.source.page,
          section: event.source.section,
        });
      }
      for (const risk of riskQueries[index]?.data ?? []) {
        if (risk.severity !== "high" || risk.review?.status === "rejected") continue;
        exposures.push({
          id: risk.id,
          tenderId: tender.id,
          tenderTitle: tender.title,
          text: risk.text,
          source: "risk",
          severity: "high",
          page: risk.source.page,
          section: risk.source.section,
        });
      }
      for (const result of complianceQueries[index]?.data ?? []) {
        if (result.status !== "unmet" || result.review?.status === "rejected") continue;
        exposures.push({
          id: result.id,
          tenderId: tender.id,
          tenderTitle: tender.title,
          text: result.requirement_text,
          source: "compliance",
          severity: "unmet",
          page: result.source.page,
          section: result.source.section,
        });
      }
    });

    // Ayrıştırılabilen tarihler önce ve yakından uzağa; ayrıştırılamayanlar sonda.
    deadlines.sort((a, b) => {
      if (a.date === null && b.date === null) return 0;
      if (a.date === null) return 1;
      if (b.date === null) return -1;
      return a.date.getTime() - b.date.getTime();
    });

    // Karşılanmayan gereksinim, sözleşme riskinden önce gelir: eleme sebebi odur.
    exposures.sort((a, b) => (a.source === b.source ? 0 : a.source === "compliance" ? -1 : 1));

    return {
      totalTenders: list.length,
      reviewReady: list.filter((tender) => tender.status === "review_ready").length,
      analyzing: list.filter((tender) => tender.status === "analyzing").length,
      drafts: list.filter((tender) => tender.status === "draft").length,
      quota:
        usage.data === undefined
          ? []
          : [
              {
                label: "Doküman",
                used: usage.data.documents.used,
                limit: usage.data.documents.limit,
              },
              { label: "Sayfa", used: usage.data.pages.used, limit: usage.data.pages.limit },
            ],
      periodEnd: usage.data?.period_end ?? null,
      deadlines,
      exposures,
      inProgress: list
        .filter((tender) => tender.status === "analyzing")
        .map((tender) => ({ id: tender.id, title: tender.title })),
      detailLoading,
    };
  }, [tenders.data, usage.data, readyTenders, timelineQueries, riskQueries, complianceQueries, detailLoading]);

  return (
    <>
      <PageHeader
        title="Panel"
        description="Açık ihalelerinizde eleme riski taşıyan maddeler ve yaklaşan teklif tarihleri."
        actions={<NewTenderDialog variant="secondary" />}
      />
      <PanelView
        data={data}
        state={tenders.isPending ? "loading" : tenders.isError ? "error" : "ready"}
        errorMessage={tenders.error?.message}
        onRetry={() => void tenders.refetch()}
        newTenderAction={<NewTenderDialog />}
      />
    </>
  );
}
