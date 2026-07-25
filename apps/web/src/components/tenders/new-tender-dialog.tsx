"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { InlineError } from "@/components/states";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";

/** Yeni ihale projesi — DESIGN.md §8.6 form alanı + §8.7 modal sözleşmesi. */
export function NewTenderDialog({
  variant = "primary",
}: {
  variant?: "primary" | "secondary";
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [open, setOpen] = useState(false);

  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/tenders", { body: { title } });
      if (error !== undefined) throw new Error("İhale oluşturulamadı. Bir kez daha deneyin.");
      return data;
    },
    onSuccess: (tender) => {
      setTitle("");
      setOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["tenders"] });
      router.push(`/tenders/${tender.id}`);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={variant}>
          <Plus strokeWidth={2} />
          Yeni ihale
        </Button>
      </DialogTrigger>
      <DialogContent size="sm">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>Yeni ihale projesi</DialogTitle>
            <DialogDescription>
              Projeyi açın, ardından şartname dosyalarını yükleyin.
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="flex flex-col gap-1.5">
            <Label htmlFor="tender-title">
              İhale başlığı <span className="text-danger">*</span>
            </Label>
            <Input
              id="tender-title"
              required
              autoFocus
              maxLength={200}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="2026/128764 — Bilgi işlem altyapı yenileme"
              aria-describedby="tender-title-help"
            />
            {/* Placeholder etiketin yerine geçmez, örnek verir (§8.6). */}
            <p id="tender-title-help" className="text-xs text-ink-3">
              İhale kayıt numarası ve konusu — listede bu adla görünür.
            </p>
            {create.isError && (
              <InlineError message={create.error.message} className="mt-2" />
            )}
          </DialogBody>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="secondary">
                İptal
              </Button>
            </DialogClose>
            <Button type="submit" loading={create.isPending}>
              Oluştur
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
