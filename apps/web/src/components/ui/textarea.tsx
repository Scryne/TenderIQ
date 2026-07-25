import type * as React from "react";

import { cn } from "@/lib/utils";

/** Çok satırlı alan — Input ile aynı sözleşme (DESIGN.md §8.6). */
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "field-sizing-content min-h-16 w-full rounded-sm border border-border-strong bg-surface px-3 py-2 text-base text-ink-1",
        "transition-[border-color,box-shadow] duration-[120ms] ease-out",
        "placeholder:text-ink-3",
        "focus-visible:border-ink-1 focus-visible:ring-[3px] focus-visible:ring-ink-1/12 focus-visible:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-danger aria-invalid:focus-visible:ring-danger/15",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
