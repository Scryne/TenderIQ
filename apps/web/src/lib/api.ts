import { createApiClient } from "@tenderiq/api-client";

/**
 * Uygulama genelinde paylaşılan, tip-güvenli API istemcisi.
 *
 * Çağrılar aynı-origin `/api/v1` proxy'sine gider (`app/api/v1/[...path]`);
 * proxy, httpOnly cookie'deki oturum token'ını Authorization'a çevirip
 * backend'e iletir. Token tarayıcı JS'ine hiç açılmaz.
 */
export const api = createApiClient({ baseUrl: "" });
