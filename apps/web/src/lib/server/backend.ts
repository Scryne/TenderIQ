// Sunucu tarafı (route handler / middleware) yardımcıları — tarayıcıya sızmaz.

/** Backend API taban URL'i (yalnızca sunucuda okunur). */
export const API_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Kısa ömürlü erişim (JWT) token'ının saklandığı httpOnly cookie adı. */
export const SESSION_COOKIE = "tenderiq_token";

/** Rotasyonlu refresh token'ının saklandığı httpOnly cookie adı. */
export const REFRESH_COOKIE = "tenderiq_refresh";

/**
 * Cookie ömrü = refresh token ömrü (30 gün). Erişim token'ının KENDİSİ kısa
 * ömürlüdür (backend'te ≤1 saat) ve süresi dolunca /api/v1 proxy'si tarafından
 * refresh token'la sessizce yenilenir. Cookie'nin uzun yaşaması, tarayıcının
 * her istekte token'ı taşıyıp yenileme yolunu tetiklemesini sağlar; middleware
 * de oturum varlığını cookie üzerinden görür.
 */
export const SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60;
