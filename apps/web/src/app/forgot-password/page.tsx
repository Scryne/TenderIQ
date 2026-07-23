"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

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

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");

  const submit = useMutation({
    mutationFn: async () => {
      // Yanıt her zaman 204 (kullanıcı numaralandırma sızmaz).
      await api.POST("/api/v1/auth/forgot-password", { body: { email } });
    },
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-6 p-8">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Parolanızı mı unuttunuz?</CardTitle>
          <CardDescription>
            E-posta adresinizi girin; kayıtlıysa sıfırlama bağlantısı gönderelim.
          </CardDescription>
        </CardHeader>
        {submit.isSuccess ? (
          <CardContent className="space-y-4">
            <p className="text-sm text-ink-2">
              Eğer <span className="font-medium text-ink-1">{email}</span> bir hesaba bağlıysa,
              sıfırlama bağlantısını içeren bir e-posta gönderdik.
            </p>
            <Button asChild variant="outline" className="w-full">
              <Link href="/login">Girişe dön</Link>
            </Button>
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
                <Label htmlFor="email">E-posta</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
            </CardContent>
            <CardFooter className="flex-col items-stretch gap-3">
              <Button type="submit" disabled={submit.isPending}>
                {submit.isPending ? "Gönderiliyor…" : "Sıfırlama bağlantısı gönder"}
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
