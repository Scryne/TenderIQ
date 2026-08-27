// İki iş yapar:
//
// 1. **CSP nonce'u üretir** ve zorlayıcı politikayı yayınlar (bkz. `lib/security/csp.ts`).
//    Nonce hem YANIT başlığına hem İSTEK başlığına yazılır: Next kendi betik
//    etiketlerine nonce'u istek başlığındaki politikadan okuyarak ekler,
//    `layout.tsx` ise `x-nonce`u okuyup `next-themes`in satır içi betiğine geçirir.
//
// 2. **Korumalı sayfa yönlendirmesi:** oturum cookie'si yoksa /login'e gönderir.
//    Yalnızca UX içindir (cookie varlığı kontrolü); gerçek yetkilendirme her API
//    çağrısında backend JWT doğrulamasıyla yapılır.

import { NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/server/backend";
import {
  buildContentSecurityPolicy,
  generateNonce,
  reportingEndpointsHeader,
} from "@/lib/security/csp";

const PROTECTED_PREFIXES = ["/panel", "/tenders", "/capability", "/usage", "/settings"];

export function middleware(request: NextRequest): NextResponse {
  const nonce = generateNonce();
  const policy = buildContentSecurityPolicy(nonce, process.env.NODE_ENV === "production");

  const hasSession = request.cookies.has(SESSION_COOKIE);
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  if (isProtected && !hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    url.searchParams.set("next", pathname);
    return withSecurityHeaders(NextResponse.redirect(url), policy);
  }
  // `/login` BURADA yönlendirilmez. Middleware yalnız cookie'nin VARLIĞINI
  // görür, geçerliliğini göremez; "cookie var → /tenders" kuralı bu yüzden bayat
  // bir oturumda kullanıcıyı kilitliyordu: giriş sayfası erişilemez oluyor,
  // /tenders ise 401 alıp boş kalıyordu — yani hesaba bir daha hiç girilemiyordu.
  // Doğrulanmış yönlendirme `app/login/page.tsx` içinde, backend'e sorularak
  // yapılır (orası Node çalışma zamanı: `API_URL`i çalışma anında okuyabilir,
  // edge middleware okuyamaz — bkz. `lib/security/csp.ts`deki derleme-anı notu).

  // Politika İSTEK başlığına da yazılır — Next nonce'u buradan okuyup kendi
  // `<script>` etiketlerine ekler. Yalnız yanıt başlığını yazsaydık Next
  // betiklerine nonce koymaz ve zorlayıcı politika sayfayı tamamen kırardı.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("content-security-policy", policy);
  requestHeaders.set("x-nonce", nonce);

  return withSecurityHeaders(NextResponse.next({ request: { headers: requestHeaders } }), policy);
}

function withSecurityHeaders(response: NextResponse, policy: string): NextResponse {
  response.headers.set("Content-Security-Policy", policy);
  response.headers.set("Reporting-Endpoints", reportingEndpointsHeader());
  return response;
}

export const config = {
  matcher: [
    // Tüm DOKÜMAN istekleri. CSP yalnız korumalı rotalarda değil HER sayfada
    // gerekli — /login ve /register en çok korunması gereken sayfalar.
    //
    // Dışarıda bırakılanlar: `/api` (JSON; CSP dokümanı ilgilendirir ve
    // `/api/csp-report` kendi kendini engellememeli), `_next/static` ve
    // `_next/image` (değişmez varlıklar; her birine nonce üretmek boşa maliyet),
    // `favicon.ico` ve `.well-known`.
    //
    // `missing` koşulu prefetch isteklerini atlar: Next router prefetch'i HTML
    // gövdesini kullanmaz, ona nonce üretmek gereksizdir.
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico|\\.well-known).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
