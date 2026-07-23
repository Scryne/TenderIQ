// Aktif organizasyonu değiştirir: backend'ten hedef org için yeni token'lar alır ve
// httpOnly cookie'lere yazar (çoklu-org, Sprint 3.3-E). Mevcut oturumun erişim token'ı
// süresi dolmuşsa refresh token'la sessizce yenilenip yeniden denenir.

import { NextRequest, NextResponse } from "next/server";

import { API_URL, REFRESH_COOKIE, SESSION_COOKIE } from "@/lib/server/backend";
import { writeSessionCookies } from "@/lib/server/session";

async function tryRefresh(
  refreshToken: string,
): Promise<{ access_token: string; refresh_token: string } | null> {
  try {
    const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (!response.ok) return null;
    const payload = (await response.json().catch(() => null)) as {
      access_token?: string;
      refresh_token?: string;
    } | null;
    if (
      payload == null ||
      typeof payload.access_token !== "string" ||
      typeof payload.refresh_token !== "string"
    ) {
      return null;
    }
    return { access_token: payload.access_token, refresh_token: payload.refresh_token };
  } catch {
    return null;
  }
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const body: unknown = await request.json().catch(() => null);
  const organizationId =
    body != null && typeof body === "object"
      ? (body as { organization_id?: unknown }).organization_id
      : undefined;
  if (typeof organizationId !== "string") {
    return NextResponse.json(
      { error: { code: "validation_error", message: "organization_id gerekli." } },
      { status: 422 },
    );
  }

  let accessToken = request.cookies.get(SESSION_COOKIE)?.value;
  if (accessToken === undefined) {
    return NextResponse.json(
      { error: { code: "unauthorized", message: "Oturum bulunamadı." } },
      { status: 401 },
    );
  }

  const call = (token: string): Promise<Response> =>
    fetch(`${API_URL}/api/v1/auth/switch-org`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
      body: JSON.stringify({ organization_id: organizationId }),
      cache: "no-store",
    });

  let backendResponse: Response;
  try {
    backendResponse = await call(accessToken);
    if (backendResponse.status === 401) {
      const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
      if (refreshToken !== undefined) {
        const rotated = await tryRefresh(refreshToken);
        if (rotated !== null) {
          accessToken = rotated.access_token;
          backendResponse = await call(accessToken);
        }
      }
    }
  } catch {
    return NextResponse.json(
      { error: { code: "internal_error", message: "Kimlik servisine ulaşılamadı." } },
      { status: 502 },
    );
  }

  const payload: unknown = await backendResponse.json().catch(() => null);
  if (!backendResponse.ok) {
    return NextResponse.json(
      payload ?? { error: { code: "internal_error", message: "Organizasyon değiştirilemedi." } },
      { status: backendResponse.status },
    );
  }
  const tokens = payload as { access_token?: string; refresh_token?: string | null };
  if (typeof tokens.access_token !== "string") {
    return NextResponse.json(
      { error: { code: "internal_error", message: "Beklenmeyen yanıt." } },
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
