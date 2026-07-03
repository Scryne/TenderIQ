import { createApiClient } from "@tenderiq/api-client";

/**
 * Uygulama genelinde paylaşılan, tip-güvenli API istemcisi.
 *
 * Taban URL derleme anında `NEXT_PUBLIC_API_URL` ile verilir (yoksa yerel
 * geliştirme varsayılanı). Tüm çağrılar üretilen OpenAPI tiplerine bağlıdır.
 */
export const api = createApiClient({
  baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});
