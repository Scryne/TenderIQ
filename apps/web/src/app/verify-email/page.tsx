"use client";

import { CheckCircle2, Loader2, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AuthNotice } from "@/components/auth/auth-layout";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type State = "pending" | "success" | "error";

function VerifyEmail() {
  const token = useSearchParams().get("token");
  const [result, setResult] = useState<State>("pending");
  // Bağlantıda token yoksa sonuç render sırasında bellidir; bunu efektte state'e
  // yazmak gereksiz bir ikinci render (ve bir kare "doğrulanıyor…") demekti.
  const state: State = token === null ? "error" : result;

  useEffect(() => {
    if (token === null) return;
    let cancelled = false;
    void (async () => {
      const { error } = await api.POST("/api/v1/auth/verify-email", { body: { token } });
      if (!cancelled) setResult(error === undefined ? "success" : "error");
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <AuthNotice title="E-posta doğrulama">
      <div className="flex items-start gap-3">
        {state === "pending" && (
          <Loader2 aria-hidden className="mt-0.5 size-4 shrink-0 animate-spin text-ink-3" />
        )}
        {state === "success" && (
          <CheckCircle2
            aria-hidden
            className="mt-0.5 size-4 shrink-0 text-success"
            strokeWidth={1.75}
          />
        )}
        {state === "error" && (
          <TriangleAlert
            aria-hidden
            className="mt-0.5 size-4 shrink-0 text-danger"
            strokeWidth={1.75}
          />
        )}
        <p aria-live="polite">
          {state === "pending" && "E-posta adresiniz doğrulanıyor…"}
          {state === "success" &&
            "E-posta adresiniz doğrulandı. Artık tüm özellikleri kullanabilirsiniz."}
          {state === "error" &&
            "Bağlantı geçersiz ya da süresi dolmuş. Ayarlar sayfasından yeni bir doğrulama e-postası isteyin."}
        </p>
      </div>
      <Button asChild className="w-full">
        <Link href={state === "error" ? "/settings" : "/panel"}>
          {state === "error" ? "Ayarlara git" : "Panele git"}
        </Link>
      </Button>
    </AuthNotice>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmail />
    </Suspense>
  );
}
