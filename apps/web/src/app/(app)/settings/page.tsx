"use client";

import { useQuery } from "@tanstack/react-query";
import { MailPlus, ShieldCheck, UserCog, Users } from "lucide-react";

import { AccountSection } from "@/components/settings/account-section";
import { DataRightsSection } from "@/components/settings/data-rights-section";
import { InvitationsSection } from "@/components/settings/invitations-section";
import { MembersSection } from "@/components/settings/members-section";
import { PageHeader } from "@/components/shell/page-header";
import { ForbiddenState } from "@/components/states";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";

/**
 * Ayarlar — DESIGN.md §9.7.
 *
 * Sol dikey sekme navigasyonu (200px) + sağ içerik. Kaydetme modeli sayfa
 * genelinde TEK: her ayar grubu kendi kartında, kart içinde kaydeder. Anında
 * kaydeden toggle ile kart altı kaydet butonu karıştırılmaz.
 */
export default function SettingsPage() {
  const me = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/auth/me");
      if (error !== undefined) throw new Error("Oturum bilgisi alınamadı.");
      return data;
    },
  });

  const isAdmin = me.data?.role === "admin";

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Ayarlar"
        description="Hesabınızı, çalışma alanı üyelerini ve davetleri yönetin."
      />

      {me.isPending && (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-9 w-64" />
          <Skeleton className="h-48 w-full" />
        </div>
      )}

      {me.data !== undefined && (
        <Tabs defaultValue="account" className="gap-6 lg:flex-row">
          <TabsList
            variant="vertical"
            className="shrink-0 lg:sticky lg:top-20 lg:w-[200px] lg:self-start"
          >
            <TabsTrigger value="account">
              <UserCog strokeWidth={1.75} />
              Hesap
            </TabsTrigger>
            <TabsTrigger value="members">
              <Users strokeWidth={1.75} />
              Üyeler
            </TabsTrigger>
            {isAdmin && (
              <TabsTrigger value="invitations">
                <MailPlus strokeWidth={1.75} />
                Davetler
              </TabsTrigger>
            )}
            <TabsTrigger value="data">
              <ShieldCheck strokeWidth={1.75} />
              Verilerim
            </TabsTrigger>
          </TabsList>

          <div className="min-w-0 flex-1">
            <TabsContent value="account">
              <AccountSection />
            </TabsContent>
            <TabsContent value="members">
              <MembersSection isAdmin={isAdmin} currentUserId={me.data.id} />
            </TabsContent>
            <TabsContent value="data">
              <DataRightsSection isAdmin={isAdmin} />
            </TabsContent>
            <TabsContent value="invitations">
              {isAdmin ? (
                <InvitationsSection />
              ) : (
                <ForbiddenState description="Davet gönderme yönetici yetkisi gerektirir. Çalışma alanı yöneticinizden isteyin." />
              )}
            </TabsContent>
          </div>
        </Tabs>
      )}
    </div>
  );
}
