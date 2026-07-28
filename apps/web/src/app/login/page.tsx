"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthLayout } from "@/components/auth/auth-layout";
import { InlineError } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const login = useMutation({
    mutationFn: async () => {
      // Token httpOnly cookie'ye sunucu tarafında yazılır; JS token görmez.
      const response = await fetch("/api/session", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        if (response.status === 429) {
          throw new Error(
            "Çok fazla deneme yapıldı. Birkaç dakika bekleyip yeniden deneyin.",
          );
        }
        if (response.status === 401) {
          throw new Error("E-posta veya parola hatalı.");
        }
        throw new Error("Giriş yapılamadı. Biraz sonra yeniden deneyin.");
      }
    },
    onSuccess: () => {
      const next = searchParams.get("next");
      // Yalnızca site-içi yollar: "//evil.com" gibi protokol-göreli URL'ler dışarı kaçırır.
      const isInternal = next !== null && next.startsWith("/") && !next.startsWith("//");
      router.push(isInternal ? next : "/panel");
      router.refresh();
    },
  });

  return (
    <AuthLayout
      title="Giriş yap"
      description="TenderIQ hesabınızla oturum açın."
      footer={
        <span>
          Hesabınız yok mu?{" "}
          <Link
            href="/register"
            className="text-ink-2 underline decoration-border-strong underline-offset-4 hover:decoration-ink-1"
          >
            Ücretsiz hesap oluşturun
          </Link>
          .
        </span>
      }
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          login.mutate();
        }}
      >
        {/* Hata form ÜSTÜNDE tek blok, alan altında değil (§9.6). */}
        {login.isError && <InlineError message={login.error.message} />}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">E-posta</Label>
          <Input
            id="email"
            type="email"
            required
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="ad.soyad@firma.com.tr"
            aria-invalid={login.isError || undefined}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <Label htmlFor="password">Parola</Label>
            <Link
              href="/forgot-password"
              className="text-xs text-ink-3 underline decoration-border-strong underline-offset-4 hover:text-ink-1 hover:decoration-ink-1"
            >
              Parolamı unuttum
            </Link>
          </div>
          <Input
            id="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-invalid={login.isError || undefined}
          />
        </div>

        <Button type="submit" className="mt-1 w-full" loading={login.isPending}>
          Giriş yap
        </Button>
      </form>
    </AuthLayout>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
