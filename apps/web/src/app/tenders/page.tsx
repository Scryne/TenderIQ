"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api";

const TENDER_STATUS_LABELS: Record<string, string> = {
  draft: "Taslak",
  analyzing: "Analiz ediliyor",
  review_ready: "İncelemeye hazır",
  archived: "Arşivlendi",
};

export default function TendersPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");

  const tenders = useQuery({
    queryKey: ["tenders"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/tenders");
      if (error !== undefined) {
        if (response.status === 401) {
          router.push("/login");
        }
        throw new Error("İhaleler yüklenemedi.");
      }
      return data;
    },
  });

  const createTender = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/tenders", {
        body: { title },
      });
      if (error !== undefined) throw new Error("İhale oluşturulamadı.");
      return data;
    },
    onSuccess: (tender) => {
      setTitle("");
      void queryClient.invalidateQueries({ queryKey: ["tenders"] });
      router.push(`/tenders/${tender.id}`);
    },
  });

  const logout = useMutation({
    mutationFn: async () => {
      await fetch("/api/session", { method: "DELETE" });
    },
    onSuccess: () => {
      router.push("/login");
      router.refresh();
    },
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">İhalelerim</h1>
        <Button variant="outline" size="sm" onClick={() => logout.mutate()}>
          Çıkış yap
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Yeni ihale</CardTitle>
          <CardDescription>
            Bir ihale projesi oluşturun; ardından şartname dosyalarını yükleyin.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              createTender.mutate();
            }}
          >
            <input
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="İhale başlığı (ör. 2026 BT Altyapı İhalesi)"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button type="submit" disabled={createTender.isPending}>
              {createTender.isPending ? "Oluşturuluyor…" : "Oluştur"}
            </Button>
          </form>
          {createTender.isError && (
            <p className="mt-2 text-sm text-destructive">{createTender.error.message}</p>
          )}
        </CardContent>
      </Card>

      {tenders.isPending && <p className="text-sm text-muted-foreground">Yükleniyor…</p>}
      {tenders.isError && <p className="text-sm text-destructive">{tenders.error.message}</p>}
      {tenders.data !== undefined && tenders.data.length === 0 && (
        <p className="text-sm text-muted-foreground">Henüz ihale yok. İlkini yukarıdan oluşturun.</p>
      )}

      <div className="flex flex-col gap-3">
        {tenders.data?.map((tender) => (
          <Link key={tender.id} href={`/tenders/${tender.id}`}>
            <Card className="transition-colors hover:bg-muted/50">
              <CardContent className="flex items-center justify-between py-4">
                <span className="font-medium">{tender.title}</span>
                <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
                  {TENDER_STATUS_LABELS[tender.status] ?? tender.status}
                </span>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </main>
  );
}
