import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";

/** Oturumlu uygulama sayfaları — kenar çubuklu kabuk (DESIGN §6.5). */
export default function AppLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
