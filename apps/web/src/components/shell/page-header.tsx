import type { ReactNode } from "react";

/**
 * Sayfa başlığı (DESIGN §7.3): başlık + tek satır bağlam solda, eylem kümesi
 * sağda. Başlık tipi `title-page` (22/28 · 600) ölçüsündedir.
 */
export function PageHeader({
  title,
  context,
  actions,
}: {
  title: ReactNode;
  context?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-[22px] font-semibold leading-7 tracking-tight text-ink-1">{title}</h1>
        {context !== undefined && <p className="mt-1 text-sm text-ink-2">{context}</p>}
      </div>
      {actions !== undefined && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
