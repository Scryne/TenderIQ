"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileStack, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { StatusPill, type StatusTone } from "@/components/status-pill";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";

const TENDER_STATUS: Record<string, { label: string; tone: StatusTone }> = {
  draft: { label: "Taslak", tone: "neutral" },
  analyzing: { label: "Analiz ediliyor", tone: "info" },
  review_ready: { label: "İncelemeye hazır", tone: "success" },
  archived: { label: "Arşivlendi", tone: "neutral" },
};

export default function TendersPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);

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
      setDialogOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["tenders"] });
      router.push(`/tenders/${tender.id}`);
    },
  });

  const newTenderDialog = (
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="size-4" strokeWidth={1.75} />
          Yeni ihale
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            createTender.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>Yeni ihale projesi</DialogTitle>
            <DialogDescription>
              Projeyi oluşturun; ardından şartname dosyalarını yükleyin.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 py-4">
            <Label htmlFor="tender-title">İhale başlığı</Label>
            <Input
              id="tender-title"
              required
              autoFocus
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="ör. 2026/128764 — BT Altyapı Yenileme"
            />
            {createTender.isError && (
              <p className="text-sm text-danger">{createTender.error.message}</p>
            )}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={createTender.isPending}>
              {createTender.isPending ? "Oluşturuluyor…" : "Oluştur"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );

  return (
    <>
      <PageHeader
        title="İhalelerim"
        context="Şartname yükleyin; gereksinim, belge, risk ve takvim analizi otomatik başlasın."
        actions={newTenderDialog}
      />

      {tenders.isPending && (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      )}
      {tenders.isError && <p className="text-sm text-danger">{tenders.error.message}</p>}

      {tenders.data !== undefined && tenders.data.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-xl border bg-surface py-16">
          <span className="flex size-10 items-center justify-center rounded-lg bg-surface-2">
            <FileStack className="size-5 text-ink-3" strokeWidth={1.5} />
          </span>
          <p className="text-sm text-ink-2">Henüz ihale projesi yok.</p>
          {newTenderDialog}
        </div>
      )}

      {tenders.data !== undefined && tenders.data.length > 0 && (
        <div className="overflow-hidden rounded-xl border bg-surface">
          <Table>
            <TableHeader>
              <TableRow className="bg-surface-2/60 hover:bg-surface-2/60">
                <TableHead className="text-xs font-medium text-ink-2">İhale</TableHead>
                <TableHead className="w-44 text-right text-xs font-medium text-ink-2">
                  Durum
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tenders.data.map((tender) => {
                const status = TENDER_STATUS[tender.status] ?? {
                  label: tender.status,
                  tone: "neutral" as StatusTone,
                };
                return (
                  <TableRow
                    key={tender.id}
                    className="h-14 cursor-pointer"
                    onClick={() => router.push(`/tenders/${tender.id}`)}
                  >
                    <TableCell className="font-medium text-ink-1">{tender.title}</TableCell>
                    <TableCell className="text-right">
                      <StatusPill tone={status.tone} label={status.label} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
