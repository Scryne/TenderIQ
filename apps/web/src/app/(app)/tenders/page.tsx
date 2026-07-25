"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/shell/page-header";
import { NewTenderDialog } from "@/components/tenders/new-tender-dialog";
import { TenderListView } from "@/components/tenders/tender-list-view";
import { api } from "@/lib/api";

export default function TendersPage() {
  const router = useRouter();

  const tenders = useQuery({
    queryKey: ["tenders"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/tenders");
      if (error !== undefined) {
        if (response.status === 401) router.push("/login");
        throw new Error("İhaleler yüklenemedi.");
      }
      return data;
    },
  });

  return (
    <>
      <PageHeader
        title="İhalelerim"
        description="Şartnameyi yükleyin; gereksinim, belge, risk ve takvim analizi kaynağıyla birlikte çıksın."
        actions={<NewTenderDialog />}
      />
      <TenderListView
        tenders={tenders.data ?? []}
        state={tenders.isPending ? "loading" : tenders.isError ? "error" : "ready"}
        errorMessage={tenders.error?.message}
        onRetry={() => void tenders.refetch()}
        newTenderAction={<NewTenderDialog />}
      />
    </>
  );
}
