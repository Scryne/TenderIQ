"use client";

import { AlertTriangle, Check, Download, Plus, ShieldAlert, Trash2 } from "lucide-react";
import { useState } from "react";

import { EvidenceCoverage, EvidenceQuote, EvidenceRail, SourceRef } from "@/components/evidence";
import { DistributionList, Meter, MetricCard } from "@/components/metric";
import { FilterBar, FilterChip, ToggleChip } from "@/components/filters";
import { SectionHeader } from "@/components/shell/page-header";
import { EmptyState, ErrorState, FilterEmptyState, InlineError } from "@/components/states";
import { StatusPill } from "@/components/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";

/* Token vitrini — paleti 20 ekran kodlandıktan SONRA değil, şimdi görün. */

const SURFACES = [
  { name: "canvas", token: "--canvas", hint: "sayfa zemini" },
  { name: "surface", token: "--surface", hint: "kart, panel" },
  { name: "surface-2", token: "--surface-2", hint: "tablo başlığı, input" },
  { name: "border", token: "--border", hint: "hairline ayırıcı" },
  { name: "border-strong", token: "--border-strong", hint: "kontrol kenarlığı · 3:1" },
];

const INKS = [
  { name: "ink-1", token: "--ink-1", ratio: "17,5:1", hint: "başlık, ana metin" },
  { name: "ink-2", token: "--ink-2", ratio: "9,6:1", hint: "açıklama" },
  { name: "ink-3", token: "--ink-3", ratio: "5,1:1", hint: "etiket, meta" },
];

const SEMANTIC = [
  { name: "accent", token: "--accent", ratio: "17,5:1", hint: "birincil eylem = mürekkep" },
  { name: "success", token: "--success", ratio: "5,0:1", hint: "onaylandı, karşılanıyor" },
  { name: "warning", token: "--warning", ratio: "5,1:1", hint: "zorunlu, kota eşiği" },
  { name: "danger", token: "--danger", ratio: "6,6:1", hint: "yüksek risk, karşılanmıyor" },
  { name: "info", token: "--info", ratio: "6,1:1", hint: "analiz sürüyor" },
];

const TYPE_SCALE = [
  { cls: "text-4xl", label: "4xl · 40/44 · -0.025em", sample: "Hero başlığı" },
  { cls: "text-3xl", label: "3xl · 30/36 · -0.02em", sample: "Metrik değeri 184.392" },
  { cls: "text-2xl", label: "2xl · 24/32 · -0.015em", sample: "Sayfa başlığı" },
  { cls: "text-xl", label: "xl · 20/28 · -0.01em", sample: "Bölüm başlığı" },
  { cls: "text-lg", label: "lg · 16/24 · -0.005em", sample: "Kart başlığı" },
  { cls: "text-base", label: "base · 14/22", sample: "Arayüz varsayılanı — Şartname gereksinimi" },
  { cls: "text-sm", label: "sm · 13/20", sample: "Tablo hücresi, ikincil metin" },
  { cls: "text-xs", label: "xs · 12/16 · +0.01em", sample: "Yardımcı metin, rozet" },
];

export default function DesignTokensPage() {
  const [filterA, setFilterA] = useState("all");
  const [filterB, setFilterB] = useState("high");
  const [toggle, setToggle] = useState(true);

  return (
    <div className="flex flex-col gap-12">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-1">
          Tasarım token&apos;ları · Yön A “Mürekkep”
        </h1>
        <p className="mt-2 max-w-[68ch] text-sm text-ink-2">
          Monokrom sistem: birincil eylem rengi mürekkeptir, kroma yalnızca dört semantik durumda
          ve kanıt vurgusunda bulunur. Koyu temada mürekkep kâğıda döner. Kontrast oranları
          hesaplanmıştır (hedef metin 4,5:1 · UI 3:1).
        </p>
      </div>

      {/* ── Renk ─────────────────────────────────────────────────────────── */}
      <section>
        <SectionHeader title="Yüzeyler ve kenarlıklar" description="Üç yüzey seviyesi, iki kenarlık." />
        <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(180px,1fr))]">
          {SURFACES.map((item) => (
            <div key={item.name} className="rounded-lg border border-border bg-surface p-4">
              <div
                className="h-14 w-full rounded-sm border border-border"
                style={{ background: `var(${item.token})` }}
              />
              <p className="mt-3 font-mono text-xs text-ink-1">{item.name}</p>
              <p className="mt-0.5 text-xs text-ink-3">{item.hint}</p>
            </div>
          ))}
        </div>

        <SectionHeader
          title="Mürekkep tonları"
          description="Üç ton yeter; dördüncüsü hiyerarşiyi bulanıklaştırır."
          className="mt-8"
        />
        <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
          {INKS.map((item) => (
            <div key={item.name} className="rounded-lg border border-border bg-surface p-4">
              <p className="text-lg font-semibold" style={{ color: `var(${item.token})` }}>
                Şartname maddesi
              </p>
              <p className="mt-2 font-mono text-xs text-ink-1">{item.name}</p>
              <p className="mt-0.5 text-xs text-ink-3">
                {item.hint} · {item.ratio}
              </p>
            </div>
          ))}
        </div>

        <SectionHeader
          title="Aksan ve durum renkleri"
          description="Aksan kromatik değil: mürekkebin kendisi. Durum renkleri sabit anlam taşır."
          className="mt-8"
        />
        <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
          {SEMANTIC.map((item) => (
            <div key={item.name} className="rounded-lg border border-border bg-surface p-4">
              <div className="flex items-center gap-2">
                <span
                  className="size-8 shrink-0 rounded-sm"
                  style={{ background: `var(${item.token})` }}
                />
                <span className="min-w-0 font-mono text-xs text-ink-1">{item.name}</span>
              </div>
              <p className="mt-2 text-xs text-ink-3">
                {item.hint} · {item.ratio}
              </p>
            </div>
          ))}
        </div>

        <SectionHeader
          title="Kanıt vurgusu"
          description="Ürünün tek dolgulu rengi. PDF katmanında ve alıntı bloğunda aynı ton kullanılır."
          className="mt-8"
        />
        <div className="rounded-lg border border-border bg-surface p-5">
          <p className="max-w-[68ch] text-sm leading-7 text-ink-2">
            7.3.2. İstekliler teklifleriyle birlikte geçici teminat sunacaktır.{" "}
            <mark className="evidence-mark box-decoration-clone px-0.5 font-medium text-ink-1">
              Geçici teminat mektubu ihale tarihinden itibaren 90 gün geçerli olmalıdır.
            </mark>{" "}
            Teklif geçerlilik süresi 120 takvim günüdür.
          </p>
        </div>
      </section>

      {/* ── Tipografi ────────────────────────────────────────────────────── */}
      <section>
        <SectionHeader
          title="Tipografi"
          description="Instrument Sans (başlık) · Inter Tight (arayüz) · IBM Plex Mono (koordinat, sayı). Üçü de latin-ext taşır."
        />
        <div className="rounded-lg border border-border bg-surface">
          {TYPE_SCALE.map((step) => (
            <div
              key={step.cls}
              className="flex flex-wrap items-baseline justify-between gap-4 border-b border-border px-5 py-3.5 last:border-b-0"
            >
              <span
                className={`${step.cls} min-w-0 font-display font-semibold text-ink-1`}
              >
                {step.sample}
              </span>
              <span className="shrink-0 font-mono text-[11px] text-ink-3">{step.label}</span>
            </div>
          ))}
          <div className="flex flex-wrap items-baseline justify-between gap-4 border-t border-border px-5 py-3.5">
            <span className="text-overline text-ink-3">OVERLINE · BÖLÜM BAŞLIĞI ETİKETİ</span>
            <span className="shrink-0 font-mono text-[11px] text-ink-3">
              11/14 · 600 · +0.06em · CSS uppercase YOK (Ek B.3)
            </span>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-border bg-surface p-5">
          <p className="text-overline text-ink-3">TÜRKÇE GLİF DENETİMİ</p>
          <p className="mt-2 font-display text-2xl text-ink-1">
            İstanbul Ağrı Şırnak Çorum Öğüt Üzüm · ı İ ğ Ğ ş Ş ç Ç ö Ö ü Ü
          </p>
          <p className="mt-2 font-mono text-sm text-ink-2">
            2026/128764 · s.42 · md.4.3.1 · {formatCurrency(1234567)} · {formatPercent(12.4)} ·{" "}
            {formatNumber(184392)}
          </p>
        </div>
      </section>

      {/* ── Geometri ─────────────────────────────────────────────────────── */}
      <section>
        <SectionHeader
          title="Radius ve gölge"
          description="İki görünür radius (6 kontrol · 10 kart). Gölge yalnız yüzen yüzeylerde; kartlar 1px kenarlık kullanır."
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { cls: "rounded-sm", label: "sm · 6px", hint: "rozet, input, buton" },
            { cls: "rounded-md", label: "md · 8px", hint: "dropdown, popover" },
            { cls: "rounded-lg", label: "lg · 10px", hint: "kart, panel" },
            { cls: "rounded-xl", label: "xl · 12px", hint: "modal" },
          ].map((item) => (
            <div key={item.cls} className="rounded-lg border border-border bg-surface p-4">
              <div className={`h-12 w-full bg-surface-2 ${item.cls}`} />
              <p className="mt-3 font-mono text-xs text-ink-1">{item.label}</p>
              <p className="mt-0.5 text-xs text-ink-3">{item.hint}</p>
            </div>
          ))}
        </div>
        {/* Gölgeler surface-2 zemine oturur: canvas ile surface arasındaki fark
            çok küçük olduğu için beyaz üstünde beyaz gölge görünmüyordu. */}
        <div className="mt-3 grid gap-3 rounded-lg bg-surface-2 p-4 sm:grid-cols-3">
          {[
            { cls: "shadow-sm", label: "shadow-sm", hint: "segment seçili öğe" },
            { cls: "shadow-md", label: "shadow-md", hint: "dropdown, toast" },
            { cls: "shadow-lg", label: "shadow-lg", hint: "yalnız modal" },
          ].map((item) => (
            <div key={item.cls}>
              <div className={`h-14 w-full rounded-lg bg-surface ${item.cls}`} />
              <p className="mt-3 font-mono text-xs text-ink-1">{item.label}</p>
              <p className="mt-0.5 text-xs text-ink-3">{item.hint}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── İmza öğesi ───────────────────────────────────────────────────── */}
      <section>
        <SectionHeader
          title="İmza öğesi · kaynak şeridi"
          description="Bulguyu kanıtına bağlayan 2px dikey çizgi + mono koordinat. Yalnız kanıt bağı olan yerde çizilir."
        />
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-5">
            {(["ink", "danger", "warning", "success"] as const).map((tone) => (
              <EvidenceRail key={tone} tone={tone}>
                <p className="text-[13.5px] leading-5 text-ink-1">
                  {tone === "danger"
                    ? "Gecikme cezası günlük binde 3 olarak belirlenmiştir."
                    : tone === "warning"
                      ? "İş deneyim belgesi sunulması zorunludur."
                      : tone === "success"
                        ? "ISO 27001 belgesi gereksinimi karşılanıyor."
                        : "Son teklif verme tarihi: 18.08.2026 — 10:30"}
                </p>
                <div className="mt-2">
                  <SourceRef page={42} section="4.3.1" />
                </div>
              </EvidenceRail>
            ))}
          </div>
          <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5">
            <EvidenceQuote
              quote="Geçici teminat mektubu, ihale tarihinden itibaren 90 gün geçerli olmalıdır."
              page={24}
              section="7.3.2"
              documentName="teknik-sartname.pdf"
            />
            <div className="flex flex-wrap items-center gap-4 border-t border-border pt-4">
              <EvidenceCoverage grounded={18} total={18} />
              <EvidenceCoverage grounded={15} total={18} />
            </div>
          </div>
        </div>
      </section>

      {/* ── Bileşenler ───────────────────────────────────────────────────── */}
      <section>
        <SectionHeader title="Butonlar" description="Yükseklik sm 32 · md 36 · lg 40. Uppercase yok." />
        <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Button>Bulguları incele</Button>
            <Button variant="secondary">
              <Download strokeWidth={1.75} /> Rapor indir
            </Button>
            <Button variant="ghost">Vazgeç</Button>
            <Button variant="danger">
              <Trash2 strokeWidth={1.75} /> Üyeyi çıkar
            </Button>
            <Button variant="danger-ghost">Oturumu kapat</Button>
            <Button variant="link">Tümünü gör</Button>
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
            <Button size="sm">
              <Plus strokeWidth={2} /> Yeni ihale
            </Button>
            <Button size="md">Orta (36px)</Button>
            <Button size="lg">Büyük (40px)</Button>
            <Button size="xs" variant="secondary">
              Küçük
            </Button>
            <Button size="icon-sm" variant="ghost" aria-label="Onayla">
              <Check strokeWidth={2.5} />
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
            <Button loading>Kaydediliyor</Button>
            <Button variant="secondary" loading>
              Yükleniyor
            </Button>
            <Button disabled>Devre dışı</Button>
          </div>
        </div>
      </section>

      <section>
        <SectionHeader
          title="Rozetler"
          description="Yükseklik 22px · radius 6px — pill DEĞİL. Metin her zaman yazılır."
        />
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface p-5">
          <StatusPill tone="success" label="Onaylandı" />
          <StatusPill tone="warning" label="Zorunlu" />
          <StatusPill tone="danger" label="Yüksek risk" />
          <StatusPill tone="info" label="Analiz ediliyor" />
          <StatusPill tone="neutral" label="Onay bekliyor" />
          <Badge tone="ink">İnsan onayı</Badge>
          <Badge tone="outline">Cezai şart</Badge>
          <Badge tone="danger" dot>
            <ShieldAlert strokeWidth={2} /> Karşılanmıyor
          </Badge>
        </div>
      </section>

      <section>
        <SectionHeader title="Form alanları" description="36px · 1px border-strong · focus'ta mürekkep kenarlık." />
        <div className="grid max-w-[480px] gap-4 rounded-lg border border-border bg-surface p-5">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="demo-title">
              İhale başlığı <span className="text-danger">*</span>
            </Label>
            <Input id="demo-title" placeholder="2026/128764 — Bilgi işlem altyapı yenileme" />
            <p className="text-xs text-ink-3">İhale kayıt numarası ve konusu.</p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="demo-error">E-posta</Label>
            <Input id="demo-error" aria-invalid defaultValue="ad.soyad@" />
            <p className="text-xs text-danger">
              E-posta adresi ad@site.com biçiminde olmalı.
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="demo-select">Doküman türü</Label>
            <Select defaultValue="technical">
              <SelectTrigger id="demo-select" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="technical">Teknik şartname</SelectItem>
                <SelectItem value="administrative">İdari şartname</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="demo-textarea">Yetkinlik beyanı</Label>
            <Textarea id="demo-textarea" placeholder="ISO 27001 belgemiz güncel…" />
          </div>
          <label className="flex items-center gap-2 text-sm text-ink-2">
            <Checkbox defaultChecked /> Onay bekleyenleri dahil et
          </label>
        </div>
      </section>

      <section>
        <SectionHeader title="Segment, sekme ve filtre çipi" description="Aktif filtre mürekkep zemin alır — unutulmaz." />
        <div className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-5">
          <Tabs defaultValue="requirements" className="gap-0">
            <TabsList variant="segment">
              <TabsTrigger value="requirements">Gereksinimler</TabsTrigger>
              <TabsTrigger value="deliverables">Belgeler</TabsTrigger>
              <TabsTrigger value="risks">Riskler</TabsTrigger>
              <TabsTrigger value="timeline">Takvim</TabsTrigger>
            </TabsList>
          </Tabs>
          <Tabs defaultValue="general" className="gap-0">
            <TabsList variant="underline">
              <TabsTrigger value="general">Genel</TabsTrigger>
              <TabsTrigger value="history">Geçmiş</TabsTrigger>
              <TabsTrigger value="documents">Belgeler</TabsTrigger>
            </TabsList>
          </Tabs>
          <FilterBar dirty onReset={() => setFilterB("all")}>
            <FilterChip
              label="Tüm türler"
              value={filterA}
              options={[
                { value: "technical", label: "Teknik" },
                { value: "administrative", label: "İdari" },
              ]}
              onChange={setFilterA}
            />
            <FilterChip
              label="Tüm şiddetler"
              value={filterB}
              options={[
                { value: "high", label: "Yüksek" },
                { value: "medium", label: "Orta" },
              ]}
              onChange={setFilterB}
            />
            <ToggleChip label="Yalnız zorunlu" pressed={toggle} onPressedChange={setToggle} />
          </FilterBar>
        </div>
      </section>

      <section>
        <SectionHeader
          title="Metrik kartı ve ölçerler"
          description="Tek varyant: etiket → değer → niteleyici (+ hedefe göre 4px çubuk)."
        />
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
          <MetricCard
            label="ELEME RİSKİ"
            value="4"
            unit="madde"
            tone="danger"
            icon={ShieldAlert}
            qualifier="2 ihalede"
          />
          <MetricCard
            label="İNCELEMEYE HAZIR"
            value="3"
            unit="ihale"
            tone="info"
            icon={Check}
            qualifier="Toplam 11 proje içinde"
          />
          <MetricCard
            label="AYLIK KOTA"
            value="82"
            unit="/ 100"
            icon={AlertTriangle}
            tone="warning"
            progress={82}
            qualifier="Dönem sonu 31.07.2026"
          />
        </div>
        <div className="mt-4 grid gap-8 rounded-lg border border-border bg-surface p-5 sm:grid-cols-2 sm:gap-6">
          <div className="flex flex-col gap-5">
            <p className="text-overline text-ink-3">KOTA ÖLÇERİ · EŞİĞE GÖRE TON DEĞİŞTİRİR</p>
            <Meter label="Doküman" used={82} limit={100} formatValue={formatNumber} />
            <Meter label="Sayfa" used={4820} limit={5000} formatValue={formatNumber} />
            <Meter label="Kullanıcı" used={3} limit={null} formatValue={formatNumber} />
          </div>
          <div className="flex flex-col gap-5">
            <p className="text-overline text-ink-3">
              SIRALI DAĞILIM · RİSK MADDELERİ KATEGORİYE GÖRE
            </p>
            <DistributionList
              items={[
                { label: "Cezai şart", value: 12, tone: "danger" },
                { label: "Teminat", value: 8, tone: "warning" },
                { label: "Ödeme koşulu", value: 5 },
                { label: "Fesih", value: 2 },
              ]}
              formatValue={formatNumber}
            />
          </div>
        </div>
      </section>

      <section>
        <SectionHeader title="Tablo" description="Satır 48px · zebra yok · başlık sticky · sayısal sütun sağa hizalı." />
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          <Table>
            <TableHeader>
              <TableRow className="border-b-0 hover:bg-transparent">
                <TableHead>İHALE</TableHead>
                <TableHead className="w-44">DURUM</TableHead>
                <TableHead numeric className="w-32">
                  BULGU
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[
                { title: "2026/128764 — Bilgi işlem altyapı yenileme", status: "review_ready", count: 18 },
                { title: "2026/119023 — Yazılım geliştirme hizmet alımı", status: "analyzing", count: 0 },
                { title: "2026/104518 — Veri merkezi bakım hizmeti", status: "draft", count: 0 },
              ].map((row) => (
                <TableRow key={row.title} interactive>
                  <TableCell className="font-medium">{row.title}</TableCell>
                  <TableCell>
                    <StatusPill
                      tone={
                        row.status === "review_ready"
                          ? "success"
                          : row.status === "analyzing"
                            ? "info"
                            : "neutral"
                      }
                      label={
                        row.status === "review_ready"
                          ? "İncelemeye hazır"
                          : row.status === "analyzing"
                            ? "Analiz ediliyor"
                            : "Taslak"
                      }
                    />
                  </TableCell>
                  <TableCell numeric>{formatNumber(row.count)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* ── Durumlar ─────────────────────────────────────────────────────── */}
      <section>
        <SectionHeader
          title="Durum tasarımı"
          description="Beş durum da kodlanır. Boş durum bir davettir, hata çözüm söyler."
        />
        <div className="grid gap-4 lg:grid-cols-2">
          <EmptyState
            icon={Plus}
            title="Henüz ihale projesi yok"
            description="Bir proje açıp şartnameyi yükleyin; analiz kendiliğinden başlar."
            action={<Button>Yeni ihale</Button>}
          />
          <FilterEmptyState query="teminat" onReset={() => undefined} />
          <ErrorState detail="HTTP 503 · req_a8f2c1" onRetry={() => undefined} />
          <Card>
            <CardHeader className="block">
              <CardTitle>Kart içi durumlar</CardTitle>
              <CardDescription>Kısmi hata sayfayı çökertmez.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 pt-0">
              <InlineError
                message="Uygunluk sonuçları yüklenemedi."
                onRetry={() => undefined}
              />
              <div className="flex flex-col gap-2">
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
