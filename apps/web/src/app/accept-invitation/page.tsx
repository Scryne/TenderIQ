"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

const ROLE_LABEL: Record<string, string> = {
  admin: "Yönetici",
  member: "Üye",
  viewer: "İzleyici",
};

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

  const accept = useMutation({
    mutationFn: async () => {
      const accountExists = preview.data?.account_exists ?? false;
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
        router.push("/tenders");
        router.refresh();
      } else {
        // Mevcut kullanıcı: otomatik giriş yok — üyelik eklendi, normal giriş yapmalı.
        router.push("/login");
      }
    },
  });

  const accountExists = preview.data?.account_exists ?? false;

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-6 p-8">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Organizasyona katıl</CardTitle>
          <CardDescription>
            {preview.isPending && token !== null && "Davet yükleniyor…"}
            {(token === null || preview.isError) &&
              "Davet bağlantısı geçersiz veya süresi dolmuş."}
            {preview.data && (
              <>
                <span className="font-medium text-ink-1">{preview.data.organization_name}</span>{" "}
                organizasyonuna{" "}
                <span className="font-medium text-ink-1">
                  {ROLE_LABEL[preview.data.role] ?? preview.data.role}
                </span>{" "}
                olarak davet edildiniz ({preview.data.email}).
              </>
            )}
          </CardDescription>
        </CardHeader>

        {preview.isPending && token !== null && (
          <CardContent>
            <Skeleton className="h-10 w-full" />
          </CardContent>
        )}

        {preview.data && (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              accept.mutate();
            }}
          >
            <CardContent className="space-y-4">
              {!accountExists && (
                <>
                  <div className="space-y-1.5">
                    <Label htmlFor="full-name">Ad soyad (isteğe bağlı)</Label>
                    <Input
                      id="full-name"
                      value={fullName}
                      onChange={(event) => setFullName(event.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="password">Parola belirle</Label>
                    <Input
                      id="password"
                      type="password"
                      required
                      minLength={8}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                    />
                    <p className="text-xs text-ink-3">En az 8 karakter.</p>
                  </div>
                </>
              )}
              {accountExists && (
                <p className="text-sm text-ink-2">
                  Bu e-posta zaten bir hesaba bağlı. Daveti kabul edip ardından giriş yapın.
                </p>
              )}
              {accept.isError && <p className="text-sm text-danger">{accept.error.message}</p>}
            </CardContent>
            <CardFooter className="flex-col items-stretch gap-3">
              <Button type="submit" disabled={accept.isPending}>
                {accept.isPending ? "Katılınıyor…" : "Daveti kabul et"}
              </Button>
            </CardFooter>
          </form>
        )}

        {(token === null || preview.isError) && (
          <CardContent>
            <Button asChild variant="outline" className="w-full">
              <Link href="/login">Girişe dön</Link>
            </Button>
          </CardContent>
        )}
      </Card>
    </main>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense>
      <AcceptInvitation />
    </Suspense>
  );
}
