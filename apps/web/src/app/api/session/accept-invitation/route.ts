// Üye davetini kabul eder (kimliksiz): backend'e iletir, yeni hesap için dönen
// otomatik-giriş token'larını httpOnly cookie'lere yazar (Sprint 3.3-E-2). Mevcut
// kullanıcı için token dönmez (link sızma savunması) — yalnız üyelik eklenir.

import { NextRequest, NextResponse } from "next/server";

import { API_URL } from "@/lib/server/backend";
import { writeSessionCookies } from "@/lib/server/session";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const body: unknown = await request.json().catch(() => null);
  if (body === null || typeof body !== "object") {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Geçersiz istek gövdesi." } },
      { status: 422 },
    );
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_URL}/api/v1/invitations/accept`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: { code: "internal_error", message: "Davet servisine ulaşılamadı." } },
      { status: 502 },
    );
  }

  const payload: unknown = await backendResponse.json().catch(() => null);
  if (!backendResponse.ok) {
    return NextResponse.json(
      payload ?? { error: { code: "internal_error", message: "Davet kabul edilemedi." } },
      { status: backendResponse.status },
    );
  }

  const result = payload as {
    organization_id?: string;
    account_created?: boolean;
    tokens?: { access_token?: string; refresh_token?: string | null } | null;
  };
  const response = NextResponse.json({
    ok: true,
    account_created: result.account_created ?? false,
  });
  // Yeni hesap: otomatik giriş token'ları httpOnly cookie'lere yazılır.
  if (result.tokens != null && typeof result.tokens.access_token === "string") {
    writeSessionCookies(response, {
      access_token: result.tokens.access_token,
      refresh_token: result.tokens.refresh_token,
    });
  }
  return response;
}
