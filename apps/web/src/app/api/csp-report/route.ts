/**
 * CSP ihlal raporlarının toplandığı uç.
 *
 * Politika artık ZORLAYICI (bkz. `lib/security/csp.ts`), yani bir ihlal aynı
 * zamanda **kırılan bir özellik** demektir. Rapor toplamanın amacı budur:
 * "sayfa çalışmıyor" şikâyeti gelmeden önce hangi kaynağın engellendiğini
 * görmek. Rapor akmıyorsa politikayı sıkılaştırmak kör uçuşa döner.
 *
 * İki biçim birden kabul edilir çünkü tarayıcılar ikisini de gönderiyor:
 * `report-uri` → `application/csp-report` (tek nesne, `csp-report` anahtarı),
 * `report-to`  → `application/reports+json` (dizi, `type: "csp-violation"`).
 */

import * as Sentry from "@sentry/nextjs";
import { NextRequest, NextResponse } from "next/server";

/** Gövde üst sınırı. Uç kimlik doğrulamasızdır (tarayıcı anonim POST eder). */
const MAX_BODY_BYTES = 64 * 1024;

/** Log satırında bir alanın en fazla kaç karakteri yazılır. */
const MAX_FIELD_LENGTH = 300;

type ViolationFields = {
  documentUrl?: string;
  blockedUrl?: string;
  directive?: string;
  disposition?: string;
  sourceFile?: string;
  lineNumber?: number;
};

function truncate(value: unknown): string | undefined {
  if (typeof value !== "string" || value.length === 0) return undefined;
  return value.length > MAX_FIELD_LENGTH ? `${value.slice(0, MAX_FIELD_LENGTH)}…` : value;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

/** `report-uri` ve `report-to` gövdelerini tek biçime indirir. */
function normalize(payload: unknown): ViolationFields[] {
  const records: Record<string, unknown>[] = [];

  if (Array.isArray(payload)) {
    // report-to: [{ type, url, body: {...} }]
    for (const entry of payload) {
      if (!entry || typeof entry !== "object") continue;
      const item = entry as Record<string, unknown>;
      if (item.type !== undefined && item.type !== "csp-violation") continue;
      const body = item.body;
      if (body && typeof body === "object") records.push(body as Record<string, unknown>);
    }
  } else if (payload && typeof payload === "object") {
    const item = payload as Record<string, unknown>;
    // report-uri: { "csp-report": {...} }
    const legacy = item["csp-report"];
    if (legacy && typeof legacy === "object") records.push(legacy as Record<string, unknown>);
    else records.push(item);
  }

  // Alan adları iki biçimde farklıdır (`blocked-uri` ↔ `blockedURL`); ikisi de
  // okunur, aksi hâlde raporun yarısı boş görünür ve teşhis işe yaramaz.
  return records.map((record) => ({
    documentUrl: truncate(record["document-uri"] ?? record.documentURL),
    blockedUrl: truncate(record["blocked-uri"] ?? record.blockedURL),
    directive: truncate(record["effective-directive"] ?? record.effectiveDirective),
    disposition: truncate(record.disposition),
    sourceFile: truncate(record["source-file"] ?? record.sourceFile),
    lineNumber: asNumber(record["line-number"] ?? record.lineNumber),
  }));
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (declaredLength > MAX_BODY_BYTES) {
    return new NextResponse(null, { status: 413 });
  }

  let payload: unknown;
  try {
    const raw = await request.text();
    if (raw.length > MAX_BODY_BYTES) return new NextResponse(null, { status: 413 });
    payload = JSON.parse(raw);
  } catch {
    // Bozuk gövde bir arıza değil (tarayıcı sürümleri farklı gönderiyor);
    // 204 dönüp sessizce geç — tarayıcı zaten yeniden denemez.
    return new NextResponse(null, { status: 204 });
  }

  for (const violation of normalize(payload)) {
    // Yalnız politikanın gerçekten adlandırdığı ihlaller loglanır; boş
    // kayıtlar gürültüdür.
    if (!violation.directive && !violation.blockedUrl) continue;

    const summary =
      `CSP ihlali · ${violation.directive ?? "bilinmeyen yönerge"}` +
      ` · engellenen: ${violation.blockedUrl ?? "-"}` +
      ` · sayfa: ${violation.documentUrl ?? "-"}` +
      (violation.sourceFile
        ? ` · kaynak: ${violation.sourceFile}:${violation.lineNumber ?? "?"}`
        : "");

    // Sunucu logu her ortamda çalışır; Sentry yalnız DSN varsa.
    console.warn(summary);
    Sentry.captureMessage(summary, {
      level: "warning",
      tags: { kind: "csp-violation", directive: violation.directive ?? "unknown" },
    });
  }

  return new NextResponse(null, { status: 204 });
}
