"use client";

import { useSyncExternalStore } from "react";

/**
 * Kenar çubuğu daraltma tercihi — oturumlar arasında `localStorage`da korunur.
 *
 * Eskiden değer bir efektte okunup state'e yazılıyordu (react-hooks 7
 * `set-state-in-effect`). Tercih aslında tarayıcıda yaşayan DIŞ bir durum, o
 * yüzden `useSyncExternalStore` ile okunur: sunucu render'ı ve hydration
 * `false` (genişletilmiş) görür, hemen ardından gerçek değer uygulanır —
 * eski davranışla aynı, hydration uyumsuzluğu yok. Yan kazanç: başka sekmede
 * değişen tercih `storage` olayıyla bu sekmeye de yansır.
 */
const KEY = "tiq.sidebar";
const listeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  const onStorage = (event: StorageEvent) => {
    if (event.key === KEY) onChange();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onStorage);
  };
}

function read(): boolean {
  return window.localStorage.getItem(KEY) === "collapsed";
}

export function useSidebarCollapsed(): [boolean, () => void] {
  const collapsed = useSyncExternalStore(subscribe, read, () => false);

  function toggle() {
    window.localStorage.setItem(KEY, collapsed ? "expanded" : "collapsed");
    // `storage` olayı yalnız DİĞER sekmelere gider; bu sekmedeki aboneler elle uyarılır.
    for (const listener of listeners) listener();
  }

  return [collapsed, toggle];
}
