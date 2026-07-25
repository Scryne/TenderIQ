import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** Beş kanonik durum tonu — altıncı renk icat edilmez (DESIGN.md §5.2). */
export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

/**
 * Durum rozeti — DESIGN.md §8.4.
 *
 * Adı tarihsel olarak "pill" ama **pill değildir**: radius 6px. Tablo içinde
 * 999px rozet amatör durur (§8.4). Metin her zaman yazılır; renk tek başına
 * bilgi taşımaz (§12).
 */
export function StatusPill({
  tone,
  label,
  className,
}: {
  tone: StatusTone;
  label: string;
  className?: string;
}) {
  return (
    <Badge tone={tone} dot className={cn("shrink-0", className)}>
      {label}
    </Badge>
  );
}
