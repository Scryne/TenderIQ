import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  Check,
  ClipboardCheck,
  ListChecks,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { BrandLockup, BrandMark } from "@/components/auth/auth-layout";
import { EvidenceRail, SourceRef } from "@/components/evidence";
import { LEGAL_LINKS } from "@/components/marketing/legal-shell";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "TenderIQ · Kaynağa bağlı ihale ve şartname analizi",
  description:
    "Yüzlerce sayfalık Türkçe ihale ve RFP dokümanını dakikalar içinde analiz edin. " +
    "Gereksinim, risk, teslim belgesi ve uygunluk boşlukları. Her bulgu kaynağına kadar izlenebilir.",
};

/* ═══════════════════════════════════════════════════════════════════════════
 * LANDING — Yön A "Mürekkep"
 *
 * Sayfanın tek işi: "bu ürün bulgusunu kanıtlıyor mu?" sorusunu 5 saniyede
 * cevaplamak. Bu yüzden hero'nun sağ yarısı bir illüstrasyon değil, ürünün
 * gerçek bulgu satırıdır — kaynak koordinatı ve kanıt şeridiyle.
 *
 * §13 uyumu: gradient yok, glow yok, kromatik marka rengi yok, uppercase buton
 * yok, "3 sütunlu jenerik özellik kartı" ızgarası yok. Tek doygun renkler
 * semantik durumlar ve kanıt vurgusu.
 * ═══════════════════════════════════════════════════════════════════════════ */

const NAV_LINKS = [
  { href: "#kanit", label: "Kanıt" },
  { href: "#yetenekler", label: "Yetenekler" },
  { href: "#nasil-calisir", label: "Nasıl çalışır" },
  { href: "#fiyatlandirma", label: "Fiyatlandırma" },
  { href: "#guvenlik", label: "Güvenlik" },
] as const;

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-ink-1">
      <SiteHeader />
      <main className="flex-1">
        <Hero />
        <TerminologyStrip />
        <CitationShowcase />
        <Capabilities />
        <HowItWorks />
        <Pricing />
        <Security />
        <FinalCta />
      </main>
      <SiteFooter />
    </div>
  );
}

/* ------------------------------ Header ------------------------------ */

function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-canvas/90 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-6 px-5">
        <BrandLockup />

        <nav className="hidden items-center gap-0.5 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-sm px-2.5 py-2 text-sm text-ink-2 transition-colors duration-[120ms] hover:bg-hover hover:text-ink-1"
            >
              {link.label}
            </a>
          ))}
        </nav>

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

/* ------------------------------- Hero ------------------------------- */

function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-border">
      {/* Kâğıt kılavuz çizgileri — dekoratif gradyan değil, hairline ızgara. */}
      <div
        aria-hidden
        className="bg-rule pointer-events-none absolute inset-0 opacity-70 [mask-image:linear-gradient(to_bottom,black,transparent_85%)]"
      />

      <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-5 py-20 lg:grid-cols-[1.05fr_0.95fr] lg:py-28">
        <div className="animate-rise">
          <span className="inline-flex items-center gap-2 rounded-sm border border-border bg-surface px-2.5 py-1 text-xs font-medium text-ink-2">
            <span aria-hidden className="animate-live size-1.5 rounded-full bg-success" />
            Kapalı beta · Türkçe kamu ihaleleri
          </span>

          <h1 className="mt-5 font-display text-4xl leading-[1.06] font-semibold tracking-tight text-balance text-ink-1 sm:text-5xl">
            Şartnamedeki her maddeyi{" "}
            <span className="relative whitespace-nowrap">
              <span className="relative z-10">kanıtıyla</span>
              {/* Fosforlu kalem metnin ÜSTÜNE biner, altına çizilmez: ölçüler
                  em cinsinden verilir ki 4xl/5xl kırılımlarında kaymasın. */}
              <span
                aria-hidden
                className="absolute inset-x-[-0.08em] bottom-[0.14em] z-0 h-[0.42em] bg-evidence"
              />
            </span>{" "}
            görün.
          </h1>

          <p className="mt-6 max-w-xl text-lg leading-relaxed text-pretty text-ink-2">
            TenderIQ yüzlerce sayfalık ihale dosyasını okur; gereksinimleri, riskleri, istenen
            belgeleri ve uygunluk boşluklarını çıkarır. Her bulgu, dokümandaki tam sayfa ve maddeye
            bağlıdır. Gerekçesini göremediğiniz bir sonuç göstermez.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/register" className={cn(buttonVariants({ size: "lg" }))}>
              Ücretsiz başla
              <ArrowRight strokeWidth={2} />
            </Link>
            <a
              href="#kanit"
              className={cn(buttonVariants({ variant: "secondary", size: "lg" }))}
            >
              Kanıtı gör
            </a>
          </div>

          <p className="mt-5 text-sm text-ink-3">
            Kredi kartı istenmez · Ücretsiz planda ayda 3 doküman · KVKK-uyumlu
          </p>
        </div>

        {/* Ürünün gerçek bulgu satırı — illüstrasyon değil. */}
        <div className="animate-rise [animation-delay:120ms]">
          <FindingPreview />
        </div>
      </div>
    </section>
  );
}

/** Hero'daki inceleme önizlemesi: uygulamanın kendi bileşenleriyle kurulur. */
function FindingPreview() {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-md">
      <div className="flex items-center gap-2 border-b border-border bg-surface-2 px-4 py-2.5">
        <span className="font-mono text-[11px] text-ink-3">
          2026/128764 · idari-sartname.pdf
        </span>
        <span className="ml-auto inline-flex items-center gap-1.5 font-mono text-[11px] text-ink-3">
          <span aria-hidden className="size-1.5 rounded-full bg-success" />
          18/18 kaynağa bağlı
        </span>
      </div>

      <div className="divide-y divide-border">
        <PreviewRow
          tone="danger"
          text="Yüklenici, teslim gecikmesinin her takvim günü için sözleşme bedelinin binde 3'ü oranında gecikme cezası öder."
          page={42}
          section="4.3.1"
          badges={
            <>
              <Badge tone="danger" dot>
                Yüksek risk
              </Badge>
              <Badge tone="outline">Cezai şart</Badge>
            </>
          }
        />
        <PreviewRow
          tone="warning"
          text="İş deneyimini gösteren belgeler: son beş yıl içinde bedel içeren tek sözleşmeye ilişkin iş deneyim belgesi."
          page={44}
          section="7.5.1"
          badges={
            <>
              <Badge tone="warning">Zorunlu</Badge>
              <Badge tone="outline">Belge</Badge>
            </>
          }
        />
        <PreviewRow
          tone="ink"
          text="Son teklif verme tarihi ve saati: 18.11.2026, 10:30"
          page={3}
          section="1.2"
          badges={<Badge tone="outline">Son teklif</Badge>}
        />
      </div>

      <div className="flex items-center gap-3 border-t border-border bg-surface-2 px-4 py-2.5">
        <span className="h-1.5 w-24 overflow-hidden rounded-full bg-border">
          <span className="block h-full w-2/3 rounded-full bg-accent" />
        </span>
        <span className="font-mono text-[11px] text-ink-2">12/18 karara bağlandı</span>
      </div>
    </div>
  );
}

function PreviewRow({
  tone,
  text,
  page,
  section,
  badges,
}: {
  tone: "ink" | "danger" | "warning";
  text: string;
  page: number;
  section: string;
  badges: ReactNode;
}) {
  return (
    <div className="p-4">
      <EvidenceRail tone={tone}>
        <p className="text-[13.5px] leading-5 text-ink-1">{text}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <SourceRef page={page} section={section} />
          {badges}
        </div>
      </EvidenceRail>
    </div>
  );
}

/* -------------------------- Terminoloji şeridi ---------------------- */

function TerminologyStrip() {
  const items = [
    "4734 sayılı Kamu İhale Kanunu",
    "Teknik ve idari şartname",
    "Sözleşme tasarısı",
    "Zeyilname",
    "Yeterlik kriterleri",
    "EKAP terminolojisi",
  ];
  return (
    <section className="border-b border-border bg-surface">
      <div className="mx-auto max-w-6xl px-5 py-7">
        <p className="text-overline text-center text-ink-3">
          TÜRK KAMU İHALE MEVZUATININ DİLİYLE ÇALIŞIR
        </p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-sm text-ink-2">
          {items.map((item) => (
            <span key={item} className="inline-flex items-center gap-2">
              <span aria-hidden className="size-1 rounded-full bg-border-strong" />
              {item}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------- Bölüm 1 · Şerhli belge (imza) ------------------- */

/*
 * Hero ile aynı "solda metin, sağda kart" iskeletini tekrarlamamak için imza bölümü
 * tam genişlikte bir şartname sayfasıdır: vurgulu pasajlar sağ kenardaki numaralı
 * şerhlere bağlanır. Ürünün inceleme ekranındaki iki bölmeli düzenin (§4 kırmızı
 * çizgi) statik karşılığı; bulgu ile kaynağı aynı bakışta okunur.
 */
const ANNOTATIONS = [
  {
    n: 1,
    tone: "warning" as const,
    badges: (
      <>
        <Badge tone="warning">Zorunlu</Badge>
        <Badge tone="outline">Belge</Badge>
      </>
    ),
    text: "Teklif bedelinin en az %3'ü tutarında geçici teminat sunulacak.",
    section: "7.3.1",
  },
  {
    n: 2,
    tone: "danger" as const,
    badges: (
      <>
        <Badge tone="danger" dot>
          Yüksek risk
        </Badge>
        <Badge tone="outline">Teminat</Badge>
      </>
    ),
    text: "Teminat süresi (90 gün) teklif geçerlilik süresini (120 gün) kapsamıyor.",
    section: "7.3.2",
  },
  {
    n: 3,
    tone: "warning" as const,
    badges: (
      <>
        <Badge tone="warning" dot>
          Orta risk
        </Badge>
        <Badge tone="outline">Alt yüklenici</Badge>
      </>
    ),
    text: "İşin hiçbir kısmı alt yükleniciye verilemez; ortaklık yapısı buna göre kurulmalı.",
    section: "7.4.1",
  },
];

function Marker({ n }: { n: number }) {
  return (
    <sup className="ml-0.5 font-mono text-[10px] font-medium text-evidence-edge" aria-label={`şerh ${n}`}>
      [{n}]
    </sup>
  );
}

function CitationShowcase() {
  return (
    <section id="kanit" className="scroll-mt-20">
      <div className="mx-auto max-w-6xl px-5 py-20 lg:py-28">
        <SectionHeading
          section="1"
          label="İzlenebilirlik"
          title="“Bunu nereden çıkardın?” sorusunun cevabı sayfanın kenarında"
          desc="Teklif kararı milyonlarca liralık taahhüt doğurur. TenderIQ hiçbir bulguyu gerekçesiz sunmaz: her satır dokümandaki tam pasaja bağlıdır ve orijinal metnin üzerinde vurgulanır."
        />

        <figure className="mt-12 overflow-hidden rounded-lg border border-border bg-surface shadow-sm">
          <div className="flex items-center justify-between gap-3 border-b border-border bg-surface-2 px-5 py-2.5">
            <span className="font-mono text-[11px] text-ink-3">teknik-sartname.pdf</span>
            <span className="font-mono text-[11px] text-ink-3">s. 24 / 118</span>
          </div>

          <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
            {/* Sayfa: şartnamenin kendi dizgisi, serif değil; kanıt kroması yalnız vurguda. */}
            <div className="px-6 py-8 sm:px-10 lg:py-10">
              <p className="font-display text-sm font-semibold text-ink-1">Madde 7 · Teminatlar</p>
              <div className="mt-4 flex max-w-[64ch] flex-col gap-4 text-[15px] leading-7 text-ink-2">
                <p>
                  7.3.1. İstekliler, teklifleriyle birlikte{" "}
                  <mark className="evidence-mark box-decoration-clone px-0.5 text-ink-1">
                    teklif bedelinin %3&apos;ünden az olmamak üzere geçici teminat
                  </mark>
                  <Marker n={1} /> sunacaktır. Teminat, standart forma uygun düzenlenir.
                </p>
                <p>
                  7.3.2.{" "}
                  <mark className="evidence-mark box-decoration-clone px-0.5 text-ink-1">
                    Geçici teminat mektubu ihale tarihinden itibaren 90 gün geçerli olmalıdır.
                  </mark>
                  <Marker n={2} /> Teklif geçerlilik süresi ise 120 takvim günüdür.
                </p>
                <p>
                  7.4.1. Yüklenici, sözleşme konusu işi bizzat yürütür.{" "}
                  <mark className="evidence-mark box-decoration-clone px-0.5 text-ink-1">
                    İşin hiçbir kısmı alt yükleniciye yaptırılamaz.
                  </mark>
                  <Marker n={3} />
                </p>
                <p className="text-ink-3">
                  7.5. Teminat mektuplarının iadesi, kesin kabulün ardından 30 gün içinde yapılır.
                </p>
              </div>
            </div>

            {/* Kenar şerhleri: uygulamanın bulgu satırıyla aynı bileşenler. */}
            <ol className="flex flex-col divide-y divide-border border-t border-border bg-surface-2 lg:border-t-0 lg:border-l">
              {ANNOTATIONS.map((note) => (
                <li key={note.n} className="flex gap-3 px-5 py-5">
                  <span className="mt-0.5 font-mono text-[11px] font-medium text-evidence-edge">
                    [{note.n}]
                  </span>
                  <EvidenceRail tone={note.tone} className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">{note.badges}</div>
                    <p className="mt-2 text-sm leading-6 font-medium text-ink-1">{note.text}</p>
                    <div className="mt-2">
                      <SourceRef page={24} section={note.section} />
                    </div>
                  </EvidenceRail>
                </li>
              ))}
            </ol>
          </div>
        </figure>
        <p className="mt-4 max-w-[70ch] text-sm text-ink-3">
          Uygulamada bir şerhi seçmek belgeyi o sayfaya götürür ve pasajı vurgular. Onay, düzeltme
          ve ret kararları kim ve ne zaman bilgisiyle saklanır; her karar geri alınabilir.
        </p>
      </div>
    </section>
  );
}

/* --------------------- Bölüm 2 · Çıkarım ajanları -------------------- */

const AGENTS: {
  icon: LucideIcon;
  name: string;
  scope: string;
  example: string;
  page: number;
  section: string;
}[] = [
  {
    icon: ListChecks,
    name: "Gereksinim",
    scope: "Teknik ve idari şartnamedeki her yükümlülük. Zorunlu olanlar ayrıca işaretlenir.",
    example: "TS EN ISO/IEC 27001 belgesi zorunlu",
    page: 9,
    section: "7.2.3",
  },
  {
    icon: ClipboardCheck,
    name: "Belge",
    scope: "Sunulacak belge, sertifika ve teminatlar. Eksik evrak teklif gecesi değil, ilk gün görünür.",
    example: "İmza sirküleri veya imza beyannamesi",
    page: 8,
    section: "7.1",
  },
  {
    icon: AlertTriangle,
    name: "Risk",
    scope: "Cezai şart, fesih, garanti ve ödeme maddeleri, şiddetine göre sıralı.",
    example: "Günlük binde 3 gecikme cezası",
    page: 42,
    section: "46.1",
  },
  {
    icon: CalendarClock,
    name: "Takvim",
    scope: "Son teklif, teslim ve garanti süreleri; panelde tek listede.",
    example: "Son teklif 18.11.2026, 10:30",
    page: 1,
    section: "3.2",
  },
  {
    icon: ShieldCheck,
    name: "Uygunluk",
    scope: "Yeterlik kriterleri ile firmanızın yetkinlik beyanı karşılaştırılır.",
    example: "Benzer iş deneyimi eşiği karşılanmıyor",
    page: 9,
    section: "7.2.1",
  },
];

function Capabilities() {
  return (
    <section id="yetenekler" className="scroll-mt-20 border-y border-border bg-surface">
      <div className="mx-auto max-w-6xl px-5 py-20 lg:py-24">
        <SectionHeading
          section="2"
          label="Çıkarım ajanları"
          title="Şartnameyi okumaktan değil, karar vermekten sorumlu olun"
          desc="Beş uzman ajan aynı dokümanı tek akışta okur. Her biri kendi sorusunu sorar ve her cevabı kaynağına bağlar."
        />

        {/* Dizin: kart ızgarası değil, şartname fihristi gibi okunan sıralı tablo. */}
        <div className="mt-12 border-t border-ink-1">
          <div className="hidden grid-cols-[12rem_minmax(0,1fr)_minmax(0,1.1fr)] gap-6 border-b border-border py-3 md:grid">
            <span className="font-mono text-[11px] text-ink-3">Ajan</span>
            <span className="font-mono text-[11px] text-ink-3">Ne arar</span>
            <span className="font-mono text-[11px] text-ink-3">Örnek bulgu</span>
          </div>
          <ol>
            {AGENTS.map((agent) => (
              <li
                key={agent.name}
                className="grid gap-2 border-b border-border py-5 md:grid-cols-[12rem_minmax(0,1fr)_minmax(0,1.1fr)] md:gap-6"
              >
                <span className="flex items-center gap-2.5">
                  <agent.icon aria-hidden className="size-4 text-ink-2" strokeWidth={1.75} />
                  <span className="text-[15px] font-semibold text-ink-1">{agent.name}</span>
                </span>
                <p className="text-sm leading-6 text-ink-2">{agent.scope}</p>
                <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm text-ink-1">
                  <span>{agent.example}</span>
                  <SourceRef page={agent.page} section={agent.section} />
                </p>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

/* ------------------------- Bölüm 3 · İşleme hattı ------------------------ */

const STATIONS: { title: string; body: string }[] = [
  { title: "Yükle", body: "PDF, DOCX, XLSX. Taranmış sayfalar OCR ile metne çevrilir." },
  { title: "Ayrıştır", body: "Sayfa, madde ve tablo yapısı korunur; konum her öğede saklanır." },
  { title: "Getir", body: "Anlamsal ve anahtar kelime araması birlikte, ilgili pasajları seçer." },
  { title: "Çıkar ve bağla", body: "Ajanlar bulgu üretir. Kaynağına bağlanamayan bulgu elenir." },
  { title: "İncele ve aktar", body: "Onaylı bulgular Word raporu ve Excel kontrol listesi olur." },
];

function HowItWorks() {
  return (
    <section id="nasil-calisir" className="scroll-mt-20">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-20 lg:grid-cols-[18rem_minmax(0,1fr)] lg:gap-14 lg:py-24">
        <SectionHeading
          section="3"
          label="İşleme hattı"
          title="Dosyadan onaylı rapora"
          desc="Aradaki her adımda kaynak görünür kalır; hiçbir adım bir kara kutu değildir."
        />

        {/* Hat şeridi: kart üçlüsü değil, tek çizgi üzerinde istasyonlar. */}
        <ol className="relative grid gap-8 sm:grid-cols-2 lg:mt-2 lg:grid-cols-5 lg:gap-5">
          <span
            aria-hidden
            className="absolute top-[7px] right-0 left-0 hidden h-px bg-border-strong lg:block"
          />
          {STATIONS.map((station, index) => (
            <li key={station.title} className="relative">
              <span className="relative z-10 flex items-center gap-3 bg-canvas pr-2 lg:w-fit">
                <span
                  aria-hidden
                  className={cn(
                    "size-[15px] rounded-full border-2",
                    index === 3 ? "border-evidence-edge bg-evidence-strong" : "border-ink-1 bg-canvas",
                  )}
                />
                <span className="font-mono text-[11px] text-ink-3">
                  {String(index + 1).padStart(2, "0")}
                </span>
              </span>
              <h3 className="mt-4 text-[15px] font-semibold text-ink-1">{station.title}</h3>
              <p className="mt-1.5 text-sm leading-6 text-ink-2">{station.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* --------------------------- Fiyatlandırma -------------------------- */

const PLANS = [
  {
    name: "Ücretsiz",
    price: "₺0",
    period: "/ ay",
    tagline: "Denemek ve tekil ihaleler için.",
    features: [
      "3 doküman / ay",
      "35 sayfa / ay",
      "Gereksinim, risk, belge ve takvim çıkarımı",
      "Kaynak vurgulu inceleme",
      "Word ve Excel çıktısı",
    ],
    cta: "Ücretsiz başla",
    href: "/register",
    highlight: false,
  },
  {
    name: "Pro",
    price: "₺1.500",
    period: "/ ay",
    tagline: "Aktif teklif ekipleri için.",
    features: [
      "60 doküman / ay",
      "390 sayfa / ay",
      "Uygunluk analizi dahil tüm ajanlar",
      "Ekip üyeleri ve roller",
      "Öncelikli işleme kuyruğu",
      "İnsan-döngüde onay akışı",
    ],
    cta: "Pro ile başla",
    href: "/register",
    highlight: true,
  },
  {
    name: "Kurumsal",
    price: "Özel",
    period: "",
    tagline: "Yüksek hacim ve özel gereksinimler.",
    features: [
      "Sınırsız doküman ve sayfa",
      "SSO ve gelişmiş güvenlik",
      "Özel barındırma / veri ikametgâhı",
      "Entegrasyon ve API erişimi",
      "Öncelikli destek ve SLA",
    ],
    cta: "Satışla görüşün",
    href: "mailto:satis@tenderiq.local?subject=Kurumsal%20plan",
    highlight: false,
  },
];

function Pricing() {
  return (
    <section id="fiyatlandirma" className="scroll-mt-20 border-y border-border bg-surface">
      <div className="mx-auto max-w-6xl px-5 py-20 lg:py-24">
        <SectionHeading
          section="4"
          label="Fiyatlandırma"
          title="Ekibiniz büyüdükçe ölçeklenen, öngörülebilir kademeler"
          desc="Kotalar takvim ayı başında yenilenir. İstediğiniz zaman yükseltin ya da düşürün."
        />

        <div className="mt-12 grid items-stretch gap-5 lg:grid-cols-3">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={cn(
                "relative flex flex-col rounded-lg border bg-canvas p-6",
                plan.highlight ? "border-accent ring-1 ring-accent" : "border-border",
              )}
            >
              {plan.highlight && (
                <span className="absolute -top-[11px] left-6">
                  <Badge tone="ink">En çok tercih edilen</Badge>
                </span>
              )}

              <h3 className="text-[15px] font-semibold text-ink-1">{plan.name}</h3>
              <p className="mt-1 text-sm text-ink-2">{plan.tagline}</p>

              <p className="mt-5 flex items-baseline gap-1.5">
                <span className="font-display text-4xl font-semibold tracking-tight text-ink-1">
                  {plan.price}
                </span>
                {plan.period !== "" && <span className="text-sm text-ink-3">{plan.period}</span>}
              </p>

              <Link
                href={plan.href}
                className={cn(
                  buttonVariants({ variant: plan.highlight ? "primary" : "secondary" }),
                  "mt-6 w-full",
                )}
              >
                {plan.cta}
              </Link>

              <ul className="mt-6 flex flex-1 flex-col gap-3 border-t border-border pt-6">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2.5 text-sm text-ink-2">
                    <Check
                      aria-hidden
                      className="mt-0.5 size-4 shrink-0 text-success"
                      strokeWidth={2.25}
                    />
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* --------------------- Bölüm 5 · Güvenlik taahhütleri -------------------- */

/*
 * 2x2 ikon kartı yerine madde madde taahhüt: şartname okuyan birine sözleşme
 * diliyle konuşur ve her maddenin karşılığı kodda var (RLS, grounding, denetim izi).
 */
const COMMITMENTS: { title: string; body: string }[] = [
  {
    title: "Verileriniz kiracınızın dışına çıkmaz",
    body: "Her organizasyonun verisi veritabanı düzeyinde satır güvenliğiyle (RLS) ayrılır. İzolasyon uygulama koduna değil, veritabanının kendisine emanettir.",
  },
  {
    title: "Dokümanlarınız model eğitiminde kullanılmaz",
    body: "Yüklediğiniz şartnameler yalnız sizin analizinizde işlenir. Sıfır saklama politikası olan sağlayıcılar kullanılır ve alt işleyenler güven sayfasında listelenir.",
  },
  {
    title: "Kaynağı olmayan bulgu rapora girmez",
    body: "Çıkarım, dokümandaki bir pasaja bağlanamıyorsa reddedilir. Kara kutu bir sonuç yerine eksik bir rapor tercih edilir.",
  },
  {
    title: "Her karar izlenebilir",
    body: "Onay, düzeltme, ret, davet ve üyelik değişiklikleri denetim izine kim ve ne zaman bilgisiyle yazılır.",
  },
  {
    title: "Silme talebi kalıcıdır",
    body: "KVKK kapsamındaki silme talebi dokümanı, parçalarını, vektörlerini ve depolama nesnesini birlikte kaldırır.",
  },
];

function Security() {
  return (
    <section id="guvenlik" className="scroll-mt-20">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)] lg:gap-16 lg:py-24">
        <div className="lg:sticky lg:top-24 lg:self-start">
          <SectionHeading
            section="5"
            label="Güvenlik"
            title="Şartname ticari sırdır; öyle davranıyoruz"
            desc="Veri ayrımı, saklama ve izlenebilirlik sonradan eklenmedi. Mimarinin içinde."
          />
          <Link
            href="/trust"
            className={cn(buttonVariants({ variant: "secondary" }), "mt-8")}
          >
            Güven merkezini inceleyin
            <ArrowRight strokeWidth={2} />
          </Link>
        </div>

        <ol className="border-t border-ink-1">
          {COMMITMENTS.map((item, index) => (
            <li
              key={item.title}
              className="grid gap-2 border-b border-border py-6 sm:grid-cols-[6rem_minmax(0,1fr)] sm:gap-6"
            >
              <span className="font-mono text-[11px] text-ink-3">Madde {index + 1}</span>
              <div className="min-w-0">
                <h3 className="text-[15px] font-semibold text-ink-1">{item.title}</h3>
                <p className="mt-1.5 max-w-[62ch] text-sm leading-6 text-ink-2">{item.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ------------------------------ Son CTA ----------------------------- */

function FinalCta() {
  return (
    <section className="border-t border-border bg-surface">
      <div className="mx-auto max-w-6xl px-5 py-20 lg:py-24">
        <div className="relative overflow-hidden rounded-lg border border-border bg-canvas px-6 py-14 text-center sm:px-12">
          <div
            aria-hidden
            className="bg-rule pointer-events-none absolute inset-0 opacity-70 [mask-image:radial-gradient(ellipse_70%_60%_at_50%_50%,black,transparent)]"
          />
          <div className="relative">
            <BrandMark className="mx-auto" />
            <h2 className="mt-5 font-display text-3xl leading-tight font-semibold tracking-tight text-balance text-ink-1">
              Bir sonraki şartnameyi okumaya değil, incelemeye başlayın
            </h2>
            <p className="mx-auto mt-4 max-w-[54ch] text-base text-ink-2">
              İlk ihalenizi ücretsiz planda çözümleyin. Kredi kartı istenmez, kurulum gerekmez.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link href="/register" className={cn(buttonVariants({ size: "lg" }))}>
                Ücretsiz başla
                <ArrowRight strokeWidth={2} />
              </Link>
              <a
                href="mailto:satis@tenderiq.local?subject=TenderIQ%20demo"
                className={cn(buttonVariants({ variant: "secondary", size: "lg" }))}
              >
                Demo isteyin
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------- Footer ----------------------------- */

function SiteFooter() {
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
          <Link href="/login" className="hover:text-ink-1">
            Giriş yap
          </Link>
        </nav>
        <p className="text-xs text-ink-3">© 2026 TenderIQ</p>
      </div>
    </footer>
  );
}

/* ------------------------------ Yardımcı ---------------------------- */

function SectionHeading({
  section,
  label,
  title,
  desc,
}: {
  /** Şartname dizgisindeki bölüm numarası; genel "ÖZELLİKLER" etiketinin yerine. */
  section: string;
  label: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="max-w-[60ch]">
      <p className="font-mono text-xs text-ink-3">
        Bölüm {section} · {label}
      </p>
      <h2 className="mt-3 font-display text-3xl leading-tight font-semibold tracking-tight text-balance text-ink-1">
        {title}
      </h2>
      <p className="mt-4 text-base leading-relaxed text-pretty text-ink-2">{desc}</p>
    </div>
  );
}
