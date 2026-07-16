// Oturum uçları: backend'e giriş yapar, JWT'yi httpOnly cookie'ye yazar.
//
// Token tarayıcı JS'ine hiç verilmez (XSS'e karşı); API çağrıları aynı-origin
// /api/v1 proxy'si üzerinden, cookie'deki token Authorization'a çevrilerek gider.

import { NextRequest, NextResponse } from "next/server";

import { API_URL, SESSION_COOKIE, SESSION_MAX_AGE_SECONDS } from "@/lib/server/backend";

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

  const accessToken = (payload as { access_token?: string }).access_token;
  if (accessToken === undefined) {
    return NextResponse.json(
      { error: { code: "internal_error", message: "Beklenmeyen giriş yanıtı." } },
      { status: 502 },
    );
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, accessToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  });
  return response;
}

export async function DELETE(): Promise<NextResponse> {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
