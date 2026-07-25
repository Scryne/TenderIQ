"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

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
import { api } from "@/lib/api";

/**
 * İhale silme — yıkıcı eylem, onay ister.
 *
 * Kullanıcıya iki şey AÇIKÇA söylenir: (1) neyin birlikte gittiği (dokümanlar ve
 * bulgular), (2) kalıcı olmadan önce bir geri alma penceresi olduğu. İkincisi
 * olmadan kullanıcı "sil"e basmaktan çekinir ya da bastıktan sonra paniğe kapılır;
 * KVKK gereği pencerenin sonunda silmenin GERÇEKTEN kalıcı olduğu da belirtilir.
 */
export function DeleteTenderDialog({
  tenderId,
  title,
  retentionDays = 30,
}: {
  tenderId: string;
  title: string;
  /** Geri alma penceresi (sunucudaki DATA_RETENTION_DAYS ile aynı olmalı). */
  retentionDays?: number;
}) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();

  const remove = useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE("/api/v1/tenders/{tender_id}", {
        params: { path: { tender_id: tenderId } },
      });
      if (error !== undefined) throw new Error("İhale silinemedi. Bir kez daha deneyin.");
    },
    onSuccess: () => {
      setOpen(false);
      // Panel ve liste bu ihaleyi artık görmemeli.
      void queryClient.invalidateQueries({ queryKey: ["tenders"] });
      void queryClient.invalidateQueries({ queryKey: ["panel"] });
      toast.success(`"${title}" silindi.`, {
        description: `${retentionDays} gün içinde geri alınabilir.`,
        action: {
          label: "Geri al",
          onClick: () => {
            void (async () => {
              const { error } = await api.POST("/api/v1/tenders/{tender_id}/restore", {
                params: { path: { tender_id: tenderId } },
              });
              if (error !== undefined) {
                toast.error("Geri alınamadı.");
                return;
              }
              void queryClient.invalidateQueries({ queryKey: ["tenders"] });
              void queryClient.invalidateQueries({ queryKey: ["panel"] });
              toast.success("İhale geri alındı.");
              router.push(`/tenders/${tenderId}`);
            })();
          },
        },
      });
      router.push("/tenders");
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="danger-ghost">
          <Trash2 strokeWidth={1.75} />
          Sil
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>İhaleyi sil</DialogTitle>
          <DialogDescription>
            <span className="font-medium text-ink-1">{title}</span> ve ona bağlı tüm dokümanlar,
            çıkarılmış bulgular ve yorumlar silinir.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <p className="text-sm text-ink-2">
            {retentionDays} gün içinde geri alabilirsiniz. Bu sürenin sonunda veriler
            dosyalarıyla birlikte <span className="font-medium text-ink-1">kalıcı olarak</span>{" "}
            silinir ve geri getirilemez.
          </p>
          {remove.isError && <InlineError message={remove.error.message} />}
        </DialogBody>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="secondary" disabled={remove.isPending}>
              Vazgeç
            </Button>
          </DialogClose>
          <Button variant="danger" onClick={() => remove.mutate()} disabled={remove.isPending}>
            {remove.isPending ? "Siliniyor…" : "Sil"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
