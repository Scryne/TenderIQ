"use client";

import { useMutation } from "@tanstack/react-query";
import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthLayout } from "@/components/auth/auth-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");

  const submit = useMutation({
    mutationFn: async () => {
      // Yanıt her zaman 204 (kullanıcı numaralandırma sızmaz).
      await api.POST("/api/v1/auth/forgot-password", { body: { email } });
    },
  });

  if (submit.isSuccess) {
    return (
      <AuthLayout
        title="Bağlantı gönderildi"
        description="Gelen kutunuzu kontrol edin."
      >
        <div className="flex flex-col gap-5">
          <div className="flex items-start gap-3 rounded-lg border border-border bg-surface p-4">
            <MailCheck
              aria-hidden
              className="mt-0.5 size-4 shrink-0 text-success"
              strokeWidth={1.75}
            />
            <p className="text-sm text-ink-2">
              <span className="font-medium text-ink-1">{email}</span> bir hesaba bağlıysa,
              sıfırlama bağlantısını içeren e-posta gönderildi. Bağlantı 1 saat geçerlidir.
            </p>
          </div>
          <Button asChild variant="secondary" className="w-full">
            <Link href="/login">Girişe dön</Link>
          </Button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Parolanızı mı unuttunuz?"
      description="E-posta adresinizi girin; kayıtlıysa sıfırlama bağlantısı gönderelim."
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          submit.mutate();
        }}
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">E-posta</Label>
          <Input
            id="email"
            type="email"
            required
            autoFocus
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="ad.soyad@firma.com.tr"
          />
        </div>
        <Button type="submit" className="mt-1 w-full" loading={submit.isPending}>
          Sıfırlama bağlantısı gönder
        </Button>
        <Button asChild variant="ghost" className="w-full">
          <Link href="/login">Girişe dön</Link>
        </Button>
      </form>
    </AuthLayout>
  );
}
