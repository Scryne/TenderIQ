"use client";

import { useSyncExternalStore } from "react";

/**
 * Dakika çözünürlüğünde "şimdi" — render'da `Date.now()` çağırmanın saf karşılığı.
 *
 * Render içinde `Date.now()` her render'da farklı sonuç verir (React'in saflık
 * kuralı, react-hooks 7 `purity`). Saat burada dış bir depo olarak okunur:
 * değer dakikaya yuvarlanmış bir SAYI olduğu için aynı dakika içindeki her okuma
 * aynıdır (`Object.is` kararlı), abone olan bileşenler dakikada bir tazelenir —
 * açık kalan bir panelde "3 gün kaldı" gece yarısını geçince kendiliğinden düzelir.
 *
 * Gün hesapları için yeterli; saniye hassasiyeti gereken bir yerde kullanılmamalı.
 */
const MINUTE = 60_000;

function readNow(): number {
  return Math.floor(Date.now() / MINUTE) * MINUTE;
}

function subscribe(onChange: () => void): () => void {
  const timer = window.setInterval(onChange, MINUTE);
  return () => window.clearInterval(timer);
}

export function useNow(): Date {
  const now = useSyncExternalStore(subscribe, readNow, readNow);
  return new Date(now);
}
