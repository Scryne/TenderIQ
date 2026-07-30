/**
 * Ortam değişkeni manifestosu — tipli okuma + hızlı başarısızlık.
 *
 * ## Neden var
 *
 * Tur 11'de `NEXT_PUBLIC_STORAGE_ORIGIN` hiçbir yerde kurulmamıştı ve eksikliği
 * **sessizce** doküman tuvalini öldürdü: CSP `connect-src`i aynı-origin'e
 * kilitledi, tarayıcı imzalı PDF URL'ini çekemedi, sunucu logunda hiçbir iz
 * kalmadı. Bu tek bir unutulmuş değişken değil, bir SINIF:
 *
 * - Değer derleme anında gömülür (`NEXT_PUBLIC_*` ya da build ARG), yani
 *   çalışma anında düzeltilemez; üstelik middleware **edge runtime**'da koştuğu
 *   için `process.env` orada derleme sırasında sabite çevrilir.
 * - Eksik değişken `undefined` olur, kod `?? ""` ile devam eder ve arıza
 *   davranışa gömülür.
 *
 * Bu modül üç şeyi birden yapar: tek kaynaktan (`env-manifest.json`) okur,
 * eksik zorunlu değişkende **açılışı durdurur**, ve okunan değeri tipler.
 *
 * ## Doğrulama nerede koşar
 *
 * - **Derleme:** `next.config.ts` `assertBuildTimeEnv()` çağırır. Eksik build
 *   ARG derlemeyi DÜŞÜRÜR — imaj hatalı yapılandırmayla üretilemez.
 * - **Sunucu açılışı:** `instrumentation.ts` `assertRuntimeEnv()` çağırır.
 * - **Dağıtım dosyaları:** `apps/api/tests/test_yapilandirma_denetimi.py`
 *   manifestodaki her değişkenin `.env.example`, compose, Dockerfile ve CI'da
 *   bulunduğunu doğrular (Tur 11'de eksik olan tam buydu).
 */

import manifest from "../../env-manifest.json";

export type EnvLayer = "edge" | "server" | "client";
export type EnvRequirement = "always" | "production" | false;

export type EnvVariable = {
  name: string;
  buildTime: boolean;
  layers: EnvLayer[];
  required: EnvRequirement;
  default: string;
  wiring: string[];
  description: string;
  failure: string;
};

/**
 * Manifesto girdileri.
 *
 * JSON'dan geldiği için tip daraltması burada yapılır: `satisfies` ile
 * yazsaydık JSON'un genişletilmiş tipi (`string`) darlaştırılmazdı.
 */
export const ENV_VARIABLES = (manifest.variables as EnvVariable[]).map((variable) => ({
  ...variable,
  required: variable.required as EnvRequirement,
}));

function isProduction(): boolean {
  return process.env.NODE_ENV === "production";
}

function isRequiredNow(variable: EnvVariable): boolean {
  if (variable.required === "always") return true;
  if (variable.required === "production") return isProduction();
  return false;
}

/**
 * Değişken başına STATİK okuyucular.
 *
 * **`process.env[name]` (dinamik erişim) derleme anında gömülen değeri GÖREMEZ.**
 * Next yalnız `process.env.SABIT_AD` biçimindeki statik üye erişimini metinsel
 * olarak değerle değiştirir; köşeli parantezli erişim çalışma anında gerçek
 * `process.env`e bakar ve orada — derlenmiş imajda — değer yoktur. Yani
 * doğrulamayı dinamik erişimle yazmak, doğru yapılandırılmış bir kurulumda bile
 * "eksik" der ve açılışı yanlış yere kilitler (Tur 12'de tam bu yaşandı).
 *
 * Bu yüzden her değişkenin okuması burada AÇIKÇA yazılır. Manifestoya yeni bir
 * değişken eklenip buraya okuyucu eklenmezse `e2e/csp-policy.spec.ts` kırılır.
 */
const STATIC_READERS: Record<string, () => string | undefined> = {
  NEXT_PUBLIC_STORAGE_ORIGIN: () => process.env.NEXT_PUBLIC_STORAGE_ORIGIN,
  STORAGE_ORIGIN: () => process.env.STORAGE_ORIGIN,
  NEXT_PUBLIC_API_URL: () => process.env.NEXT_PUBLIC_API_URL,
  API_URL: () => process.env.API_URL,
  NEXT_PUBLIC_SENTRY_DSN: () => process.env.NEXT_PUBLIC_SENTRY_DSN,
};

/** Manifestodaki her değişkenin statik okuyucusu var mı (test bunu zorlar). */
export function variablesWithoutReader(): string[] {
  return ENV_VARIABLES.filter((variable) => !(variable.name in STATIC_READERS)).map(
    (variable) => variable.name,
  );
}

/** Değeri okur; tanımsızsa boş dize. */
function read(name: string): string {
  const reader = STATIC_READERS[name];
  return (reader ? reader() : process.env[name]) ?? "";
}

function formatMissing(missing: EnvVariable[]): string {
  const lines = missing.map(
    (variable) =>
      `  - ${variable.name} (${variable.buildTime ? "DERLEME anında" : "çalışma anında"}, ` +
      `katman: ${variable.layers.join("+")})\n` +
      `      ${variable.description}\n` +
      `      Eksikse: ${variable.failure}`,
  );
  return lines.join("\n");
}

/**
 * Derleme anında gömülen zorunlu değişkenleri doğrular.
 *
 * `next.config.ts` içinden çağrılır, yani **derleme sürecinde** koşar. Eksik
 * değişkende `throw` etmek derlemeyi düşürür; bu bilinçli: hatalı yapılandırmayla
 * üretilmiş bir imajın arızası ancak üretimde ve sessizce görünürdü.
 */
export function assertBuildTimeEnv(): void {
  const missing = ENV_VARIABLES.filter(
    (variable) => variable.buildTime && isRequiredNow(variable) && read(variable.name) === "",
  );
  if (missing.length === 0) return;
  throw new Error(
    "Derleme durduruldu — zorunlu derleme-zamanı ortam değişkenleri eksik.\n" +
      `${formatMissing(missing)}\n\n` +
      "Bunlar DERLEME argümanıdır (compose `build.args`, Dockerfile `ARG`, CI job env).\n" +
      "Çalışma anında vermek ETKİSİZDİR: politikayı üreten middleware edge\n" +
      "runtime'da koşar ve `process.env` orada derleme sırasında sabite çevrilir.",
  );
}

/**
 * Çalışma anında okunan zorunlu değişkenleri doğrular (sunucu açılışı).
 *
 * Derleme-zamanı olanlar burada TEKRAR kontrol edilir: derleme başka bir
 * makinede/aşamada yapılmış olabilir ve imaj elden ele geçebilir. Açılışta
 * durmak, ilk kullanıcının sessiz bir arızayla karşılaşmasından iyidir.
 */
export function assertRuntimeEnv(): void {
  const missing = ENV_VARIABLES.filter(
    (variable) => isRequiredNow(variable) && read(variable.name) === "",
  );
  if (missing.length === 0) return;
  throw new Error(
    "Açılış durduruldu — zorunlu ortam değişkenleri eksik.\n" + formatMissing(missing),
  );
}

/**
 * Nesne depolama origin'i (CSP `connect-src`).
 *
 * İki ad da derleme anında gömülür; `NEXT_PUBLIC_*` olan tarayıcı paketine de
 * girer, diğeri yalnız sunucu/edge paketine.
 */
export function storageOrigin(): string {
  return (
    process.env.NEXT_PUBLIC_STORAGE_ORIGIN || process.env.STORAGE_ORIGIN || ""
  );
}

/** Sentry DSN — boşsa Sentry tamamen kapalıdır. */
export function sentryDsn(): string {
  return process.env.NEXT_PUBLIC_SENTRY_DSN || "";
}
