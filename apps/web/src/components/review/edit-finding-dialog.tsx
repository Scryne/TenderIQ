"use client";

/**
 * Bulgu düzeltme dialogu (Sprint 3.2, §4.3): kategoriye özgü alanlar.
 * Yalnız gerçekten değişen alanlar PATCH'e gider; hiç değişiklik yoksa uyarılır.
 */

import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import type { EditVariables } from "@/components/review/use-finding-review";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  COMPLIANCE_STATUS,
  DELIVERABLE_KIND_LABELS,
  REQUIREMENT_KIND_LABELS,
  RISK_CATEGORY_LABELS,
  RISK_SEVERITY,
  TIMELINE_KIND_LABELS,
  type ComplianceFinding,
  type DeliverableFinding,
  type RequirementFinding,
  type RiskFinding,
  type TimelineFinding,
} from "@/lib/findings";

export type EditTarget =
  | { category: "requirements"; finding: RequirementFinding }
  | { category: "deliverables"; finding: DeliverableFinding }
  | { category: "risks"; finding: RiskFinding }
  | { category: "timeline"; finding: TimelineFinding }
  | { category: "compliance"; finding: ComplianceFinding };

export type SubmitEdit = (variables: EditVariables) => void;

function FieldSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Record<string, string | { label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-[13px]">{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger size="sm" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(options).map(([key, option]) => (
            <SelectItem key={key} value={key}>
              {typeof option === "string" ? option : option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-[13px]">{label}</Label>
      {multiline ? (
        <Textarea value={value} onChange={(e) => onChange(e.target.value)} rows={4} />
      ) : (
        <Input value={value} onChange={(e) => onChange(e.target.value)} />
      )}
    </div>
  );
}

function MandatoryField({
  value,
  onChange,
}: {
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <Label className="flex items-center gap-2 text-[13px] font-normal">
      <Checkbox checked={value} onCheckedChange={(checked) => onChange(checked === true)} />
      Zorunlu gereklilik
    </Label>
  );
}

/** Değişen alanları hesaplar; boş metinleri değişiklik saymaz. */
function changedFields<T extends Record<string, unknown>>(
  original: Record<string, unknown>,
  edited: T,
): Partial<T> {
  const changes: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(edited)) {
    if (typeof value === "string" && value.trim() === "") continue;
    if (original[key] !== value) changes[key] = value;
  }
  return changes as Partial<T>;
}

function EditForm({ target, onSubmit, onClose }: {
  target: EditTarget;
  onSubmit: SubmitEdit;
  onClose: () => void;
}) {
  // Kategoriye göre alan durumu; key={finding.id} ile her hedefte sıfırlanır.
  const [text, setText] = useState(() => {
    switch (target.category) {
      case "requirements":
      case "risks":
        return target.finding.text;
      case "deliverables":
        return target.finding.name;
      case "timeline":
        return target.finding.label;
      case "compliance":
        return target.finding.rationale;
    }
  });
  const [choice, setChoice] = useState<string>(() => {
    switch (target.category) {
      case "requirements":
      case "deliverables":
      case "timeline":
        return target.finding.kind;
      case "risks":
        return target.finding.severity;
      case "compliance":
        return target.finding.status;
    }
  });
  const [secondary, setSecondary] = useState<string>(() =>
    target.category === "risks" ? target.finding.category : "",
  );
  const [valueText, setValueText] = useState<string>(() =>
    target.category === "timeline" ? target.finding.value_text : "",
  );
  const [mandatory, setMandatory] = useState<boolean>(() =>
    target.category === "requirements" || target.category === "deliverables"
      ? target.finding.is_mandatory
      : false,
  );

  function submit() {
    let fields: Record<string, unknown>;
    switch (target.category) {
      case "requirements":
        fields = changedFields(target.finding as unknown as Record<string, unknown>, {
          text,
          kind: choice,
          is_mandatory: mandatory,
        });
        break;
      case "deliverables":
        fields = changedFields(target.finding as unknown as Record<string, unknown>, {
          name: text,
          kind: choice,
          is_mandatory: mandatory,
        });
        break;
      case "risks":
        fields = changedFields(target.finding as unknown as Record<string, unknown>, {
          text,
          severity: choice,
          category: secondary,
        });
        break;
      case "timeline":
        fields = changedFields(target.finding as unknown as Record<string, unknown>, {
          label: text,
          kind: choice,
          value_text: valueText,
        });
        break;
      case "compliance":
        fields = changedFields(target.finding as unknown as Record<string, unknown>, {
          rationale: text,
          status: choice,
        });
        break;
    }
    if (Object.keys(fields).length === 0) {
      toast.info("Değişiklik yapılmadı.");
      return;
    }
    // Alanlar yukarıdaki switch'te kategoriyle eşleşerek kuruldu (cast güvenli).
    onSubmit({
      category: target.category,
      id: target.finding.id,
      fields,
    } as EditVariables);
    onClose();
  }

  let body: ReactNode;
  switch (target.category) {
    case "requirements":
      body = (
        <>
          <TextField label="Gereksinim metni" value={text} onChange={setText} multiline />
          <FieldSelect
            label="Tür"
            value={choice}
            options={REQUIREMENT_KIND_LABELS}
            onChange={setChoice}
          />
          <MandatoryField value={mandatory} onChange={setMandatory} />
        </>
      );
      break;
    case "deliverables":
      body = (
        <>
          <TextField label="Belge adı" value={text} onChange={setText} multiline />
          <FieldSelect
            label="Tür"
            value={choice}
            options={DELIVERABLE_KIND_LABELS}
            onChange={setChoice}
          />
          <MandatoryField value={mandatory} onChange={setMandatory} />
        </>
      );
      break;
    case "risks":
      body = (
        <>
          <TextField label="Risk maddesi" value={text} onChange={setText} multiline />
          <FieldSelect label="Önem" value={choice} options={RISK_SEVERITY} onChange={setChoice} />
          <FieldSelect
            label="Kategori"
            value={secondary}
            options={RISK_CATEGORY_LABELS}
            onChange={setSecondary}
          />
        </>
      );
      break;
    case "timeline":
      body = (
        <>
          <TextField label="Öğe" value={text} onChange={setText} />
          <FieldSelect
            label="Tür"
            value={choice}
            options={TIMELINE_KIND_LABELS}
            onChange={setChoice}
          />
          <TextField label="Değer (tarih/süre)" value={valueText} onChange={setValueText} />
        </>
      );
      break;
    case "compliance":
      body = (
        <>
          <FieldSelect
            label="Durum"
            value={choice}
            options={COMPLIANCE_STATUS}
            onChange={setChoice}
          />
          <TextField label="Gerekçe" value={text} onChange={setText} multiline />
        </>
      );
      break;
  }

  return (
    <>
      <div className="grid gap-4 py-2">{body}</div>
      <DialogFooter>
        <Button variant="outline" size="sm" onClick={onClose}>
          Vazgeç
        </Button>
        <Button size="sm" onClick={submit}>
          Düzeltmeyi kaydet
        </Button>
      </DialogFooter>
    </>
  );
}

export function EditFindingDialog({
  target,
  onClose,
  onSubmit,
}: {
  target: EditTarget | null;
  onClose: () => void;
  onSubmit: SubmitEdit;
}) {
  return (
    <Dialog open={target !== null} onOpenChange={(open) => open || onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Bulguyu düzelt</DialogTitle>
          <DialogDescription>
            Düzeltme kaydedilir, bulgu &quot;Düzeltildi&quot; durumuna geçer ve düzenleme
            geçmişine yazılır.
          </DialogDescription>
        </DialogHeader>
        {target !== null && (
          <EditForm key={target.finding.id} target={target} onSubmit={onSubmit} onClose={onClose} />
        )}
      </DialogContent>
    </Dialog>
  );
}
