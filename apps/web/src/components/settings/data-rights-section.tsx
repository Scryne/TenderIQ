"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { InlineError } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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

/**
 * KVKK veri sahibi hakları: verinin kopyasını alma (md. 11) ve hesabı kapatma (md. 7).
 *
 * İkisi bilinçli olarak AYNI yerde durur ve dışa aktarma önce gelir: hesabını
 * kapatmak isteyen kullanıcının önce verisini indirebileceğini görmesi gerekir.
 * Kapatma, sayfanın en altında ve tek yıkıcı öğe olarak konumlanır.
 */
export function DataRightsSection({ isAdmin }: { isAdmin: boolean }) {
  const router = useRouter();
  const [confirmSlug, setConfirmSlug] = useState("");
  const [open, setOpen] = useState(false);

  // Aktif organizasyonun slug'ı onay metni için gerekli; `/auth/me` slug
  // döndürmediğinden üyelik listesinden alınır (aktif olan işaretlidir).
  const memberships = useQuery({
    queryKey: ["memberships"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/auth/memberships");
      if (error !== undefined) throw new Error("Organizasyonlar alınamadı.");
      return data;
    },
  });
  const organizationSlug =
    memberships.data?.find((membership) => membership.is_active)?.organization_slug ?? "";

  const exportData = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.GET("/api/v1/organizations/current/export");
      if (error !== undefined) throw new Error("Veriler dışa aktarılamadı.");
      return data;
    },
    onSuccess: (data) => {
      // Tarayıcıda dosyaya çevir: sunucuya ek bir indirme ucu açmaya gerek yok.
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `tenderiq-verilerim-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
      toast.success("Verileriniz indirildi.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const closeAccount = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/organizations/current/close", {
        body: { confirm_slug: confirmSlug },
      });
      if (error !== undefined) {
        throw new Error("Hesap kapatılamadı. Kısa adı doğru yazdığınızdan emin olun.");
      }
      return data;
    },
    onSuccess: (data) => {
      setOpen(false);
      toast.success("Hesap kapatıldı.", {
        description: `Veriler ${data.purge_after_days} gün sonra kalıcı olarak silinecek.`,
      });
      router.push("/login");
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Verilerimin kopyası</CardTitle>
          <CardDescription>
            Hesabınıza ve bu organizasyona ait kayıtların makine-okunur (JSON) kopyasını
            indirin. Şartname dosyalarının kendisi değil, hangi dosyaların işlendiği
            listelenir; dosyalara inceleme ekranından erişebilirsiniz.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="secondary"
            onClick={() => exportData.mutate()}
            disabled={exportData.isPending}
          >
            <Download strokeWidth={1.75} />
            {exportData.isPending ? "Hazırlanıyor…" : "Verilerimi indir"}
          </Button>
        </CardContent>
      </Card>

      {isAdmin && (
        <Card className="border-danger/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldAlert strokeWidth={1.75} className="size-4 text-danger" />
              Hesabı kapat
            </CardTitle>
            <CardDescription>
              Organizasyon ve tüm ihaleler, dokümanlar, bulgular silinir. Tüm üyelerin
              erişimi hemen kesilir.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button variant="danger">Hesabı kapat</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Hesabı kapat</DialogTitle>
                  <DialogDescription>
                    Bu işlemin arayüzden geri dönüşü yoktur.
                  </DialogDescription>
                </DialogHeader>
                <DialogBody className="flex flex-col gap-4">
                  <p className="text-sm text-ink-2">
                    Tüm ihaleler, dokümanlar ve bulgular önce erişime kapatılır, ardından
                    kalıcı olarak silinir. Yanlışlıkla kapattıysanız bu süre içinde destek
                    ile iletişime geçin.
                  </p>
                  <p className="text-sm text-ink-2">
                    Fatura ve kullanım kayıtlarınız, vergi mevzuatı gereği saklanmaya devam
                    eder; bunlar silinemez.
                  </p>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="confirm-slug">
                      Onaylamak için <span className="font-mono">{organizationSlug}</span> yazın
                    </Label>
                    <Input
                      id="confirm-slug"
                      value={confirmSlug}
                      onChange={(event) => setConfirmSlug(event.target.value)}
                      autoComplete="off"
                    />
                  </div>
                  {closeAccount.isError && <InlineError message={closeAccount.error.message} />}
                </DialogBody>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="secondary" disabled={closeAccount.isPending}>
                      Vazgeç
                    </Button>
                  </DialogClose>
                  <Button
                    variant="danger"
                    onClick={() => closeAccount.mutate()}
                    disabled={closeAccount.isPending || confirmSlug !== organizationSlug}
                  >
                    {closeAccount.isPending ? "Kapatılıyor…" : "Hesabı kalıcı olarak kapat"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
