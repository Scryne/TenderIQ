"use client";

/** Word/Excel export dialogu (Sprint 3.2, §4.1): biçim seç → indir. */

import { Download, FileSpreadsheet, FileText } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { downloadTenderReport } from "@/components/review/use-finding-review";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type ExportFormat = "docx" | "xlsx";

const FORMATS: { value: ExportFormat; label: string; hint: string; icon: typeof FileText }[] = [
  { value: "docx", label: "Word (.docx)", hint: "Yapılandırılmış rapor + kaynakça", icon: FileText },
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
        <Button size="sm" variant="outline">
          <Download data-slot="icon" />
          Rapor indir
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Analiz raporunu dışa aktar</DialogTitle>
          <DialogDescription>
            Rapora onaylı ve düzeltilmiş bulgular girer; kaynak referansları (sayfa no)
            raporda görünür.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-2">
          {FORMATS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setFormat(option.value)}
              className={cn(
                "flex items-center gap-3 rounded-lg border px-3.5 py-3 text-left transition-colors",
                format === option.value
                  ? "border-brand bg-brand-weak/40 ring-2 ring-brand/20"
                  : "hover:border-border-strong hover:bg-surface-2/50",
              )}
            >
              <option.icon className="size-5 shrink-0 text-ink-2" strokeWidth={1.5} />
              <span>
                <span className="block text-sm font-medium text-ink-1">{option.label}</span>
                <span className="block text-xs text-ink-3">{option.hint}</span>
              </span>
            </button>
          ))}
        </div>

        <Label className="flex items-center gap-2 text-[13px] font-normal text-ink-2">
          <Checkbox
            checked={includePending}
            onCheckedChange={(checked) => setIncludePending(checked === true)}
          />
          Onay bekleyen bulguları da dahil et (raporda &quot;Onay bekliyor&quot; olarak işaretlenir)
        </Label>

        <DialogFooter>
          <Button variant="outline" size="sm" onClick={() => setOpen(false)} disabled={busy}>
            Vazgeç
          </Button>
          <Button size="sm" onClick={run} disabled={busy}>
            {busy ? "Üretiliyor…" : "İndir"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
