"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shell/page-header";
import { StatusPill, type StatusTone } from "@/components/status-pill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_META: Record<string, { label: string; tone: StatusTone }> = {
  active: { label: "Etkin", tone: "success" },
  trialing: { label: "Deneme", tone: "info" },
  past_due: { label: "Ödeme bekliyor", tone: "warning" },
  canceled: { label: "İptal edildi", tone: "neutral" },
};

const NUMBER_FORMAT = new Intl.NumberFormat("tr-TR");

function formatLimit(limit: number | null): string {
  return limit === null ? "Sınırsız" : NUMBER_FORMAT.format(limit);
}

function formatPrice(tier: string, priceTry: number): string {
  if (tier === "enterprise") return "Özel fiyat";
  if (priceTry === 0) return "Ücretsiz";
  return `${NUMBER_FORMAT.format(priceTry)} ₺ / ay`;
}

function UsageMeter({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number | null;
}) {
  const pct = limit === null || limit === 0 ? 0 : Math.min(100, Math.round((used / limit) * 100));
  const nearLimit = limit !== null && pct >= 80;
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium text-ink-2">{label}</span>
        <span className="font-mono text-ink-1">
          {NUMBER_FORMAT.format(used)}
          <span className="text-ink-3"> / {formatLimit(limit)}</span>
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-2">
        {limit !== null && (
          <div
            className={cn(
              "h-full rounded-full transition-all",
              nearLimit ? "bg-warning" : "bg-brand",
            )}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  );
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
      if (error !== undefined) throw new Error("Plan değiştirilemedi.");
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
  const status = usage.data ? STATUS_META[usage.data.status] : undefined;

  return (
    <>
      <PageHeader
        title="Kullanım ve abonelik"
        context="Bu dönemki kota kullanımınızı görüntüleyin ve planınızı yönetin."
      />

      <Card className="mb-8">
        <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
          <CardTitle className="text-base">
            {usage.isPending ? "…" : (usage.data?.plan_name ?? "Plan")}
          </CardTitle>
          {status && <StatusPill tone={status.tone} label={status.label} />}
        </CardHeader>
        <CardContent className="space-y-5">
          {usage.isPending && (
            <>
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </>
          )}
          {usage.isError && <p className="text-sm text-danger">{usage.error.message}</p>}
          {usage.data && (
            <>
              <UsageMeter
                label="Doküman"
                used={usage.data.documents.used}
                limit={usage.data.documents.limit}
              />
              <UsageMeter
                label="Sayfa"
                used={usage.data.pages.used}
                limit={usage.data.pages.limit}
              />
              <p className="text-xs text-ink-3">
                Kota her takvim ayının başında sıfırlanır. Dönem:{" "}
                {new Date(usage.data.period_start).toLocaleDateString("tr-TR")} –{" "}
                {new Date(usage.data.period_end).toLocaleDateString("tr-TR")}
              </p>
            </>
          )}
        </CardContent>
      </Card>

      <h2 className="mb-3 text-sm font-semibold text-ink-1">Planlar</h2>
      {plans.isPending && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      )}
      {plans.isError && <p className="text-sm text-danger">{plans.error.message}</p>}
      {plans.data && (
        <div className="grid gap-4 sm:grid-cols-3">
          {plans.data.map((plan) => (
            <Card
              key={plan.tier}
              className={cn(plan.is_current && "rail-active border-brand/40 bg-brand-weak/30")}
            >
              <CardHeader className="space-y-1">
                <CardTitle className="text-base">{plan.display_name}</CardTitle>
                <p className="text-lg font-semibold text-ink-1">
                  {formatPrice(plan.tier, plan.monthly_price_try)}
                </p>
              </CardHeader>
              <CardContent className="space-y-3">
                <ul className="space-y-1.5 text-sm text-ink-2">
                  <li className="flex items-center gap-2">
                    <Check className="size-4 text-success" strokeWidth={2} />
                    {formatLimit(plan.documents_per_month)} doküman / ay
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="size-4 text-success" strokeWidth={2} />
                    {formatLimit(plan.pages_per_month)} sayfa / ay
                  </li>
                </ul>
                {plan.is_current ? (
                  <Button variant="outline" className="w-full" disabled>
                    Mevcut planınız
                  </Button>
                ) : plan.tier === "enterprise" ? (
                  <Button variant="outline" className="w-full" asChild>
                    <a href="mailto:satis@tenderiq.local?subject=Kurumsal%20plan">
                      Satışla iletişime geçin
                    </a>
                  </Button>
                ) : isAdmin ? (
                  <Button
                    className="w-full"
                    disabled={checkout.isPending}
                    onClick={() => checkout.mutate(plan.tier)}
                  >
                    {checkout.isPending ? "İşleniyor…" : "Bu plana geç"}
                  </Button>
                ) : (
                  <p className="text-center text-xs text-ink-3">
                    Plan değişikliği için yönetici gerekir.
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
