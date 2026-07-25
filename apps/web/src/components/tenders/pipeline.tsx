import { AlertTriangle, Check, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { PIPELINE_STEPS } from "@/lib/tenders";
import { cn } from "@/lib/utils";

/**
 * İşleme hattı göstergesi.
 *
 * Sohbet kutusu dizisi değil, bir ilerleme çizgisi: tamamlanan adımlar
 * mürekkep dolu, aktif adım halkalı ve nabızlı, bekleyenler hairline.
 * Kullanıcının tek sorusu "nerede kaldı, ne kadar sürer" — o yüzden aktif
 * adımın ne yaptığı ayrıca bir cümleyle yazılır.
 */
export function PipelineProgress({
  status,
  errorMessage,
  attempts,
  onRetry,
  retrying = false,
  className,
}: {
  status: string;
  errorMessage?: string | null;
  attempts?: number;
  /** Başarısız işi yeniden kuyruğa atar (`POST /jobs/{id}/retry`). */
  onRetry?: () => void;
  retrying?: boolean;
  className?: string;
}) {
  if (status === "failed") {
    return (
      <div
        role="alert"
        className={cn(
          "flex flex-wrap items-start gap-3 rounded-sm border border-danger/30 bg-danger-weak px-3 py-2.5",
          className,
        )}
      >
        <AlertTriangle
          aria-hidden
          className="mt-0.5 size-4 shrink-0 text-danger"
          strokeWidth={1.75}
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink-1">İşleme tamamlanamadı</p>
          <p className="mt-0.5 text-sm text-ink-2">
            {errorMessage != null && errorMessage !== ""
              ? errorMessage
              : "Dosya okunamadı. Şifresiz ve bozulmamış bir kopyayla yeniden yükleyin."}
          </p>
          {attempts != null && attempts > 1 && (
            <p className="mt-1 font-mono text-[11px] text-ink-3">{attempts} deneme yapıldı</p>
          )}
        </div>
        {onRetry !== undefined && (
          <Button variant="secondary" size="sm" loading={retrying} onClick={onRetry}>
            <RotateCw strokeWidth={1.75} />
            Yeniden dene
          </Button>
        )}
      </div>
    );
  }

  const activeIndex = PIPELINE_STEPS.findIndex((step) => step.key === status);
  const done = status === "review_ready";
  const active = done ? PIPELINE_STEPS.length - 1 : activeIndex;

  return (
    <div className={cn("min-w-0 max-w-xl", className)}>
      <ol className="flex items-center gap-0">
        {PIPELINE_STEPS.map((step, index) => {
          const isDone = index < active || done;
          const isActive = index === active && !done;
          return (
            <li key={step.key} className="flex min-w-0 flex-1 items-center last:flex-none">
              <span className="flex shrink-0 flex-col items-center gap-1.5">
                <span
                  aria-hidden
                  className={cn(
                    "grid size-5 place-items-center rounded-full border transition-colors",
                    isDone && "border-accent bg-accent text-ink-on-accent",
                    isActive && "animate-live border-accent bg-surface",
                    !isDone && !isActive && "border-border-strong bg-surface",
                  )}
                >
                  {isDone ? (
                    <Check className="size-3" strokeWidth={3} />
                  ) : (
                    <span
                      className={cn(
                        "size-1.5 rounded-full",
                        isActive ? "bg-accent" : "bg-border-strong",
                      )}
                    />
                  )}
                </span>
                <span
                  className={cn(
                    "hidden text-[11px] leading-4 whitespace-nowrap sm:block",
                    isDone || isActive ? "font-medium text-ink-1" : "text-ink-3",
                  )}
                >
                  {step.label}
                </span>
              </span>
              {index < PIPELINE_STEPS.length - 1 && (
                <span
                  aria-hidden
                  className={cn(
                    "mx-1.5 mb-5 h-px min-w-3 flex-1 sm:mb-5",
                    isDone ? "bg-accent" : "bg-border",
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>
      <p className="mt-2 text-xs text-ink-2 sm:mt-1">
        {done ? PIPELINE_STEPS[PIPELINE_STEPS.length - 1].detail : PIPELINE_STEPS[active]?.detail}
      </p>
    </div>
  );
}
