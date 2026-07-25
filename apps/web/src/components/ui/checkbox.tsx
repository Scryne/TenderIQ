"use client";

import { Check } from "lucide-react";
import { Checkbox as CheckboxPrimitive } from "radix-ui";
import type * as React from "react";

import { cn } from "@/lib/utils";

/** Onay kutusu — 16px, radius 4px, işaretliyken mürekkep dolgu (§8.19). */
function Checkbox({
  className,
  ...props
}: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer size-4 shrink-0 rounded-[4px] border border-border-strong bg-surface",
        "transition-colors duration-[120ms] ease-out",
        "hover:border-ink-2",
        "data-[state=checked]:border-accent data-[state=checked]:bg-accent data-[state=checked]:text-ink-on-accent",
        "data-[state=indeterminate]:border-accent data-[state=indeterminate]:bg-accent data-[state=indeterminate]:text-ink-on-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className="grid place-content-center text-current"
      >
        {props.checked === "indeterminate" ? (
          <span aria-hidden className="block h-0.5 w-2 rounded-full bg-current" />
        ) : (
          <Check className="size-3" strokeWidth={3} />
        )}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export { Checkbox };
