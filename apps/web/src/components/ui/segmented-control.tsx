"use client";

import type * as React from "react";

import { tabsListVariants, tabsTriggerClassName } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

/**
 * Segment kontrolü — DESIGN.md §8.11.
 *
 * ## Neden `Tabs` değil
 *
 * Sekme bir PANELİ açar; segment aynı veriyi farklı gösterir (§8.11 bunu açıkça
 * ayırıyor). Bu ayrım yalnız kavramsal değil: `Tabs`ı panel olmadan kullanmak
 * BOZUK ARIA üretiyordu. Radix her tetikleyiciye `role="tab"` ve
 * `aria-controls="radix-…-content-…"` yazıyor; panel hiç render edilmediği için
 * o kimlik DOM'da yok. Sonuç:
 *
 * - `aria-controls` var olmayan bir öğeye işaret ediyordu (Lighthouse
 *   `aria-valid-attr-value` — 2026-07-30'da `/tenders`te ölçüldü);
 * - ekran okuyucuya "sekme listesi" duyurulup açılacak panel bulunamıyordu,
 *   yani kullanıcıya yanlış bir zihinsel model veriliyordu.
 *
 * Burada semantik `aria-pressed` taşıyan bir düğme grubudur: filtre düğmeleri
 * için yerleşik ve doğru kalıp. Radio grubu yerine bu seçildi çünkü radio
 * semantiği ok tuşlarıyla gezinme sözleşmesi getirir (ve `Tab` ile öğeler arası
 * geçişi kapatır); düğme grubu klavyede zaten beklendiği gibi çalışır.
 *
 * Görünüm sekmeyle birebir aynı: sınıflar `tabs.tsx`ten gelir, kopyalanmaz.
 */
export type SegmentedOption<T extends string> = {
  value: T;
  /** Görünen etiket; sayaç gibi ek içerik de olabilir. */
  label: React.ReactNode;
};

export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
  label,
  className,
  listClassName,
  optionClassName,
}: {
  value: T;
  onValueChange: (value: T) => void;
  options: readonly SegmentedOption<T>[];
  /** Grubun erişilebilir adı — ekran okuyucu neyi filtrelediğini söylemeli. */
  label: string;
  className?: string;
  listClassName?: string;
  /** Her düğmeye eklenen sınıflar (ör. eşit genişlikte dağıtmak için). */
  optionClassName?: string;
}) {
  return (
    <div className={cn("flex min-w-0 max-w-full flex-col", className)}>
      <div
        role="group"
        aria-label={label}
        // `data-variant` + `group/tabs-list`: tetikleyici sınıfları bu grup
        // seçicisine bakıyor (bkz. `tabsTriggerClassName`).
        data-variant="segment"
        data-slot="segmented-control"
        className={cn(tabsListVariants({ variant: "segment" }), listClassName)}
      >
        {options.map((option) => {
          const active = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={active}
              data-state={active ? "active" : "inactive"}
              data-slot="tabs-trigger"
              onClick={() => onValueChange(option.value)}
              className={cn(tabsTriggerClassName, optionClassName)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
