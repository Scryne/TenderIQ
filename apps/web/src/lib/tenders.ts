import type { StatusTone } from "@/components/status-pill";

/** İhale durumu sözlüğü — tek kaynak; her ekran buradan okur. */
export const TENDER_STATUS: Record<
  string,
  { label: string; tone: StatusTone; hint: string }
> = {
  draft: {
    label: "Taslak",
    tone: "neutral",
    hint: "Henüz şartname yüklenmedi.",
  },
  analyzing: {
    label: "Analiz ediliyor",
    tone: "info",
    hint: "Doküman ayrıştırılıyor ve bulgular çıkarılıyor.",
  },
  review_ready: {
    label: "İncelemeye hazır",
    tone: "success",
    hint: "Bulgular çıkarıldı; onayınızı bekliyor.",
  },
  archived: {
    label: "Arşivlendi",
    tone: "neutral",
    hint: "Kapatılmış ihale.",
  },
};

export function tenderStatusMeta(status: string): {
  label: string;
  tone: StatusTone;
  hint: string;
} {
  return TENDER_STATUS[status] ?? { label: status, tone: "neutral", hint: "" };
}

/** İşleme hattı fazları — ilerleme göstergesi bu sırayla çizilir. */
export const PIPELINE_STEPS = [
  { key: "queued", label: "Kuyrukta", detail: "İşleme sırası bekleniyor." },
  { key: "parsing", label: "Ayrıştırma", detail: "Sayfa düzeni ve tablolar okunuyor." },
  { key: "indexing", label: "İndeksleme", detail: "Metin parçaları aranabilir hale getiriliyor." },
  { key: "extracting", label: "Çıkarım", detail: "Gereksinim, belge, risk ve takvim çıkarılıyor." },
  { key: "review_ready", label: "Hazır", detail: "Bulgular incelemenizi bekliyor." },
] as const;

export const DOCUMENT_KINDS = [
  { value: "technical", label: "Teknik şartname" },
  { value: "administrative", label: "İdari şartname" },
  { value: "contract", label: "Sözleşme" },
  { value: "addendum", label: "Zeyilname" },
  { value: "other", label: "Diğer" },
] as const;

export const DOCUMENT_KIND_LABELS: Record<string, string> = Object.fromEntries(
  DOCUMENT_KINDS.map((kind) => [kind.value, kind.label]),
);

/** Abonelik durumu rozetleri. */
export const SUBSCRIPTION_STATUS: Record<string, { label: string; tone: StatusTone }> = {
  active: { label: "Etkin", tone: "success" },
  trialing: { label: "Deneme", tone: "info" },
  past_due: { label: "Ödeme bekliyor", tone: "warning" },
  canceled: { label: "İptal edildi", tone: "neutral" },
};

export const ROLE_LABELS: Record<string, string> = {
  admin: "Yönetici",
  member: "Üye",
  viewer: "İzleyici",
};

export const INVITATION_STATUS: Record<string, { label: string; tone: StatusTone }> = {
  pending: { label: "Bekliyor", tone: "warning" },
  accepted: { label: "Kabul edildi", tone: "success" },
  revoked: { label: "İptal edildi", tone: "neutral" },
};
