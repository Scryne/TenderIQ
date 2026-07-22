// Aynı-origin API proxy'si: /api/v1/* isteklerini backend'e iletir.
//
// Cookie'deki kısa ömürlü erişim token'ı Authorization başlığına çevrilir; tarayıcı
// token'ı hiç görmez. Erişim token'ı süresi dolup backend 401 dönerse, refresh
// token'la (cookie) sessizce yenilenir ve istek bir kez yeniden denenir; yeni
// token'lar httpOnly cookie'lere yazılır. Yenilenemezse oturum cookie'leri
// temizlenir. Yanıt gövdesi akış olarak geçirilir (SSE dahil).

import { NextRequest } from "next/server";

import { API_URL, REFRESH_COOKIE, SESSION_COOKIE, SESSION_MAX_AGE_SECONDS } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

// İletilen istek başlıkları (allowlist — hop-by-hop/host başlıkları geçmez).
const FORWARDED_REQUEST_HEADERS = ["content-type", "accept", "idempotency-key"];

function buildHeaders(request: NextRequest, accessToken: string | undefined): Headers {
  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  // Gerçek istemci IP'si backend oran sınırlamasına taşınır: Next sunucusu (veya
  // önündeki LB) x-forwarded-for'u doldurur; backend TRUSTED_PROXY_COUNT ayarıyla
  // sondan N girdiye güvenir.
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor !== null) headers.set("x-forwarded-for", forwardedFor);
  if (accessToken !== undefined) headers.set("authorization", `Bearer ${accessToken}`);
  return headers;
}

function setCookie(name: string, value: string): string {
  const secure = process.env.NODE_ENV === "production" ? "; Secure" : "";
  return `${name}=${value}; Path=/; Max-Age=${SESSION_MAX_AGE_SECONDS}; HttpOnly; SameSite=Lax${secure}`;
}

function clearCookie(name: string): string {
  return `${name}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax`;
}

/** Refresh token'la yeni access+refresh alır; başarısızsa null. */
async function tryRefresh(
  refreshToken: string,
): Promise<{ access: string; refresh: string } | null> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
  } catch {
    return null;
  }
  if (!response.ok) return null;
  const payload: unknown = await response.json().catch(() => null);
  const tokens = payload as { access_token?: string; refresh_token?: string | null };
  if (typeof tokens.access_token !== "string" || typeof tokens.refresh_token !== "string") {
    return null;
  }
  return { access: tokens.access_token, refresh: tokens.refresh_token };
}

async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await params;
  const target = new URL(`${API_URL}/api/v1/${path.join("/")}`);
  target.search = request.nextUrl.search;

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  // Gövde bir kez okunur; olası yeniden deneme için tamponlanır (API gövdeleri
  // küçüktür — büyük dosyalar R2'ye imzalı URL ile doğrudan gider, proxy'den değil).
  const requestBody = hasBody ? await request.arrayBuffer() : undefined;

  const accessToken = request.cookies.get(SESSION_COOKIE)?.value;
  let backendResponse = await fetch(target, {
    method: request.method,
    headers: buildHeaders(request, accessToken),
    body: requestBody,
    cache: "no-store",
  });

  // 401 → erişim token'ı süresi dolmuş olabilir: refresh token'la sessizce yenile.
  let rotated: { access: string; refresh: string } | null = null;
  if (backendResponse.status === 401) {
    const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
    if (refreshToken !== undefined) {
      rotated = await tryRefresh(refreshToken);
      if (rotated !== null) {
        backendResponse = await fetch(target, {
          method: request.method,
          headers: buildHeaders(request, rotated.access),
          body: requestBody,
          cache: "no-store",
        });
      }
    }
  }

  // Gövde akış olarak geçirilir; içerik uzunluğu/kodlaması fetch tarafından
  // çözülmüş olabileceğinden bu başlıklar kopyalanmaz.
  const responseHeaders = new Headers(backendResponse.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  responseHeaders.delete("transfer-encoding");

  if (rotated !== null) {
    // Yenilenen token'lar cookie'lere yazılır (rotasyon: her ikisi de değişir).
    responseHeaders.append("set-cookie", setCookie(SESSION_COOKIE, rotated.access));
    responseHeaders.append("set-cookie", setCookie(REFRESH_COOKIE, rotated.refresh));
  } else if (backendResponse.status === 401) {
    // Yenilenemedi (refresh yok/geçersiz): oturum cookie'leri temizlenir; aksi
    // hâlde middleware (cookie var sanıp) /login ↔ /tenders döngüsü kurar.
    responseHeaders.append("set-cookie", clearCookie(SESSION_COOKIE));
    responseHeaders.append("set-cookie", clearCookie(REFRESH_COOKIE));
  }

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: responseHeaders,
  });
}

export { proxy as DELETE, proxy as GET, proxy as PATCH, proxy as POST, proxy as PUT };
