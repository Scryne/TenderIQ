import { CircleAlert, Info, TriangleAlert, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════════════════════
 * SATIR İÇİ UYARI BLOĞU — tek anatomi, üç ton.
 *
 * Bu bileşen `subscription-card.tsx` içindeki yerel `Notice`ten çıkarıldı;
 * `account-section` ve `legal-shell`teki kalıbın aynısıdır
 * (`border-<ton>/30` + `bg-<ton>-weak` + `rounded-sm`).
 *
 * **Neden paylaşılan:** aynı üründe iki farklı uyarı görünümü, kullanıcının
 * "bu ne kadar ciddi" sorusunu her ekranda yeniden sormasına yol açar. Bütçe
 * tavanı ve yönetici teşhisi ekranları üç ayrı ciddiyet seviyesi taşıyor
 * (bilgi / yaklaşıyor / durdu) — bunları ayırt eden şey ton olmalı, anatomi
 * değil.
 *
 * `ErrorState`/`InlineError` ile karışmasın: onlar bir İSTEĞİN başarısız
 * olduğunu söyler ("yeniden dene"). Bu blok başarıyla dönmüş verinin
 * ANLAMINI söyler — tekrar denemek bir şey değiştirmez.
 * ═══════════════════════════════════════════════════════════════════════════ */

type NoticeTone = "info" | "warning" | "danger";

const SHELL: Record<NoticeTone, string> = {
  info: "border-info/30 bg-info-weak",
  warning: "border-warning/30 bg-warning-weak",
  danger: "border-danger/30 bg-danger-weak",
};

const MARK: Record<NoticeTone, string> = {
  info: "text-info",
  warning: "text-warning",
  danger: "text-danger",
};

const DEFAULT_ICON: Record<NoticeTone, LucideIcon> = {
  info: Info,
  warning: TriangleAlert,
  danger: CircleAlert,
};

export function Notice({
  tone,
  icon,
  children,
  action,
  className,
}: {
  tone: NoticeTone;
  /** Tonun varsayılan ikonunu ezer (ör. bekleyen plan değişiminde takvim). */
  icon?: LucideIcon;
  children: ReactNode;
  /** Kullanıcının bu uyarı hakkında YAPABİLECEĞİ şey; metnin altında durur. */
  action?: ReactNode;
  className?: string;
}) {
  const Icon = icon ?? DEFAULT_ICON[tone];

  return (
    <div className={cn("flex items-start gap-2.5 rounded-sm border px-3 py-2.5", SHELL[tone], className)}>
      <Icon aria-hidden className={cn("mt-0.5 size-4 shrink-0", MARK[tone])} strokeWidth={1.75} />
      <div className="min-w-0 flex-1">
        <p className="max-w-[68ch] text-sm text-ink-2">{children}</p>
        {action !== undefined && <div className="mt-2.5 flex flex-wrap gap-2">{action}</div>}
      </div>
    </div>
  );
}
