import type { components, paths } from "@tenderiq/api-client";

import type { StatusTone } from "@/components/status-pill";

/** Üretilen istemciden bulgu yanıt tipleri (B.5 sözleşmesi — elle tip yazılmaz). */
type Ok<P extends keyof paths> = paths[P] extends {
  get: { responses: { 200: { content: { "application/json": infer T } } } };
}
  ? T
  : never;

export type RequirementFinding = Ok<"/api/v1/tenders/{tender_id}/requirements">[number];
export type DeliverableFinding = Ok<"/api/v1/tenders/{tender_id}/deliverables">[number];
export type RiskFinding = Ok<"/api/v1/tenders/{tender_id}/risks">[number];
export type TimelineFinding = Ok<"/api/v1/tenders/{tender_id}/timeline">[number];
export type ComplianceFinding = Ok<"/api/v1/tenders/{tender_id}/compliance">[number];
export type FindingSource = RequirementFinding["source"];

export type AnyFinding =
  | RequirementFinding
  | DeliverableFinding
  | RiskFinding
  | TimelineFinding
  | ComplianceFinding;

export type FindingCategory =
  | "requirements"
  | "deliverables"
  | "risks"
  | "timeline"
  | "compliance";

export const CATEGORY_LABELS: Record<FindingCategory, string> = {
  requirements: "Gereksinimler",
  deliverables: "Belgeler",
  risks: "Riskler",
  timeline: "Takvim",
  compliance: "Uygunluk",
};

/** İnceleme uçlarının (yorum/geçmiş/bulk) kullandığı tekil bulgu türü anahtarı. */
export type FindingKind = components["schemas"]["FindingKind"];
export type ReviewStatus = components["schemas"]["ReviewStatus"];
export type ReviewAction = components["schemas"]["ReviewAction"];

export const CATEGORY_TO_KIND: Record<FindingCategory, FindingKind> = {
  requirements: "requirement",
  deliverables: "deliverable",
  risks: "risk",
  timeline: "timeline",
  compliance: "compliance",
};

/** İnceleme durumu rozetleri (§7.8 tonları): üç durum + red (Sprint 3.2). */
export const REVIEW_STATUS: Record<ReviewStatus, { label: string; tone: StatusTone }> = {
  pending: { label: "Onay bekliyor", tone: "neutral" },
  approved: { label: "Onaylandı", tone: "success" },
  edited: { label: "Düzeltildi", tone: "info" },
  rejected: { label: "Reddedildi", tone: "danger" },
};

export const REQUIREMENT_KIND_LABELS: Record<string, string> = {
  technical: "Teknik",
  administrative: "İdari",
  financial: "Mali",
};

export const DELIVERABLE_KIND_LABELS: Record<string, string> = {
  document: "Belge",
  certificate: "Sertifika",
  guarantee: "Teminat",
  other: "Diğer",
};

export const RISK_SEVERITY: Record<string, { label: string; tone: StatusTone }> = {
  high: { label: "Yüksek", tone: "danger" },
  medium: { label: "Orta", tone: "warning" },
  low: { label: "Düşük", tone: "neutral" },
};

export const RISK_CATEGORY_LABELS: Record<string, string> = {
  penalty: "Cezai şart",
  termination: "Fesih",
  warranty: "Garanti",
  payment: "Ödeme",
  other: "Diğer",
};

export const TIMELINE_KIND_LABELS: Record<string, string> = {
  tender_date: "İhale tarihi",
  bid_deadline: "Son teklif",
  delivery: "Teslim/süre",
  warranty: "Garanti süresi",
  other: "Diğer",
};

export const COMPLIANCE_STATUS: Record<string, { label: string; tone: StatusTone }> = {
  met: { label: "Karşılanıyor", tone: "success" },
  partial: { label: "Kısmen", tone: "warning" },
  unmet: { label: "Karşılanmıyor", tone: "danger" },
};

/** Kaynak referansı metni: `s. 12 · §2.3 Teknik Şartlar` (mono ile dizilir). */
export function sourceRef(source: FindingSource): string {
  const section = source.section?.trim();
  return section != null && section !== "" ? `s. ${source.page} · ${section}` : `s. ${source.page}`;
}

/** PDF vurgu katmanının çizeceği kutu; konumsuz formatlarda (DOCX/XLSX) null. */
export function sourceBbox(
  source: FindingSource,
): { x0: number; y0: number; x1: number; y1: number } | null {
  if (
    source.bbox_x0 == null ||
    source.bbox_y0 == null ||
    source.bbox_x1 == null ||
    source.bbox_y1 == null
  ) {
    return null;
  }
  return { x0: source.bbox_x0, y0: source.bbox_y0, x1: source.bbox_x1, y1: source.bbox_y1 };
}
