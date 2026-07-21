"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";

export default function CapabilityProfilePage() {
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);

  const profile = useQuery({
    queryKey: ["capability-profile"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/capability-profile");
      if (error !== undefined) {
        if (response.status === 404) return null; // henüz tanımlanmamış
        throw new Error("Yetkinlik profili yüklenemedi.");
      }
      return data;
    },
  });

  // Sunucudaki içerik forma bir kez yazılır; kullanıcı düzenlemeye başladıysa ezilmez.
  useEffect(() => {
    if (!dirty && profile.data != null) setContent(profile.data.content);
  }, [dirty, profile.data]);

  const save = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/capability-profile", {
        body: { content },
      });
      if (error !== undefined) throw new Error("Profil kaydedilemedi.");
      return data;
    },
    onSuccess: () => {
      setDirty(false);
      void queryClient.invalidateQueries({ queryKey: ["capability-profile"] });
      toast.success("Yetkinlik profili kaydedildi.");
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Yetkinlik profili"
        context="Uygunluk analizi, şartname gereksinimlerini bu beyanla karşılaştırır."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-[15px]">Firma yetkinlik beyanı</CardTitle>
          <CardDescription>
            Referans projeler, sertifikalar (ör. ISO 27001, CMMI), kadro ve teknoloji
            yetkinliklerinizi serbest metin olarak yazın.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {profile.isPending ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <Textarea
              value={content}
              onChange={(event) => {
                setContent(event.target.value);
                setDirty(true);
              }}
              placeholder={
                "ör. 12 yıllık kamu BT entegratörüyüz; ISO 9001 ve ISO 27001 belgelerimiz " +
                "mevcut. 45 kişilik yazılım ekibi (Java, .NET, PostgreSQL)…"
              }
              className="min-h-48 font-mono text-[13px] leading-5"
            />
          )}
          {profile.isError && <p className="text-sm text-danger">{profile.error.message}</p>}
          <div className="flex items-center justify-end gap-3">
            {dirty && <span className="text-xs text-ink-3">Kaydedilmemiş değişiklik var</span>}
            <Button
              onClick={() => save.mutate()}
              disabled={save.isPending || content.trim() === "" || !dirty}
            >
              {save.isPending ? "Kaydediliyor…" : "Profili kaydet"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
