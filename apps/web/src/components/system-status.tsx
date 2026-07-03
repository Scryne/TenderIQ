"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

/** Tip-güvenli API istemcisini uçtan uca kanıtlayan canlı sistem durumu kartı. */
export function SystemStatus() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["system-version"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/system/version");
      if (error !== undefined) {
        throw new Error("API'ye ulaşılamadı.");
      }
      return data;
    },
  });

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {isLoading ? (
            <Loader2 className="animate-spin text-muted-foreground" />
          ) : error ? (
            <XCircle className="text-destructive" />
          ) : (
            <CheckCircle2 className="text-primary" />
          )}
          Sistem Durumu
        </CardTitle>
        <CardDescription>Backend API bağlantısı (tip-güvenli istemci ile)</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">Bağlanıyor…</p>}
        {error && (
          <p className="text-sm text-destructive">
            API'ye ulaşılamadı. `api` servisinin çalıştığından emin olun (`:8000`).
          </p>
        )}
        {data && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Servis</dt>
            <dd className="font-medium">{data.name}</dd>
            <dt className="text-muted-foreground">Sürüm</dt>
            <dd className="font-mono">{data.version}</dd>
            <dt className="text-muted-foreground">Ortam</dt>
            <dd className="font-medium">{data.environment}</dd>
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
