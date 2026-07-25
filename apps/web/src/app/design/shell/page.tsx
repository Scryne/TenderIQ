"use client";

import { PanelView, type PanelData } from "@/components/panel/panel-view";
import { ShellFrame } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";

/**
 * Kabuk önizlemesi — TAM SAYFA (/design/shell).
 *
 * Katalog layout'unun (design/(catalog)/layout.tsx) DIŞINDA durur: aksi halde
 * katalogun üst çubuğu ile kabuğun kendi üst çubuğu üst üste biner ve
 * katalogun max-width kabı kabuğu hapseder.
 *
 * Neden ayrı rota: `ShellFrame` kenar çubuğunu `position: fixed` ile yerleştirir
 * (§7.1 — içerik kaydırılırken çubuk sabit kalmalı). Bu yüzden bir katalog
 * kartının içine gömülemez; kabından taşar. Kabuğun gerçek davranışı —
 * 1024px altında çekmeceye düşmesi, daraltma, içeriğin 1440px'de sabitlenmesi —
 * ancak tam viewport'ta doğrulanabilir.
 */
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
      tenderId: "t1",
      tenderTitle: "2026/128764 — Bilgi işlem altyapı yenileme ve bakım hizmeti alımı",
      label: "Son teklif verme tarihi",
      valueText: "18.08.2026 saat 10:30",
      date: new Date(2026, 7, 18),
      page: 3,
      section: "1.2",
    },
    {
      id: "d2",
      tenderId: "t3",
      tenderTitle: "2026/104518 — Veri merkezi kesintisiz güç kaynağı bakımı",
      label: "Teslim süresi",
      valueText: "Sözleşme imzasından itibaren 120 takvim günü",
      date: null,
      page: 12,
      section: "9.1",
    },
  ],
  exposures: [
    {
      id: "e1",
      tenderId: "t1",
      tenderTitle: "2026/128764 — Bilgi işlem altyapı yenileme ve bakım hizmeti alımı",
      text: "İstekli, son beş yıl içinde tek sözleşmeye dayalı olarak teklif bedelinin %70'inden az olmamak üzere iş deneyimini belgelemek zorundadır.",
      source: "compliance",
      severity: "unmet",
      page: 44,
      section: "7.5.1",
    },
    {
      id: "e2",
      tenderId: "t3",
      tenderTitle: "2026/104518 — Veri merkezi kesintisiz güç kaynağı bakımı",
      text: "Yüklenici, teslim gecikmesinin her takvim günü için sözleşme bedelinin binde 3'ü oranında gecikme cezası öder.",
      source: "risk",
      severity: "high",
      page: 42,
      section: "4.3.1",
    },
  ],
  inProgress: [
    { id: "t2", title: "2026/119023 — Kurum içi yazılım geliştirme hizmet alımı" },
  ],
  detailLoading: false,
};

export default function ShellPreviewPage() {
  return (
    <ShellFrame
      pathname="/panel"
      user={{ name: "Berkay Yıldız", email: "berkay@ornekbilisim.com.tr", role: "admin" }}
      orgs={[
        { id: "1", name: "Örnek Bilişim A.Ş.", planName: "Pro", isActive: true },
        { id: "2", name: "Anadolu Sistem Ltd.", planName: "Ücretsiz", isActive: false },
      ]}
      onSwitchOrg={() => undefined}
      onLogout={() => undefined}
    >
      <PageHeader
        title="Panel"
        description="Açık ihalelerinizde eleme riski taşıyan maddeler ve yaklaşan teklif tarihleri."
        actions={<Button variant="secondary">Yeni ihale</Button>}
      />
      <PanelView data={MOCK_PANEL} state="ready" newTenderAction={<Button>Yeni ihale</Button>} />
    </ShellFrame>
  );
}
