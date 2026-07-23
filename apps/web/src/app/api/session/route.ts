// Oturum uçları: backend'e giriş yapar, kısa erişim token'ını + rotasyonlu refresh
// token'ını httpOnly cookie'lere yazar; çıkışta oturumu backend'de iptal eder.
//
// Token'lar tarayıcı JS'ine hiç verilmez (XSS'e karşı); API çağrıları aynı-origin
// /api/v1 proxy'si üzerinden gider ve erişim token'ı süresi dolunca proxy refresh
// token'la sessizce yeniler.

import { NextRequest, NextResponse } from "next/server";

import { API_URL, REFRESH_COOKIE, SESSION_COOKIE } from "@/lib/server/backend";
import { writeSessionCookies } from "@/lib/server/session";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const credentials: unknown = await request.json().catch(() => null);
  if (credentials === null || typeof credentials !== "object") {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Geçersiz istek gövdesi." } },
      { status: 422 },
    );
  }

  // Gerçek istemci IP'si backend oran sınırlamasına taşınır (bkz. /api/v1 proxy'si).
  const headers = new Headers({ "content-type": "application/json" });
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor !== null) headers.set("x-forwarded-for", forwardedFor);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: "POST",
      headers,
      body: JSON.stringify(credentials),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: { code: "internal_error", message: "Kimlik servisine ulaşılamadı." } },
      { status: 502 },
    );
  }
  const payload: unknown = await backendResponse.json().catch(() => null);

  if (!backendResponse.ok) {
    return NextResponse.json(
      payload ?? { error: { code: "internal_error", message: "Giriş başarısız." } },
      { status: backendResponse.status },
    );
  }

  const tokens = payload as { access_token?: string; refresh_token?: string | null };
  if (tokens.access_token === undefined) {
    return NextResponse.json(
      { error: { code: "internal_error", message: "Beklenmeyen giriş yanıtı." } },
      { status: 502 },
    );
  }

  const response = NextResponse.json({ ok: true });
  writeSessionCookies(response, {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
  });
  return response;
}

export async function DELETE(request: NextRequest): Promise<NextResponse> {
  // Çıkış: refresh token ailesini backend'de iptal et (en-iyi-çaba), cookie'leri sil.
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (refreshToken !== undefined) {
    try {
      await fetch(`${API_URL}/api/v1/auth/logout`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      });
    } catch {
      // İptal edilemese bile cookie'ler temizlenir; erişim token'ı kısa ömürlüdür.
    }
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.delete(SESSION_COOKIE);
  response.cookies.delete(REFRESH_COOKIE);
  return response;
}
