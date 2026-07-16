// Aynı-origin API proxy'si: /api/v1/* isteklerini backend'e iletir.
//
// Cookie'deki oturum token'ı Authorization başlığına çevrilir; tarayıcı token'ı
// hiç görmez. Yanıt gövdesi akış olarak geçirilir (SSE dahil). Tip-güvenli
// istemci (openapi-fetch) baseUrl "" ile bu proxy üzerinden çalışır.

import { NextRequest } from "next/server";

import { API_URL, SESSION_COOKIE } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

// İletilen istek başlıkları (allowlist — hop-by-hop/host başlıkları geçmez).
const FORWARDED_REQUEST_HEADERS = ["content-type", "accept", "idempotency-key"];

async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await params;
  const target = new URL(`${API_URL}/api/v1/${path.join("/")}`);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  // Gerçek istemci IP'si backend oran sınırlamasına taşınır: Next sunucusu
  // (veya önündeki LB) x-forwarded-for'u doldurur; backend TRUSTED_PROXY_COUNT
  // ayarıyla sondan N girdiye güvenir.
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor !== null) headers.set("x-forwarded-for", forwardedFor);
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (token !== undefined) headers.set("authorization", `Bearer ${token}`);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const backendResponse = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
  });

  // Gövde akış olarak geçirilir; içerik uzunluğu/kodlaması fetch tarafından
  // çözülmüş olabileceğinden bu başlıklar kopyalanmaz.
  const responseHeaders = new Headers(backendResponse.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  responseHeaders.delete("transfer-encoding");
  if (backendResponse.status === 401) {
    // Süresi dolmuş/geçersiz oturum: cookie temizlenir; aksi hâlde middleware
    // (cookie var sanıp) /login ↔ /tenders arasında yönlendirme döngüsü kurar.
    responseHeaders.append(
      "set-cookie",
      `${SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax`,
    );
  }
  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: responseHeaders,
  });
}

export {
  proxy as DELETE,
  proxy as GET,
  proxy as PATCH,
  proxy as POST,
  proxy as PUT,
};
