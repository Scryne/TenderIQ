"use client";

/**
 * Yönetici teşhis kartı — `GET /api/v1/usage/admin` (Tur 16 backend, Tur 17 ekran).
 *
 * **Bu kartın yanıtladığı soru kullanıcınınkinden farklı:** üstteki kart "ne
 * kadarım kaldı" der, bu kart **"o sayıya ne kadar güvenebilirim"** der. İkisi
 * aynı ekranda çünkü ikincisi birincisini nitelendiriyor; ayrı bir sayfaya
 * koymak, yöneticinin harcamayı gördüğü yerde onun güvenilirliğini
 * göremediği bir kör nokta üretirdi.
 *
 * **`unpriced_calls` bu kartın asıl konusudur.** Tutarı hesaplanamamış her
 * çağrı harcama toplamına GİRMEZ; yani tavan olduğundan gevşek davranır ve
 * ekrandaki "kalan" gerçekte olduğundan büyük görünür. Sıfırdan farklıysa
 * uyarıya dönüşür — sessiz kalması, kapatılmak istenen arızanın ta kendisi.
 *
 * Erişim: uç yalnız kiracı yöneticisine açık (403). Arayüz de kartı yalnız
 * yöneticiye çizer — ama asıl kapı sunucudadır; bu yalnız gürültü azaltma.
 */

import type { components } from "@tenderiq/api-client";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { Notice } from "@/components/notice";
import { InlineError } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatCurrencyPrecise, formatDate, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export function AdminUsageCard() {
  const diagnostics = useQuery({
    queryKey: ["usage-admin"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/usage/admin");
      if (error !== undefined) throw new Error("Teşhis bilgisi alınamadı.");
      return data;
    },
  });

  return (
    <Card>
      <CardHeader>
        <div className="min-w-0">
          <CardTitle as="h2">Yönetici teşhisi</CardTitle>
          {/* Dönem burada CÜMLE içinde geçer, ızgarada bir "metrik" olarak
              değil: tarih aralığı ölçülen bir büyüklük değildir ve mono
              ızgarada ₺8,40 ile aynı ağırlığı alınca gerçek metrikleri
              sulandırıyordu. */}
          <CardDescription>
            {diagnostics.data === undefined
              ? "Yukarıdaki harcama sayısına ne kadar güvenilebileceğini bu değerler söyler."
              : `${formatDate(diagnostics.data.period_start)} – ${formatDate(diagnostics.data.period_end)} dönemi. Yukarıdaki harcama sayısına ne kadar güvenilebileceğini bu değerler söyler.`}
          </CardDescription>
        </div>
        <Badge tone="outline">Yalnız yönetici</Badge>
      </CardHeader>

      <CardContent className="pt-4">
        {diagnostics.isPending && (
          <div className="grid gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-3" aria-busy>
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i}>
                <Skeleton className="h-2.5 w-24" />
                <Skeleton className="mt-2.5 h-5 w-20" />
              </div>
            ))}
          </div>
        )}

        {diagnostics.isError && (
          <InlineError
            message={diagnostics.error.message}
            onRetry={() => void diagnostics.refetch()}
          />
        )}

        {diagnostics.data !== undefined && (
          <div className="flex flex-col gap-5">
            <AdminNotices data={diagnostics.data} />

            <dl className="grid gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-3">
              <Stat term="Dönem harcaması">{formatCurrencyPrecise(diagnostics.data.spent_try)}</Stat>
              <Stat term="Ayrılan (süren işler)">
                {formatCurrencyPrecise(diagnostics.data.reserved_try)}
              </Stat>
              <Stat term="Tavan">
                {diagnostics.data.limit_try === null
                  ? "Sınırsız"
                  : formatCurrencyPrecise(diagnostics.data.limit_try)}
              </Stat>
              <Stat term="LLM çağrısı">{formatNumber(diagnostics.data.calls)}</Stat>
              <Stat
                term="Tutarı hesaplanamayan"
                tone={diagnostics.data.unpriced_calls > 0 ? "warning" : "ink"}
              >
                {formatNumber(diagnostics.data.unpriced_calls)}
              </Stat>
            </dl>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

type Diagnostics = components["schemas"]["AdminUsageResponse"];

/**
 * Sayılar tek başına arızayı anlatmaz: "3" görüp ne anlama geldiğini bilmek
 * gerekir. Her uyarı üç şeyi söyler — ne oldu · sonucu ne · kim düzeltir.
 */
function AdminNotices({ data }: { data: Diagnostics }) {
  const notices: ReactNode[] = [];

  if (data.fx_rate_missing) {
    notices.push(
      <Notice key="fx-missing" tone="danger">
        Döviz kuru tanımlı değil. Her çağrı 0 TL olarak kaydediliyor, harcama toplamı sıfır
        kalıyor ve <strong className="font-medium text-ink-1">bütçe tavanı fiilen
        uygulanmıyor</strong>.{" "}
        {data.unpriced_calls > 0 &&
          `Bu dönemdeki ${formatNumber(data.unpriced_calls)} çağrının tutarı bu yüzden hesaplanamadı. `}
        Kuru sistem yöneticisi tanımlar.
      </Notice>,
    );
  } else if (data.fx_rate_stale) {
    notices.push(
      <Notice key="fx-stale" tone="warning">
        {data.fx_rate_age_days === null
          ? "Döviz kurunun güncellenme tarihi yazılmamış; ne kadar eski olduğu bilinmiyor."
          : `Döviz kuru ${formatNumber(data.fx_rate_age_days)} gündür güncellenmedi.`}{" "}
        Harcama tutarları güncel kurdan sapabilir; tavan olduğundan gevşek ya da sıkı
        davranır. Kuru sistem yöneticisi günceller.
      </Notice>,
    );
  }

  // Kur eksikken bu uyarı YAZILMAZ: fiyatlandırılamayan çağrılar o durumda
  // bağımsız bir arıza değil, kur eksikliğinin SONUCUDUR. İkisini yan yana iki
  // kırmızı/sarı blok olarak göstermek, tek bir sebebi iki sorun gibi okutur ve
  // yöneticiyi olmayan ikinci bir işin peşine düşürür.
  if (data.unpriced_calls > 0 && !data.fx_rate_missing) {
    notices.push(
      <Notice key="unpriced" tone="warning">
        {formatNumber(data.unpriced_calls)} çağrının tutarı hesaplanamadı (bilinmeyen model ya
        da eksik kur). Bu çağrılar harcama toplamına girmiyor —{" "}
        <strong className="font-medium text-ink-1">tavan olduğundan gevşek davranıyor</strong>{" "}
        ve kalan bütçe gerçekte olduğundan büyük görünüyor.
      </Notice>,
    );
  }

  if (data.unverified_models.length > 0) {
    notices.push(
      <Notice key="unverified" tone="info">
        Fiyatı sağlayıcıya karşı doğrulanmamış model kullanılıyor:{" "}
        <span className="font-mono text-ink-1">{data.unverified_models.join(", ")}</span>. Bu
        çağrılar harcamaya girer ama tutarları tahminidir.
      </Notice>,
    );
  }

  if (notices.length === 0) return null;
  return <div className="flex flex-col gap-3">{notices}</div>;
}

const STAT_TONE = {
  ink: "text-ink-1",
  warning: "text-warning",
} as const;

function Stat({
  term,
  tone = "ink",
  children,
}: {
  term: string;
  tone?: keyof typeof STAT_TONE;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-overline text-ink-3">{term}</dt>
      <dd className={cn("mt-1.5 font-mono text-base tabular-nums", STAT_TONE[tone])}>{children}</dd>
    </div>
  );
}
