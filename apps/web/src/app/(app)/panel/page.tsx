"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { PanelView, type PanelData } from "@/components/panel/panel-view";
import { PageHeader } from "@/components/shell/page-header";
import { NewTenderDialog } from "@/components/tenders/new-tender-dialog";
import { api } from "@/lib/api";

/**
 * Panel verisi TEK uçtan gelir (`GET /api/v1/panel`).
 *
 * Önceden beş uçtan birleştiriliyordu ve istekleri sınırlamak için yalnız ilk
 * beş incelemeye-hazır ihalenin bulguları çekiliyordu; bu da "en yakın son
 * teklif tarihi"ni değil "ilk beş ihalenin en yakın tarihi"ni gösteriyordu.
 * Sunucu artık sıralamayı (ayrıştırılmış tarihe göre) ve limiti kendisi
 * uyguladığından burada yalnız sunum eşlemesi kalır.
 */
const EMPTY: PanelData = {
  totalTenders: 0,
  reviewReady: 0,
  analyzing: 0,
  drafts: 0,
  quota: [],
  periodEnd: null,
  deadlines: [],
  exposures: [],
  inProgress: [],
};

export default function PanelPage() {
  const panel = useQuery({
    queryKey: ["panel"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/panel");
      if (error !== undefined) throw new Error("Panel verisi yüklenemedi.");
      return data;
    },
  });

  const data: PanelData = useMemo(() => {
    const body = panel.data;
    if (body === undefined) return EMPTY;

    return {
      totalTenders: body.tenders.total,
      reviewReady: body.tenders.review_ready,
      analyzing: body.tenders.analyzing,
      drafts: body.tenders.draft,
      quota: [
        { label: "Doküman", used: body.documents.used, limit: body.documents.limit },
        { label: "Sayfa", used: body.pages.used, limit: body.pages.limit },
      ],
      periodEnd: body.period_end,
      deadlines: body.deadlines.map((item) => ({
        id: item.id,
        tenderId: item.tender_id,
        tenderTitle: item.tender_title,
        label: item.label,
        valueText: item.value_text,
        // Sunucu ayrıştırıp sıraladı; burada yeniden ayrıştırmıyoruz — aynı
        // metnin iki farklı yerde farklı sonuç vermesi sıralamayı bozardı.
        date: item.due_date === null ? null : new Date(`${item.due_date}T00:00:00`),
        page: item.page,
        section: item.section,
      })),
      exposures: body.exposures.map((item) => ({
        id: item.id,
        tenderId: item.tender_id,
        tenderTitle: item.tender_title,
        text: item.text,
        source: item.source,
        severity: item.source === "compliance" ? ("unmet" as const) : ("high" as const),
        page: item.page,
        section: item.section,
      })),
      inProgress: body.in_progress.map((item) => ({ id: item.id, title: item.title })),
    };
  }, [panel.data]);

  return (
    <>
      <PageHeader
        title="Panel"
        description="Açık ihalelerinizde eleme riski taşıyan maddeler ve yaklaşan teklif tarihleri."
        actions={<NewTenderDialog variant="secondary" />}
      />
      <PanelView
        data={data}
        state={panel.isPending ? "loading" : panel.isError ? "error" : "ready"}
        errorMessage={panel.error?.message}
        onRetry={() => void panel.refetch()}
        newTenderAction={<NewTenderDialog />}
      />
    </>
  );
}
