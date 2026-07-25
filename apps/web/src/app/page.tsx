import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  Check,
  ClipboardCheck,
  FileDown,
  Layers,
  Link2,
  ListChecks,
  Lock,
  ShieldCheck,
  UploadCloud,
  type LucideIcon,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { BrandLockup, BrandMark } from "@/components/auth/auth-layout";
import { EvidenceRail, SourceRef } from "@/components/evidence";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "TenderIQ — Yapay zekâ destekli ihale ve RFP analizi",
  description:
    "Yüzlerce sayfalık Türkçe ihale ve RFP dokümanını dakikalar içinde analiz edin. " +
    "Gereksinim, risk, teslim-belge ve uygunluk boşlukları — her bulgu kaynağına kadar izlenebilir.",
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
          <Link href="/login" className={cn(buttonVariants({ size: "sm" }))}>
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
            bağlıdır — gerekçesini görmediğiniz bir sonuç göstermez.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/login" className={cn(buttonVariants({ size: "lg" }))}>
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
            Kredi kartı istenmez · Ücretsiz planda ayda 5 doküman · KVKK-uyumlu
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
          text="Son teklif verme tarihi ve saati: 18.08.2026 — 10:30"
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

/* ----------------------- Kanıt vitrini (imza) ----------------------- */

function CitationShowcase() {
  const points = [
    {
      title: "Sayfa ve madde düzeyinde referans",
      body: "Her bulgu “s. 24 · 7.3.2” gibi kesin bir konumla gelir; aramak zorunda kalmazsınız.",
    },
    {
      title: "Orijinal metinde vurgulama",
      body: "Kaynak pasaj, dokümanın kendi görünümünde işaretlenir — bağlamından koparılmaz.",
    },
    {
      title: "İnsan-döngüde onay",
      body: "Bulguyu düzeltin, onaylayın ya da reddedin; her karar kim/ne zaman iziyle saklanır.",
    },
  ];

  return (
    <section id="kanit" className="scroll-mt-20">
      <div className="mx-auto grid max-w-6xl items-center gap-14 px-5 py-20 lg:grid-cols-2 lg:py-24">
        <div>
          <p className="text-overline text-ink-3">İZLENEBİLİRLİK</p>
          <h2 className="mt-3 font-display text-3xl leading-tight font-semibold tracking-tight text-balance text-ink-1 sm:text-4xl">
            “Bunu nereden çıkardın?” sorusunun cevabı hep bir tık uzakta
          </h2>
          <p className="mt-5 text-lg leading-relaxed text-ink-2">
            Teklif kararları milyonlarca liralık taahhüt doğurur. TenderIQ hiçbir bulguyu
            gerekçesiz sunmaz: her satır dokümandaki tam pasaja bağlıdır ve orijinal metnin
            üzerinde vurgulanır.
          </p>

          <ul className="mt-8 flex flex-col gap-4">
            {points.map((item) => (
              <li key={item.title} className="flex gap-3">
                <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-success-weak text-success">
                  <Check aria-hidden className="size-3" strokeWidth={3} />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink-1">{item.title}</p>
                  <p className="mt-0.5 text-sm text-ink-2">{item.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-border bg-surface p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="text-overline text-ink-3">KAYNAK PASAJ</span>
            <span className="rounded-sm bg-surface-2 px-2 py-1 font-mono text-[11px] text-ink-2">
              teknik-sartname.pdf · s.24
            </span>
          </div>

          <div className="mt-4 rounded-sm border border-border bg-surface-2 p-4">
            <p className="text-sm leading-7 text-ink-2">
              7.3.2. İstekliler, teklifleriyle birlikte teklif bedelinin %3&apos;ünden az olmamak
              üzere geçici teminat sunacaktır.{" "}
              <mark className="evidence-mark box-decoration-clone px-0.5 font-medium text-ink-1">
                Geçici teminat mektubu, ihale tarihinden itibaren 90 gün geçerli olmalıdır.
              </mark>{" "}
              Teklif geçerlilik süresi ise 120 takvim günüdür.
            </p>
          </div>

          <div className="mt-4 rounded-sm border border-border p-4">
            <EvidenceRail tone="danger">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="danger" dot>
                  Yüksek risk
                </Badge>
                <Badge tone="outline">Teminat</Badge>
              </div>
              <p className="mt-2 text-sm font-medium text-ink-1">
                Teminat geçerlilik süresi (90 gün), teklif geçerlilik süresini (120 gün)
                kapsamıyor.
              </p>
              <div className="mt-2">
                <SourceRef page={24} section="7.3.2" />
              </div>
            </EvidenceRail>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ----------------------------- Yetenekler --------------------------- */

const CAPABILITIES: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: ListChecks,
    title: "Gereksinim çıkarımı",
    body: "Teknik ve idari şartnamedeki her zorunlu gereksinimi madde madde çıkarır; zorunlu olanları ayrıca işaretler.",
  },
  {
    icon: ClipboardCheck,
    title: "İstenen belgeler",
    body: "Sunulması gereken belge, sertifika ve teminatları listeler. Eksik evrağı teklif gecesi değil, ilk gün görün.",
  },
  {
    icon: AlertTriangle,
    title: "Risk analizi",
    body: "Cezai şart, fesih, garanti ve ödeme maddelerini şiddetine göre sınıflandırır; çelişkileri yüzeye çıkarır.",
  },
  {
    icon: CalendarClock,
    title: "Takvim çıkarımı",
    body: "Son teklif tarihi, teslim süresi ve garanti süresi gibi tarihleri metinden çıkarır ve panelde toplar.",
  },
  {
    icon: ShieldCheck,
    title: "Uygunluk boşlukları",
    body: "Yeterlik kriterlerini firma yetkinlik profilinizle karşılaştırır; karşılamadığınız maddeleri öne alır.",
  },
  {
    icon: FileDown,
    title: "Word ve Excel çıktısı",
    body: "Onayladığınız bulguları kaynak referanslarıyla birlikte rapora ve kontrol listesine dönüştürür.",
  },
];

function Capabilities() {
  return (
    <section id="yetenekler" className="scroll-mt-20 border-y border-border bg-surface">
      <div className="mx-auto max-w-6xl px-5 py-20 lg:py-24">
        <SectionHeading
          eyebrow="YETENEKLER"
          title="Şartnameyi okumaktan değil, karar vermekten sorumlu olun"
          desc="Beş uzman çıkarım ajanı tek akışta çalışır ve her sonucu kaynağına bağlar."
        />

        {/* Jenerik 3'lü ikon kartı ızgarası değil (§13.3): iki sütunlu, kenarlıkla
            ayrılmış yoğun liste — okuma sırası soldan sağa değil yukarıdan aşağı. */}
        <div className="mt-12 grid divide-y divide-border border-y border-border sm:grid-cols-2 sm:divide-x">
          {CAPABILITIES.map((item) => (
            <div key={item.title} className="flex gap-4 p-6">
              <span className="grid size-9 shrink-0 place-items-center rounded-md bg-surface-2">
                <item.icon aria-hidden className="size-[18px] text-ink-2" strokeWidth={1.75} />
              </span>
              <div className="min-w-0">
                <h3 className="text-[15px] font-semibold text-ink-1">{item.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{item.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------------------------- Nasıl çalışır ------------------------- */

const STEPS: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: UploadCloud,
    title: "Yükle",
    body: "İhale dosyalarını sürükleyip bırakın. Yüzlerce sayfa ve taranmış belge dahil — OCR ile metne çevrilir.",
  },
  {
    icon: Link2,
    title: "Analiz et",
    body: "Çıkarım ajanları bulguları üretir. Kaynağına bağlanamayan bir bulgu rapora hiç girmez.",
  },
  {
    icon: Check,
    title: "Doğrula ve aktar",
    body: "Bulguları kaynağında inceleyip onaylayın; Word raporu ve Excel kontrol listesi olarak paylaşın.",
  },
];

function HowItWorks() {
  return (
    <section id="nasil-calisir" className="scroll-mt-20">
      <div className="mx-auto max-w-6xl px-5 py-20 lg:py-24">
        <SectionHeading
          eyebrow="NASIL ÇALIŞIR"
          title="Dosyadan onaylı rapora üç adımda"
          desc="Yüklemeden dışa aktarmaya; aradaki her adımda kaynak görünür kalır."
        />

        <ol className="mt-12 grid gap-4 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <li
              key={step.title}
              className="rounded-lg border border-border bg-surface p-6"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="grid size-9 place-items-center rounded-md bg-accent text-ink-on-accent">
                  <step.icon aria-hidden className="size-[18px]" strokeWidth={1.75} />
                </span>
                <span className="font-mono text-2xl font-medium text-border-strong">
                  {String(index + 1).padStart(2, "0")}
                </span>
              </div>
              <h3 className="mt-4 text-[15px] font-semibold text-ink-1">{step.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{step.body}</p>
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
      "5 doküman / ay",
      "150 sayfa / ay",
      "Gereksinim, risk, belge ve takvim çıkarımı",
      "Kaynak vurgulu inceleme",
      "Word ve Excel çıktısı",
    ],
    cta: "Ücretsiz başla",
    href: "/login",
    highlight: false,
  },
  {
    name: "Pro",
    price: "₺1.500",
    period: "/ ay",
    tagline: "Aktif teklif ekipleri için.",
    features: [
      "100 doküman / ay",
      "5.000 sayfa / ay",
      "Uygunluk analizi dahil tüm ajanlar",
      "Ekip üyeleri ve roller",
      "Öncelikli işleme kuyruğu",
      "İnsan-döngüde onay akışı",
    ],
    cta: "Pro ile başla",
    href: "/login",
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
          eyebrow="FİYATLANDIRMA"
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

/* ------------------------------ Güvenlik ---------------------------- */

const SECURITY: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: ShieldCheck,
    title: "KVKK-uyumlu",
    body: "Türk veri koruma mevzuatı gözetilerek tasarlandı; aydınlatma ve saklama ilkeleri gömülü.",
  },
  {
    icon: Layers,
    title: "Kiracı izolasyonu",
    body: "Her organizasyonun verisi veritabanı düzeyinde satır güvenliğiyle (RLS) ayrılır.",
  },
  {
    icon: Lock,
    title: "Verileriniz eğitimde kullanılmaz",
    body: "Yüklediğiniz dokümanlar model eğitimine dahil edilmez; yalnız sizin analizinizde çalışır.",
  },
  {
    icon: Link2,
    title: "Kara kutu değil",
    body: "Kaynağına bağlanamayan bir çıkarım rapora girmez. Denetlenebilirlik ürünün temelidir.",
  },
];

function Security() {
  return (
    <section id="guvenlik" className="scroll-mt-20">
      <div className="mx-auto max-w-6xl px-5 py-20 lg:py-24">
        <SectionHeading
          eyebrow="GÜVENLİK"
          title="Şartname ticari sırdır; öyle davranıyoruz"
          desc="Veri ayrımı, saklama ve izlenebilirlik kararları sonradan eklenmedi — mimarinin içinde."
        />

        <div className="mt-12 grid gap-4 sm:grid-cols-2">
          {SECURITY.map((item) => (
            <div key={item.title} className="rounded-lg border border-border bg-surface p-6">
              <span className="grid size-9 place-items-center rounded-md bg-surface-2">
                <item.icon aria-hidden className="size-[18px] text-ink-2" strokeWidth={1.75} />
              </span>
              <h3 className="mt-4 text-[15px] font-semibold text-ink-1">{item.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{item.body}</p>
            </div>
          ))}
        </div>
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
              <Link href="/login" className={cn(buttonVariants({ size: "lg" }))}>
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
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="hover:text-ink-1">
              {link.label}
            </a>
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
  eyebrow,
  title,
  desc,
}: {
  eyebrow: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="max-w-[60ch]">
      <p className="text-overline text-ink-3">{eyebrow}</p>
      <h2 className="mt-3 font-display text-3xl leading-tight font-semibold tracking-tight text-balance text-ink-1">
        {title}
      </h2>
      <p className="mt-4 text-base leading-relaxed text-ink-2">{desc}</p>
    </div>
  );
}
