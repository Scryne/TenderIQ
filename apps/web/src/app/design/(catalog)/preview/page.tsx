"use client";

import Link from "next/link";
import { useState } from "react";

import { PanelView, type PanelData } from "@/components/panel/panel-view";
import { FindingRow, ReviewProgress } from "@/components/review/finding-row";
import { SectionHeader } from "@/components/shell/page-header";
import { PipelineProgress } from "@/components/tenders/pipeline";
import { TenderListView, type TenderRow } from "@/components/tenders/tender-list-view";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

/* ═══════════════════════════════════════════════════════════════════════════
 * EKRAN ÖNİZLEMELERİ — DESIGN.md §14 doğrulama yüzeyi
 *
 * Buradaki veriler MOCK'tur ve KVKK gereği hiçbir gerçek şartname içeriği
 * taşımaz: kurum ve firma adları uydurmadır, madde metinleri kamuya açık
 * tip sözleşme diline benzetilerek yazılmıştır (§13.4 — lorem ipsum da yasak,
 * gerçek belge de yasak).
 * ═══════════════════════════════════════════════════════════════════════════ */

const MOCK_TENDERS: TenderRow[] = [
  {
    id: "8f2c1a94-0000-4000-8000-000000000001",
    title: "2026/128764 — Bilgi işlem altyapı yenileme ve bakım hizmeti alımı",
    status: "review_ready",
  },
  {
    id: "8f2c1a94-0000-4000-8000-000000000002",
    title: "2026/119023 — Kurum içi yazılım geliştirme hizmet alımı",
    status: "analyzing",
  },
  {
    id: "8f2c1a94-0000-4000-8000-000000000003",
    title: "2026/104518 — Veri merkezi kesintisiz güç kaynağı bakımı",
    status: "review_ready",
  },
  {
    id: "8f2c1a94-0000-4000-8000-000000000004",
    title: "2026/098117 — Coğrafi bilgi sistemi lisans ve destek alımı",
    status: "draft",
  },
  {
    id: "8f2c1a94-0000-4000-8000-000000000005",
    title: "2025/221904 — Ağ anahtarı tedarik ve kurulum işi",
    status: "archived",
  },
];

const MOCK_PANEL: PanelData = {
  totalTenders: 5,
  reviewReady: 2,
  analyzing: 1,
  drafts: 1,
  quota: [
    { label: "Doküman", used: 82, limit: 100 },
    { label: "Sayfa", used: 4820, limit: 5000 },
  ],
  periodEnd: "2026-07-31T23:59:59Z",
  deadlines: [
    {
      id: "d1",
      tenderId: MOCK_TENDERS[0].id,
      tenderTitle: MOCK_TENDERS[0].title,
      label: "Son teklif verme tarihi",
      valueText: "18.08.2026 saat 10:30",
      date: new Date(2026, 7, 18),
      page: 3,
      section: "1.2",
    },
    {
      id: "d2",
      tenderId: MOCK_TENDERS[2].id,
      tenderTitle: MOCK_TENDERS[2].title,
      label: "Teslim süresi",
      valueText: "Sözleşme imzasından itibaren 120 takvim günü",
      date: null,
      page: 12,
      section: "9.1",
    },
    {
      id: "d3",
      tenderId: MOCK_TENDERS[0].id,
      tenderTitle: MOCK_TENDERS[0].title,
      label: "Zeyilname son tarihi",
      valueText: "29.07.2026",
      date: new Date(2026, 6, 29),
      page: 5,
      section: "2.4",
    },
  ],
  exposures: [
    {
      id: "e1",
      tenderId: MOCK_TENDERS[0].id,
      tenderTitle: MOCK_TENDERS[0].title,
      text: "İstekli, son beş yıl içinde tek sözleşmeye dayalı olarak teklif bedelinin %70'inden az olmamak üzere iş deneyimini belgelemek zorundadır.",
      source: "compliance",
      severity: "unmet",
      page: 44,
      section: "7.5.1",
    },
    {
      id: "e2",
      tenderId: MOCK_TENDERS[2].id,
      tenderTitle: MOCK_TENDERS[2].title,
      text: "Yüklenici, teslim gecikmesinin her takvim günü için sözleşme bedelinin binde 3'ü oranında gecikme cezası öder; ceza toplamı bedelin %20'sini aşarsa idare sözleşmeyi feshedebilir.",
      source: "risk",
      severity: "high",
      page: 42,
      section: "4.3.1",
    },
    {
      id: "e3",
      tenderId: MOCK_TENDERS[0].id,
      tenderTitle: MOCK_TENDERS[0].title,
      text: "Geçici teminat mektubunun geçerlilik süresi (90 gün), teklif geçerlilik süresini (120 gün) kapsamamaktadır.",
      source: "risk",
      severity: "high",
      page: 24,
      section: "7.3.2",
    },
  ],
  inProgress: [{ id: MOCK_TENDERS[1].id, title: MOCK_TENDERS[1].title }],
  detailLoading: false,
};

const EMPTY_PANEL: PanelData = {
  ...MOCK_PANEL,
  totalTenders: 0,
  reviewReady: 0,
  analyzing: 0,
  drafts: 0,
  deadlines: [],
  exposures: [],
  inProgress: [],
};

type ScreenState = "ready" | "empty" | "loading" | "error";

const STATES: { value: ScreenState; label: string }[] = [
  { value: "ready", label: "Dolu" },
  { value: "empty", label: "Boş" },
  { value: "loading", label: "Yükleniyor" },
  { value: "error", label: "Hata" },
];

export default function DesignPreviewPage() {
  const [state, setState] = useState<ScreenState>("ready");

  const listState = state === "loading" ? "loading" : state === "error" ? "error" : "ready";
  const tenders = state === "empty" ? [] : MOCK_TENDERS;

  return (
    <div className="flex flex-col gap-12">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-1">Ekran önizlemeleri</h1>
        <p className="mt-2 max-w-[68ch] text-sm text-ink-2">
          Sunum bileşenleri mock veriyle render edilir; backend gerekmez. Durum anahtarı beş
          durumun dördünü buradan gezdirir (filtre-boş durumu, listede arama yaparak tetiklenir).
        </p>
        <div className="mt-4">
          <Tabs value={state} onValueChange={(value) => setState(value as ScreenState)} className="gap-0">
            <TabsList variant="segment">
              {STATES.map((item) => (
                <TabsTrigger key={item.value} value={item.value}>
                  {item.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
      </div>

      {/* ── Kabuk ────────────────────────────────────────────────────────── *
       * Kabuk buraya GÖMÜLEMEZ: kenar çubuğu `position: fixed` kullanır (§7.1)
       * ve bir katalog kartının içine alındığında kabından taşar. Kendi tam
       * sayfa rotasında doğrulanır. */}
      <section>
        <SectionHeader
          title="Uygulama kabuğu"
          description="264px kenar çubuğu · 56px üst çubuk · çalışma alanı seçici · içerik 1440px'de sabitlenir."
        />
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-5">
          <p className="max-w-[68ch] text-sm text-ink-2">
            Kenar çubuğu sabit konumlandırılmıştır; gerçek davranışı (1024px altında çekmeceye
            düşmesi, daraltma, içeriğin ortalanması) ancak tam viewport&apos;ta görünür.
          </p>
          <Button asChild variant="secondary">
            <Link href="/design/shell">Tam sayfada aç</Link>
          </Button>
        </div>
      </section>

      {/* ── Panel ────────────────────────────────────────────────────────── */}
      <section>
        <SectionHeader title="Panel" description="Birincil iş: eleme riski taşıyan madde, kanıtıyla." />
        <PanelView
          data={state === "empty" ? EMPTY_PANEL : MOCK_PANEL}
          state={listState}
          errorMessage="Sunucuya ulaşılamıyor. Bağlantınızı kontrol edip yeniden deneyin."
          onRetry={() => undefined}
          newTenderAction={<Button>Yeni ihale</Button>}
        />
      </section>

      {/* ── İhale listesi ────────────────────────────────────────────────── */}
      <section>
        <SectionHeader
          title="İhale listesi"
          description="Segment sekmeleri + arama. Aramayla filtre-boş durumunu tetikleyebilirsiniz."
        />
        <TenderListView
          tenders={tenders}
          state={listState}
          errorMessage="İhaleler yüklenemedi."
          onRetry={() => undefined}
          newTenderAction={<Button>Yeni ihale</Button>}
        />
      </section>

      {/* ── İşleme hattı ─────────────────────────────────────────────────── */}
      <section>
        <SectionHeader title="İşleme hattı" description="Beş faz + hata durumu (yeniden dene ile)." />
        <div className="flex flex-col gap-4">
          {(["queued", "parsing", "extracting", "review_ready"] as const).map((status) => (
            <div key={status} className="rounded-lg border border-border bg-surface p-5">
              <p className="mb-4 font-mono text-[11px] text-ink-3">{status}</p>
              <PipelineProgress status={status} />
            </div>
          ))}
          <div className="rounded-lg border border-border bg-surface p-5">
            <p className="mb-4 font-mono text-[11px] text-ink-3">failed</p>
            <PipelineProgress
              status="failed"
              errorMessage="Dosya şifre korumalı olduğu için metne çevrilemedi."
              attempts={3}
              onRetry={() => undefined}
            />
          </div>
        </div>
      </section>

      {/* ── Bulgu satırı ─────────────────────────────────────────────────── */}
      <section>
        <SectionHeader
          title="Bulgu satırı"
          description="Çekirdek ekranın atom birimi. Aksiyonlar hover/focus'ta belirir; seçiliyken sabit kalır."
        />
        <div className="mb-4 flex items-center gap-4 rounded-lg border border-border bg-surface px-5 py-3">
          <span className="text-sm text-ink-2">İnceleme ilerlemesi</span>
          <ReviewProgress decided={12} total={18} />
        </div>
        <div className="flex flex-col gap-2">
          <FindingRow
            title="Yüklenici, teslim gecikmesinin her takvim günü için sözleşme bedelinin binde 3'ü oranında gecikme cezası öder."
            page={42}
            section="4.3.1"
            railTone="danger"
            tags={
              <>
                <Badge tone="danger" dot>
                  Yüksek
                </Badge>
                <Badge tone="outline">Cezai şart</Badge>
              </>
            }
            selected={false}
            onSelect={() => undefined}
            reviewStatus="pending"
            checked={false}
            onCheckedChange={() => undefined}
            actions={noopActions}
          />
          <FindingRow
            title="İş deneyimini gösteren belgeler: son beş yıl içinde bedel içeren tek sözleşmeye ilişkin iş deneyim belgesi."
            page={44}
            section="7.5.1"
            railTone="warning"
            tags={
              <>
                <Badge tone="outline">Belge</Badge>
                <Badge tone="warning">Zorunlu</Badge>
              </>
            }
            selected
            onSelect={() => undefined}
            reviewStatus="approved"
            checked
            onCheckedChange={() => undefined}
            actions={noopActions}
          />
          <FindingRow
            title="Teklif geçerlilik süresi 60 takvim günüdür."
            page={9}
            section="3.1"
            tags={<Badge tone="outline">Takvim</Badge>}
            selected={false}
            onSelect={() => undefined}
            reviewStatus="rejected"
            checked={false}
            onCheckedChange={() => undefined}
            actions={noopActions}
          />
          <FindingRow
            title="ISO/IEC 27001 bilgi güvenliği yönetim sistemi belgesi istenmektedir."
            page={46}
            section="7.5.4"
            railTone="success"
            tags={
              <Badge tone="success" dot>
                Karşılanıyor
              </Badge>
            }
            selected={false}
            onSelect={() => undefined}
            reviewStatus="edited"
            checked={false}
            onCheckedChange={() => undefined}
            actions={noopActions}
          />
        </div>
      </section>
    </div>
  );
}

const noopActions = {
  onApprove: () => undefined,
  onReject: () => undefined,
  onReset: () => undefined,
  onEdit: () => undefined,
  onComments: () => undefined,
  onHistory: () => undefined,
};
