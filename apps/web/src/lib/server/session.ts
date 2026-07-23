// Sunucu tarafı oturum cookie yardımcıları — httpOnly token'ları yazar.
//
// Login, org-switch ve davet-kabul akışları backend'ten yeni token'lar alır ve
// bunları httpOnly cookie'lere yazar (token tarayıcı JS'ine hiç açılmaz).

import type { NextResponse } from "next/server";

import { REFRESH_COOKIE, SESSION_COOKIE, SESSION_MAX_AGE_SECONDS } from "./backend";

export function sessionCookieOptions() {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  };
}

/** Backend token yanıtını httpOnly cookie'lere yazar (refresh yoksa yalnız access). */
export function writeSessionCookies(
  response: NextResponse,
  tokens: { access_token: string; refresh_token?: string | null },
): void {
  response.cookies.set(SESSION_COOKIE, tokens.access_token, sessionCookieOptions());
  // Refresh token, Redis kesintisinde üretilmemiş olabilir (null): o durumda yalnız
  // kısa erişim token'ıyla çalışılır, sessiz yenileme olmaz.
  if (typeof tokens.refresh_token === "string") {
    response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, sessionCookieOptions());
  }
}
