import { TriangleAlert } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { BrandLockup } from "@/components/auth/auth-layout";
import { buttonVariants } from "@/components/ui/button";
import {
  LEGAL_CONFIG,
  SUB_PROCESSORS,
  missingLegalFields,
} from "@/config/legal.config";
import { cn } from "@/lib/utils";

/** Hukuki sayfalar arası gezinme — her sayfanın altbilgisinde aynı sırayla. */
export const LEGAL_LINKS = [
  { href: "/kvkk", label: "Aydınlatma metni" },
  { href: "/sartlar", label: "Kullanım şartları" },
  { href: "/trust", label: "Güven merkezi" },
  { href: "/dpa", label: "Veri işleme sözleşmesi" },
] as const;

/**
 * Yapılandırmadan gelen bir değeri basar; değer yoksa **göze batan** bir
 * eksik-alan işareti gösterir.
 *
 * Bilinçli olarak dikkat çekicidir: bir hukuki metinde eksik alanın sessizce
 * boş kalması, yanlış bilgi vermekten tehlikelidir çünkü kimse fark etmez.
 * Değerler `config/legal.config.ts`ten okunur; metinlerde sabit yazılmaz.
 */
export function Value({ value, field }: { value?: string; field: string }) {
  if (value !== undefined && value !== "") return <>{value}</>;
  return (
    <span
      title={`legal.config.ts → ${field}`}
      className="rounded-sm bg-warning-weak px-1.5 py-0.5 font-mono text-[13px] text-warning"
    >
      [{field}]
    </span>
  );
}

function LegalHeader() {
  return (
    <header className="border-b border-border bg-canvas">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-6 px-5">
        <BrandLockup />
        <div className="flex items-center gap-2">
          <Link
            href="/login"
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "hidden sm:inline-flex")}
          >
            Giriş yap
          </Link>
          <Link href="/register" className={cn(buttonVariants({ size: "sm" }))}>
            Ücretsiz başla
          </Link>
        </div>
      </div>
    </header>
  );
}

function LegalFooter() {
  return (
    <footer className="border-t border-border bg-canvas">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-8">
        <BrandLockup />
        <nav className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-ink-2">
          {LEGAL_LINKS.map((link) => (
            <Link key={link.href} href={link.href} className="hover:text-ink-1">
              {link.label}
            </Link>
          ))}
        </nav>
        <p className="text-xs text-ink-3">© 2026 TenderIQ</p>
      </div>
    </footer>
  );
}

/**
 * Hukuki/politika sayfası kabuğu.
 *
 * Okunabilir metin bloğu 68 karakterle sınırlıdır (DESIGN.md §7.1) — bu
 * sayfalar baştan sona okunmak için var, tarama için değil.
 */
export type LegalSectionData = { id: string; title: string; body: ReactNode };

export function LegalPage({
  title,
  intro,
  sections,
}: {
  title: string;
  intro: string;
  /**
   * Bölümler **veri olarak** verilir; içindekiler listesi buradan üretilir.
   * JSX çocuk olarak alınsaydı içindekiler elle yazılırdı ve bir hukuki
   * metinde başlık ile içindekiler listesinin ayrışması kabul edilemez.
   */
  sections: LegalSectionData[];
}) {
  // Taslak durumu ELLE ayarlanmaz, veriden türetilir: `draft={false}` yazılabilse
  // bir alan eksikken de yayına alınabilir ve uyarı sessizce kaybolurdu.
  const missing = missingLegalFields();
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-ink-1">
      <LegalHeader />
      <main className="flex-1">
        <div className="mx-auto max-w-6xl px-5 py-12 lg:py-16">
          <div className="max-w-[68ch]">
            <h1 className="font-display text-3xl leading-tight font-semibold tracking-tight text-balance text-ink-1">
              {title}
            </h1>
            <p className="mt-4 text-base leading-relaxed text-ink-2">{intro}</p>
            <p className="mt-4 text-xs text-ink-3">
              Son güncelleme: {LEGAL_CONFIG.lastUpdated}
            </p>

            {missing.length > 0 && (
              <div
                role="note"
                className="mt-8 flex items-start gap-2.5 rounded-sm border border-warning/30 bg-warning-weak px-3 py-2.5"
              >
                <TriangleAlert
                  aria-hidden
                  className="mt-0.5 size-4 shrink-0 text-warning"
                  strokeWidth={1.75}
                />
                <div className="min-w-0 flex-1 text-sm text-ink-1">
                  <p>
                    Bu metin <strong className="font-medium">taslaktır</strong>; işaretli alanlar
                    doldurulmadan ve hukuk onayı alınmadan yayına alınmamalıdır.
                  </p>
                  <p className="mt-1 text-xs text-ink-2">
                    Eksik alan sayısı: {missing.length} · ayrıntı için depo kökündeki{" "}
                    <span className="font-mono">LEGAL_TODO.md</span>
                  </p>
                </div>
              </div>
            )}

            <nav aria-label="İçindekiler" className="mt-10 rounded-sm border border-border bg-surface p-4">
              <p className="text-overline text-ink-3">İçindekiler</p>
              <ol className="mt-3 flex flex-col gap-1.5">
                {sections.map((section) => (
                  <li key={section.id}>
                    <a
                      href={`#${section.id}`}
                      className="text-sm text-ink-2 underline decoration-transparent underline-offset-4 transition-colors duration-[120ms] hover:text-ink-1 hover:decoration-border-strong"
                    >
                      {section.title}
                    </a>
                  </li>
                ))}
              </ol>
            </nav>

            <div className="mt-10 flex flex-col gap-10">
              {sections.map((section) => (
                <section key={section.id} id={section.id} className="scroll-mt-24">
                  <h2 className="font-display text-xl font-semibold tracking-tight text-ink-1">
                    {section.title}
                  </h2>
                  <div className="mt-4 flex flex-col gap-4 text-sm leading-6 text-ink-2">
                    {section.body}
                  </div>
                </section>
              ))}
            </div>
          </div>
        </div>
      </main>
      <LegalFooter />
    </div>
  );
}

/** Madde listesi — hukuki metinlerde en sık kullanılan blok. */
export function LegalList({ items }: { items: ReactNode[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item, index) => (
        <li key={index} className="flex gap-2.5">
          <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-ink-3" />
          <span className="min-w-0 flex-1">{item}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * VERBİS kayıt durumu — üç duruma göre üç farklı metin.
 *
 * Yükümlülük eşiği (yıllık çalışan sayısı > 50 **veya** yıllık mali bilanço
 * toplamı > 25 milyon TL; ayrıca ana faaliyeti özel nitelikli veri işlemek
 * olanlar eşiksiz yükümlü) şirketin mali verisine bağlıdır ve koddan
 * bilinemez. Bu yüzden karar `legal.config.ts`teki `verbisStatus` alanına
 * bırakılır; `belirlenmedi` iken metin durumu **saklamaz**, açıkça yazar.
 */
export function VerbisNotice() {
  const status = LEGAL_CONFIG.verbisStatus;
  if (status === "kayitli") {
    return (
      <p>
        Veri sorumlusu, Veri Sorumluları Sicili&apos;ne (VERBİS){" "}
        <strong className="font-medium text-ink-1">kayıtlıdır</strong>.
      </p>
    );
  }
  if (status === "muaf") {
    return (
      <p>
        Veri sorumlusu, yıllık çalışan sayısı ve mali bilanço toplamı bakımından VERBİS kayıt
        yükümlülüğü eşiklerinin altında kaldığından{" "}
        <strong className="font-medium text-ink-1">kayıt yükümlülüğüne tabi değildir</strong>.
        Eşikler aşıldığında kayıt yapılır ve bu metin güncellenir.
      </p>
    );
  }
  return (
    <p>
      VERBİS kayıt yükümlülüğü, yıllık çalışan sayısı ve mali bilanço toplamı eşiklerine göre
      belirlenir;{" "}
      <Value value={undefined} field="verbisStatus" /> — değerlendirme tamamlandığında bu bölüm
      güncellenecektir.
    </p>
  );
}

/**
 * Alt işleyen tablosu — liste `config/legal.config.ts`teki `SUB_PROCESSORS`ten
 * gelir ve o liste **kodda gerçekten kullanılan** sağlayıcılardan türetilmiştir
 * (boto3/R2, sentry-sdk, anthropic/openai/ollama, langfuse, `*_PROVIDER`
 * anahtarları). Bölgeler yapılandırmadan okunur; sabit yazılmaz.
 */
export function SubProcessorTable() {
  return (
    <div className="overflow-hidden rounded-sm border border-border">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-surface-2">
            <th
              scope="col"
              className="border-b border-border px-3 py-2.5 text-left text-xs font-medium text-ink-2"
            >
              Sağlayıcı ve amaç
            </th>
            <th
              scope="col"
              className="border-b border-border px-3 py-2.5 text-left text-xs font-medium text-ink-2"
            >
              Veri ve işleme bölgesi
            </th>
          </tr>
        </thead>
        <tbody>
          {SUB_PROCESSORS.map((processor) => (
            <tr key={processor.purpose} className="border-b border-border last:border-b-0">
              <td className="px-3 py-2.5 align-top text-ink-1">
                <Value
                  value={processor.name}
                  field={processor.configuredBy ?? "alt-işleyen adı"}
                />{" "}
                — {processor.purpose}
              </td>
              <td className="px-3 py-2.5 align-top text-ink-2">
                {processor.dataCategory}
                {processor.regionKey !== undefined && (
                  <>
                    {" · "}
                    <Value
                      value={LEGAL_CONFIG.regions[processor.regionKey]}
                      field={`regions.${processor.regionKey}`}
                    />
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Veri sınıfı → süre gibi iki sütunlu tablolar için. */
export function LegalTable({
  headers,
  rows,
}: {
  headers: [string, string];
  rows: [ReactNode, ReactNode][];
}) {
  return (
    <div className="overflow-hidden rounded-sm border border-border">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-surface-2">
            {headers.map((header) => (
              <th
                key={header}
                scope="col"
                className="border-b border-border px-3 py-2.5 text-left text-xs font-medium text-ink-2"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-border last:border-b-0">
              <td className="px-3 py-2.5 align-top text-ink-1">{row[0]}</td>
              <td className="px-3 py-2.5 align-top text-ink-2">{row[1]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
