import { cn } from "@/lib/utils";

/**
 * Skeleton — DESIGN.md §10.3.
 *
 * Spinner değil skeleton; gerçek içeriğin şeklini taklit eder. Animasyon
 * `shimmer` DEĞİL (2019 estetiği), opaklık nabzı 1.5s.
 */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden
      className={cn("animate-skeleton rounded-sm bg-surface-2", className)}
      {...props}
    />
  );
}

export { Skeleton };
