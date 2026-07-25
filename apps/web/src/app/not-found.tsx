import { FileSearch } from "lucide-react";
import Link from "next/link";

import { BrandLockup } from "@/components/auth/auth-layout";
import { Button } from "@/components/ui/button";

/** 404 — DESIGN.md §10.5: dönüş yolu ver, kullanıcıyı boşlukta bırakma. */
export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-canvas px-5 py-10">
      <div className="w-full max-w-[440px]">
        <BrandLockup />
        <div className="mt-6 rounded-lg border border-border bg-surface p-6 text-center">
          <span className="mx-auto grid size-10 place-items-center rounded-md bg-surface-2">
            <FileSearch aria-hidden className="size-5 text-ink-3" strokeWidth={1.5} />
          </span>
          <h1 className="mt-4 font-display text-xl font-semibold text-ink-1">Sayfa bulunamadı</h1>
          <p className="mt-1.5 text-sm text-ink-2">
            Bağlantı taşınmış ya da ihale silinmiş olabilir. Panelden devam edebilirsiniz.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <Button asChild>
              <Link href="/panel">Panele git</Link>
            </Button>
            <Button asChild variant="secondary">
              <Link href="/tenders">İhalelerim</Link>
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
