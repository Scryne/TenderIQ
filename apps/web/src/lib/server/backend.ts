// Sunucu tarafı (route handler / middleware) yardımcıları — tarayıcıya sızmaz.

/** Backend API taban URL'i (yalnızca sunucuda okunur). */
export const API_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Oturum token'ının saklandığı httpOnly cookie adı. */
export const SESSION_COOKIE = "tenderiq_token";

/** Cookie ömrü: backend JWT ömrüyle (12 saat) hizalı. */
export const SESSION_MAX_AGE_SECONDS = 12 * 60 * 60;
