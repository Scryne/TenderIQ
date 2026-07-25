"use client";

import { ChevronDown, X, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════════════════════
 * FİLTRE ÇİPİ SATIRI — DESIGN.md §8.10
 *
 * Kritik kural: varsayılandan farklı bir filtre AKTİF görünür (mürekkep
 * kenarlık + koyu zemin). Bu ayrım olmadan kullanıcı neyi filtrelediğini
 * unutur ve "kayıt yok" ekranını hata sanır.
 * ═══════════════════════════════════════════════════════════════════════════ */

export type FilterOption = { value: string; label: string };

export function FilterChip({
  icon: Icon,
  label,
  value,
  options,
  onChange,
  /** Varsayılan değer; farklıysa çip aktif görünür. */
  defaultValue = "all",
  className,
}: {
  icon?: LucideIcon;
  /** Çipin sabit adı — seçim varsayılandayken gösterilir ("Tüm türler"). */
  label: string;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
  defaultValue?: string;
  className?: string;
}) {
  const active = value !== defaultValue;
  const selected = options.find((option) => option.value === value);

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger
        size="sm"
        aria-label={label}
        className={cn(
          "h-8 gap-1.5 rounded-sm px-2.5 text-sm [&>svg:last-child]:hidden",
          active
            ? "border-accent bg-accent text-ink-on-accent"
            : "border-border-strong bg-surface text-ink-2",
          className,
        )}
      >
        {Icon !== undefined && (
          <Icon
            aria-hidden
            className={cn("size-3.5 shrink-0", active ? "text-ink-on-accent" : "text-ink-3")}
            strokeWidth={1.75}
          />
        )}
        <SelectValue>{active ? (selected?.label ?? value) : label}</SelectValue>
        <ChevronDown
          aria-hidden
          className={cn("size-3.5 shrink-0", active ? "text-ink-on-accent" : "text-ink-3")}
          strokeWidth={1.75}
        />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={defaultValue}>{label}</SelectItem>
        {options
          .filter((option) => option.value !== defaultValue)
          .map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
      </SelectContent>
    </Select>
  );
}

/** Aç/kapa çipi — tek durumlu filtreler ("Yalnız zorunlu"). */
export function ToggleChip({
  icon: Icon,
  label,
  pressed,
  onPressedChange,
  className,
}: {
  icon?: LucideIcon;
  label: string;
  pressed: boolean;
  onPressedChange: (pressed: boolean) => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={() => onPressedChange(!pressed)}
      className={cn(
        "inline-flex h-8 shrink-0 items-center gap-1.5 rounded-sm border px-2.5 text-sm",
        "transition-colors duration-[120ms] ease-out",
        pressed
          ? "border-accent bg-accent text-ink-on-accent"
          : "border-border-strong bg-surface text-ink-2 hover:bg-surface-2",
        className,
      )}
    >
      {Icon !== undefined && <Icon aria-hidden className="size-3.5" strokeWidth={1.75} />}
      {label}
    </button>
  );
}

/**
 * Çip satırı kabı. En az bir filtre aktifse sağda "Sıfırla" belirir (§8.10).
 * 5'ten fazla çip varsa bilgi mimarisi yanlıştır — popover'a taşınmalıdır.
 */
export function FilterBar({
  children,
  dirty,
  onReset,
  trailing,
  className,
}: {
  children: ReactNode;
  /** En az bir filtre varsayılandan farklı mı? */
  dirty: boolean;
  onReset: () => void;
  /** Satırın sağ ucundaki sabit kontroller (görünüm anahtarı, dışa aktar). */
  trailing?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {children}
      {dirty && (
        <Button variant="ghost" size="sm" onClick={onReset} className="text-ink-3">
          <X strokeWidth={1.75} />
          Sıfırla
        </Button>
      )}
      {trailing !== undefined && <div className="ml-auto flex items-center gap-2">{trailing}</div>}
    </div>
  );
}
