"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Info } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shell/page-header";
import { InlineError } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/format";

/** Bir uygunluk analizinin anlamlı olması için beklenen en az beyan uzunluğu. */
const MIN_USEFUL_LENGTH = 200;

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
      const { data, error } = await api.POST("/api/v1/capability-profile", { body: { content } });
      if (error !== undefined) throw new Error("Profil kaydedilemedi. Bir kez daha deneyin.");
      return data;
    },
    onSuccess: () => {
      setDirty(false);
      void queryClient.invalidateQueries({ queryKey: ["capability-profile"] });
      // Eylem sonucu geçmiş zamanla yazılır (§8.8).
      toast.success("Yetkinlik profili kaydedildi.");
    },
    onError: (error) => toast.error(error.message),
  });

  const trimmed = content.trim();
  const defined = profile.data != null;
  const tooShort = trimmed.length > 0 && trimmed.length < MIN_USEFUL_LENGTH;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Yetkinlik profili"
        description="Uygunluk analizi, şartname gereksinimlerini bu beyanla karşılaştırır."
        meta={
          defined ? (
            <Badge tone="success" dot>
              Tanımlı
            </Badge>
          ) : (
            <Badge tone="warning" dot>
              Tanımlı değil
            </Badge>
          )
        }
      />

      {/* Bağlam kutusu: kullanıcı bu alanın NİYE var olduğunu bilmezse
          yarım yazar ve uygunluk sekmesi boş çıkar. */}
      <div className="mb-4 flex items-start gap-3 rounded-lg border border-border bg-surface p-4">
        <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-ink-3" strokeWidth={1.75} />
        <p className="text-sm text-ink-2">
          Bu beyan boşken inceleme ekranındaki <span className="font-medium text-ink-1">Uygunluk</span>{" "}
          sekmesi sonuç üretemez. Ne kadar somut yazarsanız — sertifika numarası, referans proje
          adı, kadro sayısı — karşılanmayan maddeler o kadar isabetli çıkar.
        </p>
      </div>

      <Card>
        <CardHeader className="block">
          <CardTitle>Firma yetkinlik beyanı</CardTitle>
          <CardDescription>
            Referans projeler, sertifikalar (ör. ISO 9001, ISO 27001), kadro ve teknoloji
            yetkinliklerinizi serbest metin olarak yazın.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 pt-0">
          <Label htmlFor="capability-content" className="sr-only">
            Yetkinlik beyanı
          </Label>
          {profile.isPending ? (
            <Skeleton className="h-56 w-full" />
          ) : (
            <Textarea
              id="capability-content"
              value={content}
              onChange={(event) => {
                setContent(event.target.value);
                setDirty(true);
              }}
              placeholder={
                "12 yıllık kamu BT entegratörüyüz. ISO 9001 ve ISO 27001 belgelerimiz güncel.\n" +
                "45 kişilik yazılım ekibi: Java, .NET, PostgreSQL, Kubernetes.\n" +
                "Referans: 2024 — Sağlık Bakanlığı veri merkezi taşıma projesi (18 ay)."
              }
              className="min-h-56 font-mono text-[13px] leading-5"
              aria-describedby="capability-help"
            />
          )}
          {profile.isError && (
            <InlineError
              message={profile.error.message}
              onRetry={() => void profile.refetch()}
            />
          )}
          <div id="capability-help" className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-ink-3">
              {formatNumber(trimmed.length)} karakter
              {tooShort && " — uygunluk analizi için kısa görünüyor"}
            </p>
            {defined && !dirty && (
              <p className="flex items-center gap-1.5 text-xs text-ink-3">
                <CheckCircle2 aria-hidden className="size-3.5 text-success" strokeWidth={2} />
                Kayıtlı
              </p>
            )}
          </div>
        </CardContent>
        <CardFooter className="justify-end">
          {dirty && <span className="mr-auto text-xs text-warning">Kaydedilmemiş değişiklik var</span>}
          <Button
            onClick={() => save.mutate()}
            loading={save.isPending}
            disabled={trimmed === "" || !dirty}
          >
            Profili kaydet
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
