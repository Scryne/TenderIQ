"use client";

/**
 * Abonelik durumu ve iptal akışı — `/usage` sayfasının ikinci kartı.
 *
 * **Karanlık desen yok (bilinçli kısıt).** `/sartlar` §3 koşulsuz cayma hakkı
 * taahhüt ediyor; bir hakkın arayüzde sürtünmeyle zorlaştırılması onu fiilen
 * geri almaktır. Bu yüzden burada:
 *
 * - iptal, plana geçmekle aynı derinlikte (bir tık + bir onay);
 * - onay adımında yazı yazdırma, tutma teklifi, "gerçekten emin misiniz"
 *   suçlaması ya da gizlenmiş buton yok;
 * - onay kutusundaki birincil eylem iptalin KENDİSİ, "vazgeç" değil;
 * - iptal butonu `danger` değil: kırmızı, geri alınamaz ve yıkıcı bir işlem
 *   demektir — bu ikisi de değil (dönem sonuna kadar tek tıkla geri alınır);
 * - geri alma, iptalin gösterildiği yerin TAM YANINDA durur.
 *
 * Tarihler `formatDate` üzerinden (Ek B.1); "erişim şu tarihe kadar sürüyor"
 * ve "sıradaki tahsilat" ayrı ayrı yazılır — ikisi aynı alandan gelir ama
 * kullanıcı için farklı anlamlara sahiptir ve biri diğerinin yerine geçemez.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, RotateCcw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Notice } from "@/components/notice";
import { InlineError } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";

/** Abonelik verisini etkileyen tüm sorgular — mutasyon sonrası birlikte tazelenir. */
const AFFECTED_QUERIES = [["subscription"], ["usage"], ["billing-plans"]];

export function SubscriptionCard({ isAdmin }: { isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const subscription = useQuery({
    queryKey: ["subscription"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/billing/subscription");
      if (error !== undefined) throw new Error("Abonelik bilgisi alınamadı.");
      return data;
    },
  });

  function invalidateAll() {
    for (const queryKey of AFFECTED_QUERIES) {
      void queryClient.invalidateQueries({ queryKey });
    }
  }

  const cancel = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/billing/subscription/cancel");
      if (error !== undefined) throw new Error("Abonelik iptal edilemedi. Bir kez daha deneyin.");
      return data;
    },
    onSuccess: (result) => {
      setConfirmOpen(false);
      invalidateAll();
      // Geçmiş zaman (Ek B.2) + kullanıcının asıl merak ettiği bilgi: ne zamana kadar.
      toast.success(
        result.current_period_end === null
          ? "Abonelik iptal edildi."
          : `Abonelik iptal edildi. Erişiminiz ${formatDate(result.current_period_end)} tarihine kadar sürüyor.`,
      );
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const resume = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/billing/subscription/resume");
      if (error !== undefined) throw new Error("İptal geri alınamadı. Bir kez daha deneyin.");
      return data;
    },
    onSuccess: () => {
      invalidateAll();
      toast.success("İptal geri alındı. Aboneliğiniz devam ediyor.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const keepPlan = useMutation({
    mutationFn: async (plan: "free" | "pro" | "enterprise") => {
      const { error } = await api.POST("/api/v1/billing/checkout", { body: { plan } });
      if (error !== undefined) throw new Error("Plan değişikliği geri alınamadı.");
    },
    onSuccess: () => {
      invalidateAll();
      toast.success("Plan değişikliği geri alındı.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (subscription.isPending) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Abonelik</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 pt-0">
          <Skeleton className="h-5 w-64" />
          <Skeleton className="h-9 w-40" />
        </CardContent>
      </Card>
    );
  }

  if (subscription.isError) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Abonelik</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <InlineError
            message={subscription.error.message}
            onRetry={() => void subscription.refetch()}
          />
        </CardContent>
      </Card>
    );
  }

  const data = subscription.data;
  const canceling = data.cancel_at_period_end;
  const busy = cancel.isPending || resume.isPending || keepPlan.isPending;

  return (
    <Card className="mb-6">
      <CardHeader>
        <div className="min-w-0">
          <CardTitle>Abonelik</CardTitle>
          <CardDescription>
            {canceling
              ? "Aboneliğiniz dönem sonunda sona erecek."
              : data.next_charge_at !== null
                ? `${data.plan_name} planı, iptal edilene kadar her dönem yenilenir.`
                : "Ücretsiz plandasınız; tahsilat yapılmıyor."}
          </CardDescription>
        </div>
      </CardHeader>

      {/* `pt-0` DEĞİL: kart açıklaması bir cümle, altındakiler ise veri ve eylem.
          Sıfır üst boşlukta üçü tek bir paragraf gibi okunuyordu (§13.3 —
          hiyerarşi boşlukla anlatılır). */}
      <CardContent className="flex flex-col gap-4 pt-4">
        {/* İptal edilmiş: erişimin ne zamana kadar sürdüğü EN ÖNEMLİ bilgi. */}
        {canceling && data.current_period_end !== null && (
          <Notice tone="warning">
            <span>
              <strong className="font-medium text-ink-1">{data.plan_name}</strong> erişiminiz{" "}
              <strong className="font-medium text-ink-1">
                {formatDate(data.current_period_end)}
              </strong>{" "}
              tarihine kadar sürüyor. Bu tarihte ücretsiz plana geçilecek ve yeni tahsilat
              yapılmayacak.
            </span>
          </Notice>
        )}

        {/* Planlanmış düşürme — iptal gibi bu da geri alınabilir olmalı. */}
        {!canceling && data.pending_plan !== null && data.current_period_end !== null && (
          <Notice tone="info" icon={CalendarClock}>
            <span>
              {formatDate(data.current_period_end)} tarihinde{" "}
              <strong className="font-medium text-ink-1">{data.pending_plan_name}</strong> planına
              geçilecek. O tarihe kadar mevcut kotanız değişmez.
            </span>
          </Notice>
        )}

        {/* Yenilenen abonelikte kullanıcının sorduğu tek soru: ne zaman çekilecek. */}
        {!canceling && data.next_charge_at !== null && (
          <dl className="flex flex-wrap items-baseline gap-x-2 text-sm">
            <dt className="text-ink-2">Sıradaki tahsilat</dt>
            <dd className="font-mono tabular-nums text-ink-1">
              {formatDate(data.next_charge_at)}
            </dd>
          </dl>
        )}

        {!isAdmin && (data.can_cancel || data.can_resume) && (
          <p className="text-sm text-ink-3">
            Abonelik değişikliği yönetici yetkisi gerektirir. Organizasyon yöneticinizle görüşün.
          </p>
        )}

        {isAdmin && (
          <div className="flex flex-wrap gap-2">
            {data.can_resume && (
              <Button variant="secondary" loading={resume.isPending} onClick={() => resume.mutate()}>
                <RotateCcw aria-hidden strokeWidth={1.75} />
                İptali geri al
              </Button>
            )}

            {!canceling && data.pending_plan !== null && (
              <Button
                variant="secondary"
                loading={keepPlan.isPending}
                onClick={() => keepPlan.mutate(data.plan)}
              >
                <RotateCcw aria-hidden strokeWidth={1.75} />
                {data.plan_name} planında kal
              </Button>
            )}

            {data.can_cancel && (
              <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
                <Button variant="secondary" onClick={() => setConfirmOpen(true)} disabled={busy}>
                  Aboneliği iptal et
                </Button>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Aboneliği iptal et</DialogTitle>
                    <DialogDescription>
                      İptali dönem sonuna kadar geri alabilirsiniz.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogBody className="flex flex-col gap-3">
                    <p className="text-sm text-ink-2">
                      {data.current_period_end === null
                        ? `${data.plan_name} erişiminiz dönem sonuna kadar sürer, yeni tahsilat yapılmaz.`
                        : `${data.plan_name} erişiminiz ${formatDate(data.current_period_end)} tarihine kadar sürer. Bu tarihte ücretsiz plana geçersiniz ve yeni tahsilat yapılmaz.`}
                    </p>
                    <p className="text-sm text-ink-2">
                      İhaleleriniz, dokümanlarınız ve bulgularınız silinmez; ücretsiz plan
                      limitleri geçerli olur.
                    </p>
                    {cancel.isError && <InlineError message={cancel.error.message} />}
                  </DialogBody>
                  <DialogFooter>
                    <DialogClose asChild>
                      <Button variant="secondary" disabled={cancel.isPending}>
                        Vazgeç
                      </Button>
                    </DialogClose>
                    <Button loading={cancel.isPending} onClick={() => cancel.mutate()}>
                      Aboneliği iptal et
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
