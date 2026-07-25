import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { Slot } from "radix-ui";
import type * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Buton — DESIGN.md §8.5.
 *
 * Yükseklik sm 32 · md 36 (panel varsayılanı) · lg 40. Metin 14px/500, ASLA
 * uppercase (§13.2 ve Ek B.3: CSS uppercase Türkçe'de "i"→"I" yapar).
 * `disabled` yalnız opaklık düşürür, renk değiştirmez. Focus halkası global
 * `:focus-visible` kuralından gelir — burada `outline-none` yazılmaz (§12).
 */
const buttonVariants = cva(
  [
    "relative inline-flex shrink-0 select-none items-center justify-center gap-1.5",
    "whitespace-nowrap rounded-sm font-medium",
    "transition-colors duration-[120ms] ease-out",
    "disabled:pointer-events-none disabled:opacity-50",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
    "[&_svg:not([class*='size-'])]:size-4",
  ].join(" "),
  {
    variants: {
      variant: {
        // Sayfada TEK tane (§8.5). Mürekkep zemin, kâğıt metin.
        primary: "bg-accent text-ink-on-accent hover:bg-accent-hover",
        // Yan eylemler
        secondary:
          "border border-border-strong bg-surface text-ink-1 hover:bg-surface-2",
        // Tablo içi, ikon butonları
        ghost: "text-ink-2 hover:bg-hover hover:text-ink-1",
        // Yalnız yıkıcı eylem
        danger: "bg-danger text-white hover:opacity-90",
        // Yıkıcı ama ikincil (menü içi)
        "danger-ghost": "text-danger hover:bg-danger-weak",
        link: "text-ink-1 underline decoration-border-strong underline-offset-4 hover:decoration-ink-1",
      },
      size: {
        xs: "h-6 gap-1 px-2 text-xs [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 px-3 text-sm",
        md: "h-9 px-3.5 text-base",
        lg: "h-10 px-5 text-base",
        "icon-xs": "size-6 [&_svg:not([class*='size-'])]:size-3.5",
        "icon-sm": "size-8",
        icon: "size-9",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
    /**
     * Yükleniyor: metin yerinde kalır ve buton genişliği DEĞİŞMEZ (§8.5 —
     * layout zıplaması yasak). Etiket görünmez olur, spinner üstüne biner.
     */
    loading?: boolean;
  };

function Button({
  className,
  variant,
  size,
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button";

  if (asChild) {
    return (
      <Comp
        data-slot="button"
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      >
        {children}
      </Comp>
    );
  }

  return (
    <button
      data-slot="button"
      data-loading={loading ? "" : undefined}
      disabled={disabled === true || loading}
      aria-busy={loading || undefined}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    >
      {loading && (
        <Loader2
          aria-hidden
          className="absolute size-4 animate-spin"
          strokeWidth={2}
        />
      )}
      <span
        className={cn(
          "inline-flex items-center gap-1.5",
          loading && "invisible",
        )}
      >
        {children}
      </span>
    </button>
  );
}

export { Button, buttonVariants };
