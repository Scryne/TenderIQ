"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthNotice } from "@/components/auth/auth-layout";
import { InlineError } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/tenders";

function AcceptInvitation() {
  const router = useRouter();
  const token = useSearchParams().get("token");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");

  const preview = useQuery({
    queryKey: ["invitation-lookup", token],
    enabled: token !== null,
    retry: false,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/invitations/lookup", {
        params: { query: { token: token as string } },
      });
      if (error !== undefined) throw new Error("Davet geçersiz veya süresi dolmuş.");
      return data;
    },
  });

  const accountExists = preview.data?.account_exists ?? false;

  const accept = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/session/accept-invitation", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          token,
          full_name: accountExists ? undefined : fullName || undefined,
          password: accountExists ? undefined : password,
        }),
      });
      if (!response.ok) throw new Error("Davet kabul edilemedi. Bağlantı geçersiz olabilir.");
      return (await response.json()) as { account_created: boolean };
    },
    onSuccess: (result) => {
      if (result.account_created) {
        router.push("/panel");
        router.refresh();
      } else {
        // Mevcut kullanıcı: otomatik giriş yok — üyelik eklendi, normal giriş yapmalı.
        router.push("/login");
      }
    },
  });

  if (token === null || preview.isError) {
    return (
      <AuthNotice title="Davet bağlantısı geçersiz">
        <p>
          Bağlantının süresi dolmuş ya da daha önce kullanılmış olabilir. Sizi davet eden
          yöneticiden yeni bir davet isteyin.
        </p>
        <Button asChild variant="secondary" className="w-full">
          <Link href="/login">Girişe dön</Link>
        </Button>
      </AuthNotice>
    );
  }

  if (preview.isPending) {
    return (
      <AuthNotice title="Organizasyona katıl">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-9 w-full" />
      </AuthNotice>
    );
  }

  return (
    <AuthNotice title="Organizasyona katıl">
      <div className="flex items-start gap-3 rounded-sm border border-border bg-surface-2 p-3.5">
        <span className="grid size-8 shrink-0 place-items-center rounded-md bg-surface">
          <Building2 aria-hidden className="size-4 text-ink-2" strokeWidth={1.75} />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink-1">{preview.data.organization_name}</p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-3">
            <Badge tone="neutral">{ROLE_LABELS[preview.data.role] ?? preview.data.role}</Badge>
            <span className="truncate">{preview.data.email}</span>
          </p>
        </div>
      </div>

      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          accept.mutate();
        }}
      >
        {accept.isError && <InlineError message={accept.error.message} />}

        {accountExists ? (
          <p>
            Bu e-posta zaten bir hesaba bağlı. Daveti kabul edin; ardından mevcut parolanızla
            giriş yapabilirsiniz.
          </p>
        ) : (
          <>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="full-name">Ad soyad</Label>
              <Input
                id="full-name"
                autoFocus
                autoComplete="name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Ayşe Kaya"
                aria-describedby="full-name-help"
              />
              <p id="full-name-help" className="text-xs text-ink-3">
                İsteğe bağlı — yorumlarda ve inceleme geçmişinde bu ad görünür.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">
                Parola belirle <span className="text-danger">*</span>
              </Label>
              <Input
                id="password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-describedby="password-help"
              />
              <p id="password-help" className="text-xs text-ink-3">
                En az 8 karakter olmalı.
              </p>
            </div>
          </>
        )}

        <Button type="submit" className="w-full" loading={accept.isPending}>
          Daveti kabul et
        </Button>
      </form>
    </AuthNotice>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense>
      <AcceptInvitation />
    </Suspense>
  );
}
