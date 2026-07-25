import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Rozet — DESIGN.md §8.4.
 *
 * Yükseklik 22px · padding 2px 8px · radius 6px · 12px/500.
 * **Pill (999px) DEĞİL** — tablo içinde pill amatör durur (§8.4).
 * Renk tek başına anlam taşımaz; metin her zaman yazılır (§12).
 */
const badgeVariants = cva(
  [
    "inline-flex h-[22px] w-fit shrink-0 select-none items-center gap-1.5",
    "rounded-sm px-2 text-xs font-medium whitespace-nowrap",
    "[&>svg]:pointer-events-none [&>svg]:size-3",
  ].join(" "),
  {
    variants: {
      tone: {
        neutral: "bg-surface-2 text-ink-2",
        success: "bg-success-weak text-success",
        warning: "bg-warning-weak text-warning",
        danger: "bg-danger-weak text-danger",
        info: "bg-info-weak text-info",
        /** Makine çıkarımı değil, insan kararı: mürekkep dolu rozet. */
        ink: "bg-accent text-ink-on-accent",
        outline: "border border-border text-ink-2",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

type BadgeProps = React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & {
    asChild?: boolean;
    /** 6px durum noktası — yalnız *durum* rozetlerinde, etiketlerde değil. */
    dot?: boolean;
  };

function Badge({
  className,
  tone,
  dot = false,
  asChild = false,
  children,
  ...props
}: BadgeProps) {
  const Comp = asChild ? Slot.Root : "span";
  return (
    <Comp data-slot="badge" className={cn(badgeVariants({ tone }), className)} {...props}>
      {dot && <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-current" />}
      {children}
    </Comp>
  );
}

export { Badge, badgeVariants };
