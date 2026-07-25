import type * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Form alanı — DESIGN.md §8.6.
 *
 * 36px · 1px `border-strong` (WCAG 1.4.11 için 3:1) · radius 6px.
 * Focus: kenarlık mürekkebe döner + 3px halka. Hata: `aria-invalid` ile
 * kenarlık `danger`; hata METNİ alan altında ayrıca yazılır — renk tek
 * başına bilgi taşımaz (§12).
 */
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-9 w-full min-w-0 rounded-sm border border-border-strong bg-surface px-3 text-base text-ink-1",
        "transition-[border-color,box-shadow] duration-[120ms] ease-out",
        "placeholder:text-ink-3",
        "focus-visible:border-ink-1 focus-visible:ring-[3px] focus-visible:ring-ink-1/12 focus-visible:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-danger aria-invalid:focus-visible:ring-danger/15",
        "file:mr-3 file:h-7 file:rounded-sm file:border-0 file:bg-surface-2 file:px-2.5 file:text-sm file:font-medium file:text-ink-1",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
