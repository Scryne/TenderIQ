// Korumalı sayfa yönlendirmesi: oturum cookie'si yoksa /login'e gönderir.
//
// Yalnızca UX içindir (cookie varlığı kontrolü); gerçek yetkilendirme her API
// çağrısında backend JWT doğrulamasıyla yapılır.

import { NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/server/backend";

export function middleware(request: NextRequest): NextResponse {
  const hasSession = request.cookies.has(SESSION_COOKIE);
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/tenders") && !hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  if (pathname === "/login" && hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/tenders";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/tenders/:path*", "/login"],
};
