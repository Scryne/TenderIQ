"use client";

import { useEffect, useState } from "react";

/** SSE `status` event'inin taşıdığı anlık görüntü (backend `_tender_snapshot`). */
export type TenderSnapshot = {
  tender: { id: string; status: string };
  documents: {
    id: string;
    filename: string;
    status: string;
    job: {
      id: string;
      status: string;
      attempts: number;
      error_message: string | null;
    } | null;
  }[];
};

const RECONNECT_DELAY_MS = 3000;

/**
 * İhalenin canlı durum akışına (SSE) bağlanır; kopunca kendini yeniden bağlar.
 *
 * Kimlik doğrulama aynı-origin proxy + httpOnly cookie ile olur (EventSource
 * başlık taşıyamaz).
 */
export function useTenderStream(tenderId: string): {
  snapshot: TenderSnapshot | null;
  connected: boolean;
} {
  const [snapshot, setSnapshot] = useState<TenderSnapshot | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let source: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let disposed = false;

    const connect = () => {
      source = new EventSource(`/api/v1/tenders/${tenderId}/stream`);
      source.addEventListener("status", (event) => {
        setSnapshot(JSON.parse((event as MessageEvent<string>).data) as TenderSnapshot);
      });
      source.addEventListener("not_found", () => {
        setConnected(false);
        source?.close();
      });
      source.onopen = () => setConnected(true);
      source.onerror = () => {
        // EventSource bazı hatalarda kendini toparlayamaz; kapatıp yeniden kur.
        setConnected(false);
        source?.close();
        if (!disposed) {
          retryTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      source?.close();
    };
  }, [tenderId]);

  return { snapshot, connected };
}
