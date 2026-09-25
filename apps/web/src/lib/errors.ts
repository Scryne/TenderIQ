/**
 * Kullanıcıya gösterilecek hata metni.
 *
 * `fetch` ağ katmanında reddedildiğinde (bağlantı yok, CORS, CSP) tarayıcı kendi
 * İngilizce mesajını fırlatır ve bu mesaj her `error.message` gösteriminden
 * arayüze sızar. Mesajlar tarayıcıya göre değişir; üçü de aynı Türkçe cümleye
 * çevrilir. Uygulamanın kendi Türkçe hataları olduğu gibi geçer.
 */
const NETWORK_MESSAGES = [
  "Failed to fetch", // Chromium
  "NetworkError when attempting to fetch resource.", // Firefox
  "Load failed", // Safari
];

export const NETWORK_ERROR_TEXT =
  "Sunucuya ulaşılamadı. Bağlantınızı kontrol edip yeniden deneyin.";

export function userMessage(error: unknown, fallback = "Beklenmeyen bir hata oluştu."): string {
  const message = error instanceof Error ? error.message : typeof error === "string" ? error : "";
  if (message === "") return fallback;
  if (NETWORK_MESSAGES.some((known) => message.startsWith(known))) return NETWORK_ERROR_TEXT;
  return message;
}
