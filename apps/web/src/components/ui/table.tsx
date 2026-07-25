import type * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Veri tablosu — DESIGN.md §8.3.
 *
 * Satır 48px (iki satırlı hücre) · **zebra şerit YOK**, ayırıcı 1px alt
 * kenarlık · hover `surface-2` 100ms · başlık sticky + `surface-2` zemin,
 * 11px/500/+0.04em/`ink-3`. Sayısal sütun sağa hizalı ve `tabular-nums`
 * (gövde zaten `tabular-nums`; `TableCell numeric` hizalamayı verir).
 */
function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div data-slot="table-container" className="scroll-slim relative w-full overflow-x-auto">
      <table
        data-slot="table"
        className={cn("w-full caption-bottom border-collapse text-sm", className)}
        {...props}
      />
    </div>
  );
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("sticky top-0 z-10 bg-surface-2", className)}
      {...props}
    />
  );
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("[&_tr:last-child]:border-b-0", className)}
      {...props}
    />
  );
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn("border-t border-border bg-surface-2 font-medium", className)}
      {...props}
    />
  );
}

function TableRow({
  className,
  interactive = false,
  ...props
}: React.ComponentProps<"tr"> & { interactive?: boolean }) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "border-b border-border transition-colors duration-100",
        interactive && "cursor-pointer hover:bg-surface-2",
        "data-[state=selected]:bg-surface-2",
        className,
      )}
      {...props}
    />
  );
}

function TableHead({
  className,
  numeric = false,
  ...props
}: React.ComponentProps<"th"> & { numeric?: boolean }) {
  return (
    <th
      data-slot="table-head"
      scope="col"
      className={cn(
        "h-9 px-3 align-middle text-[11px] leading-[14px] font-semibold tracking-[0.04em] whitespace-nowrap text-ink-3",
        "border-b border-border",
        numeric ? "text-right" : "text-left",
        className,
      )}
      {...props}
    />
  );
}

function TableCell({
  className,
  numeric = false,
  ...props
}: React.ComponentProps<"td"> & { numeric?: boolean }) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "px-3 py-3 align-middle text-sm text-ink-1",
        numeric && "text-right font-mono",
        className,
      )}
      {...props}
    />
  );
}

function TableCaption({ className, ...props }: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-3 text-xs text-ink-3", className)}
      {...props}
    />
  );
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
};
