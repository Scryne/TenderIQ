"use client";

import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "@/components/shell/page-header";
import { AccountSection } from "@/components/settings/account-section";
import { InvitationsSection } from "@/components/settings/invitations-section";
import { MembersSection } from "@/components/settings/members-section";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

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
    <>
      <PageHeader
        title="Ayarlar"
        context="Hesabınızı, organizasyon üyelerini ve davetleri yönetin."
      />

      {me.isPending && <Skeleton className="h-40 w-full" />}
      {me.data && (
        <div className="space-y-8">
          <AccountSection />
          <MembersSection isAdmin={isAdmin} currentUserId={me.data.id} />
          {isAdmin && <InvitationsSection />}
        </div>
      )}
    </>
  );
}
