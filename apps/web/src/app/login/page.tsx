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
          throw new Error("Çok fazla deneme yapıldı; lütfen daha sonra yeniden deneyin.");
        }
        if (response.status === 401) {
          throw new Error("E-posta veya parola hatalı.");
        }
        throw new Error("Giriş yapılamadı; lütfen daha sonra yeniden deneyin.");
      }
    },
    onSuccess: () => {
      const next = searchParams.get("next");
      // Yalnızca site-içi yollar: "//evil.com" gibi protokol-göreli URL'ler dışarı kaçırır.
      const isInternal = next !== null && next.startsWith("/") && !next.startsWith("//");
      router.push(isInternal ? next : "/tenders");
      router.refresh();
    },
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-6 p-8">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Giriş yap</CardTitle>
          <CardDescription>TenderIQ hesabınızla oturum açın.</CardDescription>
        </CardHeader>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            login.mutate();
          }}
        >
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="email" className="text-sm font-medium">
                E-posta
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="password" className="text-sm font-medium">
                Parola
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            {login.isError && <p className="text-sm text-destructive">{login.error.message}</p>}
          </CardContent>
          <CardFooter className="flex-col items-stretch gap-3">
            <Button type="submit" disabled={login.isPending}>
              {login.isPending ? "Giriş yapılıyor…" : "Giriş yap"}
            </Button>
            <Link href="/" className="text-center text-sm text-muted-foreground hover:underline">
              Ana sayfaya dön
            </Link>
          </CardFooter>
        </form>
      </Card>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
