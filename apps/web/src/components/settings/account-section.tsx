"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BadgeCheck, Building2, LogOut, Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { InlineError } from "@/components/states";
import { StatusPill } from "@/components/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/tenders";
import { cn } from "@/lib/utils";

export function AccountSection() {
  const router = useRouter();
  const [switchingId, setSwitchingId] = useState<string | null>(null);

  const me = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/auth/me");
      if (error !== undefined) throw new Error("Oturum bilgisi alınamadı.");
      return data;
    },
  });

  const memberships = useQuery({
    queryKey: ["memberships"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/auth/memberships");
      if (error !== undefined) throw new Error("Organizasyonlar alınamadı.");
      return data;
    },
  });

  const resend = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/v1/auth/resend-verification");
      if (error !== undefined) throw new Error("Doğrulama bağlantısı gönderilemedi.");
    },
    onSuccess: () => toast.success("Doğrulama bağlantısı e-postanıza gönderildi."),
    onError: (error: Error) => toast.error(error.message),
  });

  async function switchOrg(organizationId: string) {
    setSwitchingId(organizationId);
    try {
      const response = await fetch("/api/session/switch-org", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ organization_id: organizationId }),
      });
      if (!response.ok) throw new Error();
      toast.success("Çalışma alanı değiştirildi.");
      router.refresh();
    } catch {
      toast.error("Çalışma alanı değiştirilemedi.");
    } finally {
      setSwitchingId(null);
    }
  }

  async function logout() {
    await fetch("/api/session", { method: "DELETE" });
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="block">
          <CardTitle as="h2">Hesap</CardTitle>
          <CardDescription>
            Güvenlik bildirimleri ve davet e-postaları bu adrese gönderilir.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 pt-0">
          {me.isPending && <Skeleton className="h-9 w-72" />}
          {me.isError && <InlineError message={me.error.message} onRetry={() => void me.refetch()} />}
          {me.data !== undefined && (
            <>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <Mail aria-hidden className="size-4 text-ink-3" strokeWidth={1.75} />
                <span className="text-sm font-medium text-ink-1">{me.data.email}</span>
                {me.data.email_verified ? (
                  <StatusPill tone="success" label="Doğrulandı" />
                ) : (
                  <StatusPill tone="warning" label="Doğrulanmadı" />
                )}
                {me.data.full_name != null && me.data.full_name !== "" && (
                  <span className="text-sm text-ink-3">· {me.data.full_name}</span>
                )}
              </div>

              {!me.data.email_verified && (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-warning/30 bg-warning-weak px-4 py-3">
                  <p className="min-w-0 flex-1 text-sm text-ink-2">
                    E-posta adresiniz doğrulanmadı. Parola sıfırlama ve güvenlik bildirimleri
                    doğrulanana kadar ulaşmaz.
                  </p>
                  <Button variant="secondary" size="sm" loading={resend.isPending} onClick={() => resend.mutate()}>
                    <BadgeCheck strokeWidth={1.75} />
                    Doğrulama bağlantısı gönder
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="block">
          <CardTitle as="h2">Çalışma alanlarım</CardTitle>
          <CardDescription>
            Aynı hesapla birden fazla organizasyonda yer alabilirsiniz. Etkin alan, tüm
            ekranlardaki verileri belirler.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 pt-0">
          {memberships.isPending && <Skeleton className="h-14 w-full" />}
          {memberships.isError && (
            <InlineError
              message={memberships.error.message}
              onRetry={() => void memberships.refetch()}
            />
          )}
          {memberships.data?.map((membership) => (
            <div
              key={membership.organization_id}
              className={cn(
                "flex flex-wrap items-center gap-3 rounded-sm border px-4 py-3",
                membership.is_active
                  ? "border-accent bg-surface-2"
                  : "border-border bg-surface",
              )}
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-md bg-surface-2">
                <Building2 aria-hidden className="size-4 text-ink-2" strokeWidth={1.75} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink-1">
                  {membership.organization_name}
                </p>
                <p className="mt-0.5 truncate font-mono text-[11px] text-ink-3">
                  {membership.organization_slug}
                </p>
              </div>
              <Badge tone="neutral">{ROLE_LABELS[membership.role] ?? membership.role}</Badge>
              {membership.is_active ? (
                <Badge tone="ink">Etkin</Badge>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={switchingId === membership.organization_id}
                  disabled={switchingId !== null}
                  onClick={() => void switchOrg(membership.organization_id)}
                >
                  Bu alana geç
                </Button>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* §9.7 tehlikeli bölge. Bu üründe hesap silme / tüm oturumları kapatma
          ucu YOK; var olmayan bir eylem için kart uydurmak yerine yalnız gerçek
          eylem (oturumu kapatma) burada, danger kenarlığıyla verilir. */}
      <Card className="border-danger/30">
        <CardHeader className="block">
          <CardTitle as="h2">Oturum</CardTitle>
          <CardDescription>
            Ortak kullanılan bir bilgisayardaysanız işiniz bittiğinde oturumu kapatın.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <Button variant="danger-ghost" onClick={() => void logout()}>
            <LogOut strokeWidth={1.75} />
            Oturumu kapat
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
