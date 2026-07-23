"use client";

import { useMutation } from "@tanstack/react-query";
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
import { api } from "@/lib/api";

function ResetPassword() {
  const router = useRouter();
  const token = useSearchParams().get("token");
  const [password, setPassword] = useState("");

  const submit = useMutation({
    mutationFn: async () => {
      if (token === null) throw new Error("Geçersiz sıfırlama bağlantısı.");
      const { error } = await api.POST("/api/v1/auth/reset-password", {
        body: { token, new_password: password },
      });
      if (error !== undefined) {
        throw new Error("Bağlantı geçersiz veya süresi dolmuş. Yeni bir bağlantı isteyin.");
      }
    },
    onSuccess: () => {
      setTimeout(() => router.push("/login"), 1500);
    },
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-6 p-8">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Yeni parola belirle</CardTitle>
          <CardDescription>Hesabınız için yeni bir parola girin.</CardDescription>
        </CardHeader>
        {submit.isSuccess ? (
          <CardContent>
            <p className="text-sm text-ink-2">
              Parolanız güncellendi. Giriş sayfasına yönlendiriliyorsunuz…
            </p>
          </CardContent>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              submit.mutate();
            }}
          >
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="password">Yeni parola</Label>
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
              {submit.isError && <p className="text-sm text-danger">{submit.error.message}</p>}
            </CardContent>
            <CardFooter className="flex-col items-stretch gap-3">
              <Button type="submit" disabled={submit.isPending || token === null}>
                {submit.isPending ? "Kaydediliyor…" : "Parolayı güncelle"}
              </Button>
              <Link
                href="/login"
                className="text-center text-sm text-muted-foreground hover:underline"
              >
                Girişe dön
              </Link>
            </CardFooter>
          </form>
        )}
      </Card>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPassword />
    </Suspense>
  );
}
