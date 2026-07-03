import Link from "next/link";

import { SystemStatus } from "@/components/system-status";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-8 p-8">
      <div className="space-y-3 text-center">
        <h1 className="text-4xl font-bold tracking-tight">TenderIQ</h1>
        <p className="text-balance text-muted-foreground">
          Yapay zekâ destekli ihale ve RFP analiz platformu — şartnameleri dakikalar içinde,
          kaynağına kadar izlenebilir biçimde analiz eder.
        </p>
      </div>

      <SystemStatus />

      <Link href="/login" className={cn(buttonVariants({ size: "lg" }))}>
        Giriş yap
      </Link>
    </main>
  );
}
