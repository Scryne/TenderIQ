import type * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Kart — DESIGN.md §5.5 + §9.2 "dengeli" yoğunluk.
 *
 * radius 10px · 1px kenarlık · **gölge YOK**. Gölge yalnız yüzeyin üstünde
 * yüzen şeyler içindir (dropdown, modal, toast). Her karta gölge = ucuz
 * görünüm (§5.5, §13.5). Padding 20px; bölümler `border-t` ile ayrılır.
 */
function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card"
      className={cn(
        "flex flex-col rounded-lg border border-border bg-surface text-ink-1",
        className,
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "flex items-start justify-between gap-3 px-5 pt-5 pb-4",
        "[&:has(+[data-slot=card-content])]:pb-0",
        className,
      )}
      {...props}
    />
  );
}

/**
 * Kart başlığı.
 *
 * `as` ile başlık seviyesi seçilir ve VARSAYILAN `h3`tür: kartlar çoğu yerde
 * bir `SectionHeader` (h2) altında yaşar. Ama kart doğrudan sayfa başlığının
 * (h1) altındaysa `h3` bir seviye ATLAR — ekran okuyucu kullanıcısı başlık
 * listesinde eksik bir kademe görür (Lighthouse `heading-order`; 2026-07-30'da
 * `/usage`, `/settings`, `/capability`te ölçüldü). O kartlarda `as="h2"`
 * verilir.
 *
 * Görünüm seviyeden BAĞIMSIZDIR (sınıflar sabit) — yani seviyeyi düzeltmek
 * tasarımı değiştirmez.
 */
function CardTitle({
  className,
  as: Heading = "h3",
  ...props
}: React.ComponentProps<"h3"> & { as?: "h2" | "h3" | "h4" }) {
  return (
    <Heading
      data-slot="card-title"
      className={cn("font-display text-lg leading-6 font-semibold text-ink-1", className)}
      {...props}
    />
  );
}

function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="card-description"
      className={cn("mt-1 max-w-[68ch] text-sm text-ink-2", className)}
      {...props}
    />
  );
}

/** Başlık satırının sağ ucundaki kontroller (segment, menü, filtre). */
function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn("flex shrink-0 items-center gap-2", className)}
      {...props}
    />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn("p-5", className)} {...props} />;
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn("flex items-center gap-2 border-t border-border px-5 py-3.5", className)}
      {...props}
    />
  );
}

export { Card, CardHeader, CardFooter, CardTitle, CardAction, CardDescription, CardContent };
