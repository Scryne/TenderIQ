"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthLayout } from "@/components/auth/auth-layout";
import { InlineError } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";

function ResetPassword() {
  const router = useRouter();
  const token = useSearchParams().get("token");
  const [password, setPassword] = useState("");

  const submit = useMutation({
    mutationFn: async () => {
      if (token === null) throw new Error("Sıfırlama bağlantısı eksik. E-postadaki bağlantıyı kullanın.");
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

  if (submit.isSuccess) {
    return (
      <AuthLayout title="Parolanız güncellendi">
        <div className="flex items-start gap-3 rounded-lg border border-border bg-surface p-4">
          <CheckCircle2
            aria-hidden
            className="mt-0.5 size-4 shrink-0 text-success"
            strokeWidth={1.75}
          />
          <p className="text-sm text-ink-2">Giriş sayfasına yönlendiriliyorsunuz…</p>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Yeni parola belirle" description="Hesabınız için yeni bir parola girin.">
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          submit.mutate();
        }}
      >
        {submit.isError && <InlineError message={submit.error.message} />}
        {token === null && !submit.isError && (
          <InlineError message="Sıfırlama bağlantısı eksik. E-postadaki bağlantıyı kullanın." />
        )}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password">
            Yeni parola <span className="text-danger">*</span>
          </Label>
          <Input
            id="password"
            type="password"
            required
            minLength={8}
            autoFocus
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-describedby="password-help"
            aria-invalid={submit.isError || undefined}
          />
          <p id="password-help" className="text-xs text-ink-3">
            En az 8 karakter olmalı.
          </p>
        </div>

        <Button
          type="submit"
          className="mt-1 w-full"
          loading={submit.isPending}
          disabled={token === null}
        >
          Parolayı güncelle
        </Button>
        <Button asChild variant="ghost" className="w-full">
          <Link href="/login">Girişe dön</Link>
        </Button>
      </form>
    </AuthLayout>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPassword />
    </Suspense>
  );
}
