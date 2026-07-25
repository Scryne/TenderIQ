"use client";

/** Word/Excel export dialogu: biçim seç → indir. */

import { Download, FileSpreadsheet, FileText, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { downloadTenderReport } from "@/components/review/use-finding-review";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { cn } from "@/lib/utils";

type ExportFormat = "docx" | "xlsx";

const FORMATS: { value: ExportFormat; label: string; hint: string; icon: LucideIcon }[] = [
  {
    value: "docx",
    label: "Word (.docx)",
    hint: "Yapılandırılmış rapor + kaynakça",
    icon: FileText,
  },
  {
    value: "xlsx",
    label: "Excel (.xlsx)",
    hint: "Kategori başına sayfa, filtrelenebilir",
    icon: FileSpreadsheet,
  },
];

export function ExportDialog({ tenderId }: { tenderId: string }) {
  const [open, setOpen] = useState(false);
  const [format, setFormat] = useState<ExportFormat>("docx");
  const [includePending, setIncludePending] = useState(false);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      await downloadTenderReport(tenderId, format, includePending);
      // Eylem sonucu geçmiş zamanla yazılır (§8.8).
      toast.success("Rapor indirildi.");
      setOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Rapor üretilemedi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary">
          <Download strokeWidth={1.75} />
          Rapor indir
        </Button>
      </DialogTrigger>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Analiz raporunu dışa aktar</DialogTitle>
          <DialogDescription>
            Rapora onaylı ve düzeltilmiş bulgular girer. Her satırın kaynak referansı (sayfa ve
            madde) raporda korunur.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-2">
            <legend className="text-overline mb-2 text-ink-3">BİÇİM</legend>
            {FORMATS.map((option) => {
              const selected = format === option.value;
              return (
                <label
                  key={option.value}
                  className={cn(
                    "flex cursor-pointer items-center gap-3 rounded-sm border px-3.5 py-3 transition-colors duration-[120ms]",
                    selected
                      ? "border-accent bg-surface-2"
                      : "border-border hover:border-border-strong hover:bg-surface-2",
                  )}
                >
                  <input
                    type="radio"
                    name="export-format"
                    value={option.value}
                    checked={selected}
                    onChange={() => setFormat(option.value)}
                    className="sr-only"
                  />
                  <option.icon
                    aria-hidden
                    className={cn("size-5 shrink-0", selected ? "text-ink-1" : "text-ink-3")}
                    strokeWidth={1.5}
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-ink-1">{option.label}</span>
                    <span className="block text-xs text-ink-3">{option.hint}</span>
                  </span>
                  <span
                    aria-hidden
                    className={cn(
                      "ml-auto size-4 shrink-0 rounded-full border",
                      selected ? "border-accent bg-accent" : "border-border-strong",
                    )}
                  />
                </label>
              );
            })}
          </fieldset>

          <label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink-2">
            <Checkbox
              className="mt-0.5"
              checked={includePending}
              onCheckedChange={(checked) => setIncludePending(checked === true)}
            />
            Onay bekleyen bulguları da dahil et — raporda &quot;Onay bekliyor&quot; olarak
            işaretlenir.
          </label>
        </DialogBody>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="secondary" disabled={busy}>
              İptal
            </Button>
          </DialogClose>
          <Button onClick={run} loading={busy}>
            İndir
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
