"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { toast } from "sonner";

import { Meter } from "@/components/metric";
import { PageHeader, SectionHeader } from "@/components/shell/page-header";
import { CardGridSkeleton, ErrorState, InlineError } from "@/components/states";
import { StatusPill } from "@/components/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatCurrency, formatDate, formatNumber } from "@/lib/format";
import { SUBSCRIPTION_STATUS } from "@/lib/tenders";
import { cn } from "@/lib/utils";

function formatLimit(limit: number | null): string {
  return limit === null ? "Sınırsız" : formatNumber(limit);
}

function formatPrice(tier: string, priceTry: number): string {
  if (tier === "enterprise") return "Özel fiyat";
  if (priceTry === 0) return "Ücretsiz";
  return formatCurrency(priceTry);
}

export default function UsagePage() {
  const queryClient = useQueryClient();

  const me = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/auth/me");
      if (error !== undefined) throw new Error("Oturum bilgisi alınamadı.");
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

  const plans = useQuery({
    queryKey: ["billing-plans"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/billing/plans");
      if (error !== undefined) throw new Error("Planlar alınamadı.");
      return data;
    },
  });

  const checkout = useMutation({
    mutationFn: async (plan: "free" | "pro" | "enterprise") => {
      const { data, error } = await api.POST("/api/v1/billing/checkout", { body: { plan } });
      if (error !== undefined) throw new Error("Plan değiştirilemedi. Bir kez daha deneyin.");
      return data;
    },
    onSuccess: (result) => {
      if (result.checkout_url != null) {
        window.location.href = result.checkout_url;
        return;
      }
      toast.success("Plan güncellendi.");
      void queryClient.invalidateQueries({ queryKey: ["usage"] });
      void queryClient.invalidateQueries({ queryKey: ["billing-plans"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const isAdmin = me.data?.role === "admin";
  const status = usage.data === undefined ? undefined : SUBSCRIPTION_STATUS[usage.data.status];

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Kullanım ve abonelik"
        description="Bu dönemki kota kullanımınızı görün ve planınızı yönetin."
        meta={status !== undefined && <StatusPill tone={status.tone} label={status.label} />}
      />

      <Card className="mb-8">
        <CardHeader>
          <div className="min-w-0">
            <CardTitle>{usage.isPending ? "…" : (usage.data?.plan_name ?? "Plan")}</CardTitle>
            {usage.data !== undefined && (
              <p className="mt-1 text-sm text-ink-2">
                Dönem {formatDate(usage.data.period_start)} – {formatDate(usage.data.period_end)} ·
                kota her ayın başında sıfırlanır
              </p>
            )}
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-6 pt-0">
          {usage.isPending && (
            <>
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </>
          )}
          {usage.isError && (
            <InlineError message={usage.error.message} onRetry={() => void usage.refetch()} />
          )}
          {usage.data !== undefined && (
            <>
              <Meter
                label="Doküman"
                used={usage.data.documents.used}
                limit={usage.data.documents.limit}
                formatValue={formatNumber}
              />
              <Meter
                label="Sayfa"
                used={usage.data.pages.used}
                limit={usage.data.pages.limit}
                formatValue={formatNumber}
              />
            </>
          )}
        </CardContent>
      </Card>

      <SectionHeader
        title="Planlar"
        description={
          isAdmin
            ? "Plan değişikliği anında geçerli olur; kota yeni limite göre yeniden hesaplanır."
            : "Plan değişikliği için organizasyon yöneticisiyle görüşün."
        }
      />

      {plans.isPending && <CardGridSkeleton count={3} height={260} />}
      {plans.isError && (
        <ErrorState
          title="Planlar alınamadı"
          description={plans.error.message}
          onRetry={() => void plans.refetch()}
          compact
        />
      )}

      {plans.data !== undefined && (
        <div className="grid items-stretch gap-4 sm:grid-cols-3">
          {plans.data.map((plan) => (
            <Card
              key={plan.tier}
              className={cn(
                "justify-between",
                plan.is_current && "border-accent ring-1 ring-accent",
              )}
            >
              <div>
                <CardHeader className="block">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>{plan.display_name}</CardTitle>
                    {plan.is_current && <Badge tone="ink">Mevcut</Badge>}
                  </div>
                  <p className="mt-3 flex items-baseline gap-1.5">
                    <span className="font-display text-2xl font-semibold text-ink-1">
                      {formatPrice(plan.tier, plan.monthly_price_try)}
                    </span>
                    {plan.tier !== "enterprise" && plan.monthly_price_try > 0 && (
                      <span className="text-sm text-ink-3">/ ay</span>
                    )}
                  </p>
                </CardHeader>
                <CardContent className="pt-4">
                  <ul className="flex flex-col gap-2.5 text-sm text-ink-2">
                    <li className="flex items-start gap-2">
                      <Check
                        aria-hidden
                        className="mt-0.5 size-4 shrink-0 text-success"
                        strokeWidth={2.25}
                      />
                      <span>
                        <span className="font-mono text-ink-1">
                          {formatLimit(plan.documents_per_month)}
                        </span>{" "}
                        doküman / ay
                      </span>
                    </li>
                    <li className="flex items-start gap-2">
                      <Check
                        aria-hidden
                        className="mt-0.5 size-4 shrink-0 text-success"
                        strokeWidth={2.25}
                      />
                      <span>
                        <span className="font-mono text-ink-1">
                          {formatLimit(plan.pages_per_month)}
                        </span>{" "}
                        sayfa / ay
                      </span>
                    </li>
                    <li className="flex items-start gap-2">
                      <Check
                        aria-hidden
                        className="mt-0.5 size-4 shrink-0 text-success"
                        strokeWidth={2.25}
                      />
                      <span>Kaynağa bağlı bulgular · Word ve Excel çıktısı</span>
                    </li>
                  </ul>
                </CardContent>
              </div>
              <CardContent className="pt-0">
                {plan.is_current ? (
                  <Button variant="secondary" className="w-full" disabled>
                    Mevcut planınız
                  </Button>
                ) : plan.tier === "enterprise" ? (
                  <Button variant="secondary" className="w-full" asChild>
                    <a href="mailto:satis@tenderiq.local?subject=Kurumsal%20plan">
                      Satışla görüşün
                    </a>
                  </Button>
                ) : isAdmin ? (
                  <Button
                    variant="secondary"
                    className="w-full"
                    loading={checkout.isPending}
                    onClick={() => checkout.mutate(plan.tier)}
                  >
                    Bu plana geç
                  </Button>
                ) : (
                  <p className="text-center text-xs text-ink-3">
                    Plan değişikliği yönetici yetkisi gerektirir
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
