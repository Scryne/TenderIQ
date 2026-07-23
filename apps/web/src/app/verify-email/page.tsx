"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

type State = "pending" | "success" | "error";

function VerifyEmail() {
  const token = useSearchParams().get("token");
  const [state, setState] = useState<State>("pending");

  useEffect(() => {
    if (token === null) {
      setState("error");
      return;
    }
    let cancelled = false;
    void (async () => {
      const { error } = await api.POST("/api/v1/auth/verify-email", { body: { token } });
      if (!cancelled) setState(error === undefined ? "success" : "error");
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-6 p-8">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>E-posta doğrulama</CardTitle>
          <CardDescription>
            {state === "pending" && "E-posta adresiniz doğrulanıyor…"}
            {state === "success" && "E-posta adresiniz doğrulandı. Teşekkürler!"}
            {state === "error" &&
              "Doğrulama bağlantısı geçersiz veya süresi dolmuş. Yeni bir bağlantı isteyin."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild className="w-full">
            <Link href="/tenders">Uygulamaya git</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmail />
    </Suspense>
  );
}
