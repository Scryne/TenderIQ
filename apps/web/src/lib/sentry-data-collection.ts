// Sentry veri toplama politikası — sunucu, edge ve tarayıcı başlatmasının ORTAK kaynağı.
//
// @sentry/nextjs 11 `sendDefaultPii` seçeneğini kaldırdı; yerine kategori bazlı
// `dataCollection` geldi ve verilmeyen alanların VARSAYILANI "her şeyi topla"dır
// (kullanıcı bilgisi/IP, çerezler, başlıklar, istek/yanıt gövdeleri). Seçeneği
// yalnızca silmek KVKK duruşumuzu sessizce gevşetirdi.
//
// Aşağıdaki değerler, Sentry 10.75'in `sendDefaultPii: false` için kendi içinde
// uyguladığı eşlemenin (`defaultPiiToCollectionOptions`) birebir karşılığıdır:
// IP/kullanıcı bilgisi yok, gövde yok, gen-AI/MCP içerikleri yok, DB sorgu
// değerleri yok; çerez/başlık/sorgu parametrelerinde kişisel veri taşıyan
// anahtarlar (IP iletim başlıkları vb.) dışlanır. Kimlik/oturum/token içeren
// anahtarları SDK ayrıca her durumda "[Filtered]" ile maskeler.
import type { init } from "@sentry/nextjs";

type DataCollection = NonNullable<NonNullable<Parameters<typeof init>[0]>["dataCollection"]>;

/** Sentry 10'daki `PII_HEADER_SNIPPETS` (11'de dışa aktarılmıyor). */
const PII_KEY_SNIPPETS = ["forwarded", "-ip", "remote-", "via", "-user"];

export const SENTRY_DATA_COLLECTION: DataCollection = {
  userInfo: false,
  cookies: { deny: PII_KEY_SNIPPETS },
  httpHeaders: {
    request: { deny: PII_KEY_SNIPPETS },
    response: { deny: PII_KEY_SNIPPETS },
  },
  httpBodies: [],
  urlQueryParams: { deny: PII_KEY_SNIPPETS },
  graphQL: { document: true, variables: true },
  genAI: { inputs: false, outputs: false },
  // 10.75'te karşılığı olmayan yeni kategoriler: PII kapalı duruşla tutarlı olarak kapalı.
  mcp: { inputs: false, outputs: false },
  queues: false,
  databaseQueryData: false,
  stackFrameVariables: true,
  frameContextLines: 7,
};
