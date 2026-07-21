"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// pdfjs-dist, react-pdf'in sabitlediği sürümle birebir aynı pin'lenir
// (package.json); worker/API sürüm uyuşmazlığı çalışma anında hata üretir.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export type HighlightBox = { x0: number; y0: number; x1: number; y1: number };

/** Vurgu kutusu bbox'tan biraz taşar — satır kenarları kırpılmasın (nokta cinsi). */
const HIGHLIGHT_PADDING_PT = 3;

/**
 * PDF önizleme + kaynak vurgusu (Sprint 3.1, skill: document-preview-highlight).
 *
 * Performans: yüzlerce sayfalık şartnamede tüm sayfalar değil, YALNIZ aktif
 * sayfa render edilir; bulguya tıklamak sayfayı değiştirir. bbox nokta (pt)
 * cinsinden TOPLEFT origin'dir (ParsedElement sözleşmesi); PDF.js'in scale-1
 * viewport'u da pt olduğundan ölçek = renderGenişliği / viewportGenişliği.
 *
 * Dosya, imzalı URL'den TEK bir yalın GET ile indirilir (özel başlık yok →
 * CORS preflight yok; R2 kuralı yalnız PUT/GET/HEAD + content-type açar).
 */
export function PdfViewer({
  fileUrl,
  page,
  onPageChange,
  highlight,
  highlightKey,
}: {
  fileUrl: string;
  page: number;
  onPageChange: (page: number) => void;
  highlight: HighlightBox | null;
  /** Aynı kutuya yeniden tıklanınca da kaydırmayı tetikler. */
  highlightKey: string | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number | null>(null);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageViewport, setPageViewport] = useState<{ width: number; height: number } | null>(null);

  // İmzalı URL'in içeriği bir kez indirilir; PDF.js'e blob URL verilir (Range
  // isteği yok → CORS başlık kısıtına takılmaz). URL değişince eskisi bırakılır.
  const file = useQuery({
    queryKey: ["pdf-blob", fileUrl],
    staleTime: Infinity,
    queryFn: async () => {
      const response = await fetch(fileUrl);
      if (!response.ok) throw new Error("Doküman indirilemedi.");
      return response.blob();
    },
  });
  const objectUrl = useMemo(
    () => (file.data !== undefined ? URL.createObjectURL(file.data) : null),
    [file.data],
  );
  useEffect(() => {
    return () => {
      if (objectUrl !== null) URL.revokeObjectURL(objectUrl);
    };
  }, [objectUrl]);

  useEffect(() => {
    const element = containerRef.current;
    if (element === null) return;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width !== undefined && width > 0) setContainerWidth(width);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // Yeni vurgu geldiğinde kutu görünür alana getirilir.
  useEffect(() => {
    if (highlightKey === null) return;
    const id = requestAnimationFrame(() => {
      highlightRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    });
    return () => cancelAnimationFrame(id);
  }, [highlightKey, pageViewport]);

  const renderWidth = containerWidth !== null ? Math.max(containerWidth - 2, 200) : undefined;
  const scale =
    pageViewport !== null && renderWidth !== undefined ? renderWidth / pageViewport.width : null;

  const overlay =
    highlight !== null && scale !== null ? (
      <div
        ref={highlightRef}
        aria-hidden
        className="pointer-events-none absolute rounded-[3px] border-[1.5px] border-brand bg-brand/15"
        style={{
          left: (highlight.x0 - HIGHLIGHT_PADDING_PT) * scale,
          top: (highlight.y0 - HIGHLIGHT_PADDING_PT) * scale,
          width: (highlight.x1 - highlight.x0 + 2 * HIGHLIGHT_PADDING_PT) * scale,
          height: (highlight.y1 - highlight.y0 + 2 * HIGHLIGHT_PADDING_PT) * scale,
        }}
      />
    ) : null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-center gap-2 border-b bg-surface px-3 py-2">
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          aria-label="Önceki sayfa"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft className="size-4" strokeWidth={1.5} />
        </Button>
        <span className="font-mono text-xs text-ink-2">
          {page} / {numPages ?? "—"}
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          aria-label="Sonraki sayfa"
          disabled={numPages === null || page >= numPages}
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRight className="size-4" strokeWidth={1.5} />
        </Button>
      </div>

      <div ref={containerRef} className="min-h-0 flex-1 overflow-auto bg-surface-2/60 p-0">
        {file.isPending && (
          <div className="p-4">
            <Skeleton className="h-[70vh] w-full" />
          </div>
        )}
        {file.isError && (
          <p className="p-6 text-sm text-danger">
            Doküman indirilemedi. Sayfayı yenileyip yeniden deneyin.
          </p>
        )}
        {objectUrl !== null && (
          <Document
            file={objectUrl}
            onLoadSuccess={(pdf) => setNumPages(pdf.numPages)}
            loading={
              <div className="p-4">
                <Skeleton className="h-[70vh] w-full" />
              </div>
            }
            error={<p className="p-6 text-sm text-danger">PDF görüntülenemedi.</p>}
          >
            <div className="relative mx-auto w-fit shadow-rest">
              <Page
                pageNumber={page}
                width={renderWidth}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                onLoadSuccess={(loadedPage) => {
                  const viewport = loadedPage.getViewport({ scale: 1 });
                  setPageViewport({ width: viewport.width, height: viewport.height });
                }}
              />
              {overlay}
            </div>
          </Document>
        )}
      </div>
    </div>
  );
}
