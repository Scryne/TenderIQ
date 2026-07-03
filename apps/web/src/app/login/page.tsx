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
import { api } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const login = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/auth/login", {
        body: { email, password },
      });
      if (error !== undefined) {
        throw new Error("E-posta veya parola hatalı.");
      }
      return data;
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
            {login.isSuccess && (
              <p className="text-sm text-primary">
                Giriş başarılı — token alındı ({login.data.token_type}).
              </p>
            )}
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
