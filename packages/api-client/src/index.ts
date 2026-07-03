// TenderIQ API'sinin tip-güvenli istemcisi.
//
// Tipler `openapi.json`'dan `openapi-typescript` ile üretilir (`pnpm generate`);
// `openapi.json` FastAPI tarafından `scripts/export_openapi.py` ile yazılır. Bu
// zincir backend↔frontend sözleşme drift'ini yapısal olarak önler (Geliştirme
// Planı B.5): şema değişince üretilen istemci de değişmek zorundadır (CI kontrolü).

import createClient, { type ClientOptions } from "openapi-fetch";

import type { paths } from "./schema";

export type { paths } from "./schema";

/** Verilen ayarlarla tip-güvenli bir API istemcisi kurar. */
export function createApiClient(options: ClientOptions): ReturnType<typeof createClient<paths>> {
  return createClient<paths>(options);
}

export type ApiClient = ReturnType<typeof createApiClient>;
