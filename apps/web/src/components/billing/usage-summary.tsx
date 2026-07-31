"use client";

/**
 * `/usage` — dönem kullanımı ve depolama (J.6 görünürlüğü, Tur 17).
 *
 * **Bu ekranın taşıdığı tek soru:** "beni önce ne durduracak, ve ne zaman
 * sıfırlanacak?" Jenerik bir kullanım ekranı dört ölçeri (doküman · sayfa ·
 * bütçe · depolama) eşit ağırlıkta yan yana dizerdi. Bu üründe bu YANLIŞ
 * olurdu: doküman ve sayfa kotaları **bütçeden türetiliyor** (plans.py) ve
 * bütçe her zaman önce doluyor — kota bir TAVAN, bütçe BAĞLAYICI kısıt. Bu
 * yüzden bütçe ölçeri hero konumunda ve tek başına, kotalar onun altında
 * ikincil satırlar olarak duruyor.
 *
 * **Depolama ayrı karttadır** ve bu bilinçli: dönemsel değil kümülatiftir.
 * "Bu dönem" başlığı altına koymak, ay başında sıfırlanacağını ima ederdi —
 * oysa yalnız dosya silinince azalır.
 */

import { useQuery } from "@tanstack/react-query";
import { Gauge } from "lucide-react";
import Link from "next/link";

import { BudgetMeter, Meter } from "@/components/metric";
import { Notice } from "@/components/notice";
import { EmptyState, InlineError } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import {
  formatBytes,
  formatCurrencyPrecise,
  formatDate,
  formatNumber,
  splitCurrency,
} from "@/lib/format";

/** Planlar bölümünün çapası — bütçe dolduğunda çıkış yolu oraya gider. */
export const PLANS_ANCHOR = "planlar";

function formatLimitBytes(limit: number | null): string {
  return limit === null ? "sınırsız" : formatBytes(limit);
}

function formatLimitCount(limit: number | null): string {
  return limit === null ? "sınırsız" : formatNumber(limit);
}

export function UsageSummary({ isAdmin }: { isAdmin: boolean }) {
  const usage = useQuery({
    queryKey: ["usage"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/usage");
      if (error !== undefined) throw new Error("Kullanım bilgisi alınamadı.");
      return data;
    },
  });

  if (usage.isPending) return <UsageSummarySkeleton />;

  if (usage.isError) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <CardTitle as="h2">Bu dönem</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <InlineError message={usage.error.message} onRetry={() => void usage.refetch()} />
        </CardContent>
      </Card>
    );
  }

  const { budget, storage, documents, pages } = usage.data;
  const periodLine = `${formatDate(usage.data.period_start)} – ${formatDate(usage.data.period_end)}`;
  const resetsOn = formatDate(usage.data.period_end);

  // Tavan dolduğunda sunucu yeni işi REDDEDER (sert tavan; küçük modele düşme
  // ya da kısmi sonuç yok). "Kalan 0" ile "az kaldı" arasındaki fark bu yüzden
  // kozmetik değil: biri durmuş bir üründür.
  const budgetFull = budget.remaining_try !== null && budget.remaining_try <= 0;
  const budgetNear = budget.soft_exceeded && !budgetFull;
  const budgetTone = budgetFull ? "danger" : budgetNear ? "warning" : "ink";

  // İlk kullanım: dört boyutun da sıfır olduğu hâl. Dört boş çubuk çizmek
  // hiçbir soruyu yanıtlamaz; §10.1 gereği boş durum bir davettir.
  const firstUse =
    budget.spent_try === 0 &&
    budget.reserved_try === 0 &&
    documents.used === 0 &&
    pages.used === 0 &&
    storage.used_bytes === 0;

  if (firstUse) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <div className="min-w-0">
            <CardTitle as="h2">Bu dönem</CardTitle>
            <CardDescription>{periodLine}</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <EmptyState
            compact
            icon={Gauge}
            title="Bu dönemde henüz analiz yapılmadı"
            description={`${usage.data.plan_name} planınızda bu dönem ${formatLimitCount(documents.limit)} doküman ve ${formatLimitCount(pages.limit)} sayfa hakkınız var; analiz bütçesi ${budget.limit_try === null ? "sınırsız" : formatCurrencyPrecise(budget.limit_try)}. Hakkınız ${resetsOn} tarihinde yenilenir.`}
            action={
              <Button asChild>
                <Link href="/tenders">İhalelere git</Link>
              </Button>
            }
          />
          <p className="mt-4 text-xs text-ink-3">
            Depolama kotası {formatLimitBytes(storage.limit_bytes)}; dönem sonunda sıfırlanmaz.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card className="mb-6">
        <CardHeader>
          <div className="min-w-0">
            <CardTitle as="h2">Bu dönem</CardTitle>
            {/* "01.07.2026 – 01.08.2026 · 01.08.2026 tarihinde sıfırlanır"
                aynı tarihi iki kez yazıyordu. Ek uyumu riskine girmemek için
                de tarihe ek getirilmiyor (Ek B.3): "bitiminde" eksiz kalıp. */}
            <CardDescription>Dönem {periodLine} · bitiminde sıfırlanır</CardDescription>
          </div>
        </CardHeader>

        <CardContent className="flex flex-col gap-5 pt-4">
          {budgetFull && (
            <Notice
              tone="danger"
              action={
                isAdmin ? (
                  <Button size="sm" asChild>
                    <Link href={`#${PLANS_ANCHOR}`}>Planları gör</Link>
                  </Button>
                ) : undefined
              }
            >
              Bu dönemin analiz bütçesi doldu. <strong className="font-medium text-ink-1">Yeni
              analiz başlatılamıyor</strong>; süren işler tamamlanır ve mevcut bulgularınız
              erişilebilir kalır. Bütçe {resetsOn} tarihinde sıfırlanır.{" "}
              {isAdmin
                ? "Beklemek istemiyorsanız planı yükseltebilirsiniz."
                : "Daha önce devam etmek için organizasyon yöneticinizden plan yükseltmesini isteyin."}
            </Notice>
          )}

          {budgetNear && (
            <Notice tone="warning">
              Dönem bütçesinin büyük bölümü kullanıldı. Bütçe dolduğunda yeni analiz
              başlatılamaz; {resetsOn} tarihinde sıfırlanır.
            </Notice>
          )}

          <BudgetMeter
            label="ANALİZ BÜTÇESİ"
            spent={budget.spent_try}
            reserved={budget.reserved_try}
            limit={budget.limit_try}
            remaining={budget.remaining_try}
            tone={budgetTone}
            formatValue={formatCurrencyPrecise}
            splitValue={splitCurrency}
          />

          {budget.reserved_try > 0 && (
            <p className="max-w-[68ch] text-xs text-ink-3">
              Ayrılan tutar süren analizler için bekletiliyor — henüz harcanmadı. İş bitince
              serbest kalır ve yerine gerçek maliyeti yazılır.
            </p>
          )}

          <div className="flex flex-col gap-4 border-t border-border pt-5">
            {/* İki ölçerin de kendi eşik cümlesi VAR. Tur 2'de eklenen
                `showThresholdNote={false}` (aynı cümle iki kez yazılmasın)
                burada yanlış olurdu: doküman ve sayfa kotaları ayrı sebeplerle
                dolar — tek bir uzun şartname sayfa kotasını bitirip doküman
                kotasına dokunmayabilir. Cümleler ayrıştığı için tekrar yok. */}
            <Meter
              label="Doküman"
              used={documents.used}
              limit={documents.limit}
              formatValue={formatNumber}
              noteNear="Doküman kotasının %80'i kullanıldı."
              noteFull="Doküman kotası doldu. Dönem başında yenilenir; beklemek istemiyorsanız planı yükseltin."
            />
            <Meter
              label="Sayfa"
              used={pages.used}
              limit={pages.limit}
              formatValue={formatNumber}
              noteNear="Sayfa kotasının %80'i kullanıldı."
              noteFull="Sayfa kotası doldu. Tek bir uzun şartname bu kotayı tek başına bitirebilir; dönem başında yenilenir."
            />
            {/* Bu cümle olmadan ekran yalan söylüyor: kotasının üçte birini
                kullanmış bir kullanıcı "3 dokümandan 1'ini kullandım" görüp
                reddedilebilir. Kota bir üst sınır, bütçe bağlayıcı kısıt. */}
            <p className="max-w-[68ch] text-xs text-ink-3">
              Doküman ve sayfa kotası bir üst sınırdır; bir analizi fiilen durduran şey
              yukarıdaki bütçedir. Uzun bir şartname, kısa dokümanlardan çok daha fazla
              bütçe harcar.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <div className="min-w-0">
            <CardTitle as="h2">Depolama</CardTitle>
            <CardDescription>
              Dönemden bağımsızdır: ay başında sıfırlanmaz, dosya sildikçe azalır.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <Meter
            label="Kullanılan alan"
            used={storage.used_bytes}
            limit={storage.limit_bytes}
            formatValue={formatBytes}
            noteFull="Depolama alanı doldu. Yeni dosya yüklemek için eski dokümanları silin ya da planı yükseltin."
            noteNear="Depolama alanının %80'i kullanıldı."
          />
        </CardContent>
      </Card>
    </>
  );
}

/**
 * §10.3 — skeleton gerçek içeriğin ŞEKLİNİ taklit eder: hero sayı, çubuk,
 * açıklama satırı, iki ölçer. Jenerik iki kutu, yükleme bitince sayfanın
 * zıplamasına yol açardı.
 */
function UsageSummarySkeleton() {
  return (
    <>
      <Card className="mb-6" aria-busy>
        <CardHeader>
          <div className="min-w-0">
            <CardTitle as="h2">Bu dönem</CardTitle>
            <Skeleton className="mt-2 h-4 w-64" />
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-5 pt-4">
          <div>
            <Skeleton className="h-2.5 w-28" />
            <Skeleton className="mt-3 h-8 w-40" />
            <Skeleton className="mt-3 h-2 w-full rounded-full" />
            <div className="mt-3 flex gap-5">
              <Skeleton className="h-3 w-28" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
          <div className="flex flex-col gap-4 border-t border-border pt-5">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        </CardContent>
      </Card>
      <Card className="mb-6" aria-busy>
        <CardHeader>
          <CardTitle as="h2">Depolama</CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <Skeleton className="h-8 w-full" />
        </CardContent>
      </Card>
    </>
  );
}
