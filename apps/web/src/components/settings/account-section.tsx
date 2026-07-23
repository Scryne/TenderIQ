"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BadgeCheck, Building2, Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { StatusPill } from "@/components/status-pill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const ROLE_LABELS: Record<string, string> = {
  admin: "Yönetici",
  member: "Üye",
  viewer: "İzleyici",
};

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
      toast.success("Organizasyon değiştirildi.");
      router.refresh();
    } catch {
      toast.error("Organizasyon değiştirilemedi.");
    } finally {
      setSwitchingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Hesap</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {me.isPending && <Skeleton className="h-10 w-64" />}
          {me.data && (
            <>
              <div className="flex items-center gap-2.5 text-sm">
                <Mail className="size-4 text-ink-3" strokeWidth={1.5} />
                <span className="font-medium text-ink-1">{me.data.email}</span>
                {me.data.email_verified ? (
                  <StatusPill tone="success" label="Doğrulandı" />
                ) : (
                  <StatusPill tone="warning" label="Doğrulanmadı" />
                )}
              </div>
              {!me.data.email_verified && (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warning/30 bg-warning-weak/40 px-4 py-3">
                  <p className="text-sm text-ink-2">
                    E-posta adresinizi doğrulayın; güvenlik bildirimleri buraya gönderilir.
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={resend.isPending}
                    onClick={() => resend.mutate()}
                  >
                    <BadgeCheck className="size-4" strokeWidth={1.5} />
                    {resend.isPending ? "Gönderiliyor…" : "Doğrulama bağlantısı gönder"}
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Organizasyonlarım</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {memberships.isPending && <Skeleton className="h-12 w-full" />}
          {memberships.isError && (
            <p className="text-sm text-danger">{memberships.error.message}</p>
          )}
          {memberships.data?.map((membership) => (
            <div
              key={membership.organization_id}
              className={cn(
                "flex items-center gap-3 rounded-lg border px-4 py-3",
                membership.is_active ? "rail-active border-brand/40 bg-brand-weak/30" : "bg-surface",
              )}
            >
              <Building2 className="size-4 text-ink-3" strokeWidth={1.5} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink-1">
                  {membership.organization_name}
                </p>
                <p className="text-xs text-ink-3">{ROLE_LABELS[membership.role] ?? membership.role}</p>
              </div>
              {membership.is_active ? (
                <StatusPill tone="info" label="Aktif" />
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={switchingId !== null}
                  onClick={() => void switchOrg(membership.organization_id)}
                >
                  {switchingId === membership.organization_id ? "Geçiliyor…" : "Bu org'a geç"}
                </Button>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
