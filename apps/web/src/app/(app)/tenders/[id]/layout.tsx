import type { Metadata } from "next";
import type { ReactNode } from "react";

// Sayfa istemci bileşeni olduğu için `metadata` buradan verilir; kök şablon "· TenderIQ" ekler.
export const metadata: Metadata = { title: { default: "İhale detayı", template: "%s · TenderIQ" } };

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
