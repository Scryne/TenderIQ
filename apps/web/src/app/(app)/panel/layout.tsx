import type { Metadata } from "next";
import type { ReactNode } from "react";

// Sayfa istemci bileşeni olduğu için `metadata` buradan verilir; kök şablon "· TenderIQ" ekler.
export const metadata: Metadata = { title: "Panel" };

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
