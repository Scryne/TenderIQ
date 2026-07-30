"use client";

import { cva, type VariantProps } from "class-variance-authority";
import { Tabs as TabsPrimitive } from "radix-ui";
import type * as React from "react";

import { cn } from "@/lib/utils";

/**
 * İki kullanım, tek primitive:
 *
 * - `variant="segment"` — DESIGN.md §8.11 segment kontrolü. AYNI veriyi farklı
 *   gösteren 2-4 seçenek. Konteyner `surface-2`, 3px iç padding, seçili öğe
 *   `surface` + `shadow-sm`.
 * - `variant="underline"` — sayfa bölümü değiştiren gerçek sekme (§9.4).
 *   Seçili öğede 2px mürekkep alt çizgi.
 *
 * İkisini aynı ekranda karıştırma; sekme ile segment farklı işlerdir.
 */
function Tabs({
  className,
  orientation = "horizontal",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      orientation={orientation}
      // `min-w-0` şart: esnek bir kapta flex öğesinin varsayılan
      // `min-width: auto` değeri içerikten küçülmesini engeller ve TabsList'in
      // `overflow-x-auto` kuralı devreye giremeden sayfa yatay kayar.
      className={cn("group/tabs flex min-w-0 max-w-full flex-col gap-4", className)}
      {...props}
    />
  );
}

const tabsListVariants = cva("group/tabs-list inline-flex items-center", {
  variants: {
    variant: {
      // Dar ekranda çok seçenekli segment satırı sarmaz ve sayfayı yatay
      // kaydırmaya zorlar (375px'de ölçüldü: 489 > 375). Kaydırma kontrolün
      // KENDİ içinde kalır; sayfa gövdesi asla yatay kaymaz (§7.4, §15).
      segment: "h-8 max-w-full gap-0 overflow-x-auto rounded-md bg-surface-2 p-[3px] scroll-slim",
      underline: "h-9 max-w-full gap-4 overflow-x-auto border-b border-border scroll-slim",
      vertical: "h-fit w-full flex-col items-stretch gap-0.5",
    },
  },
  defaultVariants: { variant: "segment" },
});

function TabsList({
  className,
  variant = "segment",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> & VariantProps<typeof tabsListVariants>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={variant}
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  );
}

/**
 * Tetikleyici sınıfları — `SegmentedControl` de bunu kullanır.
 *
 * Ayrı bir bileşen aynı sınıfları KOPYALASA görünüm zamanla sessizce ayrışırdı;
 * segment kontrolünün sekmeyle birebir aynı görünmesi bir tasarım gereğidir
 * (DESIGN.md §8.11). Bu yüzden tek kaynak.
 */
const tabsTriggerClassName = cn(
  "relative inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap",
  "text-sm font-medium text-ink-2 transition-colors duration-[120ms] ease-out",
  "disabled:pointer-events-none disabled:opacity-50",
  "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  // segment
  "group-data-[variant=segment]/tabs-list:h-full group-data-[variant=segment]/tabs-list:rounded-sm group-data-[variant=segment]/tabs-list:px-3",
  "group-data-[variant=segment]/tabs-list:data-[state=active]:bg-surface group-data-[variant=segment]/tabs-list:data-[state=active]:text-ink-1 group-data-[variant=segment]/tabs-list:data-[state=active]:shadow-sm",
  // underline — 2px mürekkep ray, alt kenarın üstünde
  "group-data-[variant=underline]/tabs-list:h-full group-data-[variant=underline]/tabs-list:px-0.5",
  "group-data-[variant=underline]/tabs-list:after:absolute group-data-[variant=underline]/tabs-list:after:inset-x-0 group-data-[variant=underline]/tabs-list:after:-bottom-px group-data-[variant=underline]/tabs-list:after:h-0.5 group-data-[variant=underline]/tabs-list:after:rounded-full group-data-[variant=underline]/tabs-list:after:bg-accent group-data-[variant=underline]/tabs-list:after:opacity-0",
  "group-data-[variant=underline]/tabs-list:data-[state=active]:text-ink-1 group-data-[variant=underline]/tabs-list:data-[state=active]:after:opacity-100",
  // vertical (ayarlar sol sekmesi §9.7)
  "group-data-[variant=vertical]/tabs-list:h-9 group-data-[variant=vertical]/tabs-list:justify-start group-data-[variant=vertical]/tabs-list:rounded-sm group-data-[variant=vertical]/tabs-list:px-2.5",
  "group-data-[variant=vertical]/tabs-list:data-[state=active]:bg-surface-2 group-data-[variant=vertical]/tabs-list:data-[state=active]:text-ink-1",
  "hover:text-ink-1",
);

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(tabsTriggerClassName, className)}
      {...props}
    />
  );
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("flex-1 focus-visible:outline-none", className)}
      {...props}
    />
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants, tabsTriggerClassName };
