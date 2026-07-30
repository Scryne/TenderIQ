/**
 * İçerik Güvenlik Politikası — ZORLAYICI, nonce tabanlı (J.1).
 *
 * ## Neden nonce
 *
 * Politika daha önce `script-src 'self' 'unsafe-inline'` ile **yalnız rapor
 * modunda** yayınlanıyordu. `'unsafe-inline'`, XSS'e karşı script-src'in
 * sağladığı korumanın tamamını iptal eder: sayfaya enjekte edilen bir
 * `<script>` bloğu politikadan geçer. Rapor modu ise hiçbir şeyi engellemez.
 * Yani iki katman birden korumayı sıfıra indiriyordu.
 *
 * Artık her istekte tek kullanımlık bir nonce üretilir; yalnız o nonce'u
 * taşıyan betikler çalışır. Next kendi bootstrap/chunk betiklerine nonce'u
 * `Content-Security-Policy` İSTEK başlığından okuyup kendisi ekler
 * (`middleware.ts`), `next-themes`in satır içi tema betiğine ise nonce
 * `layout.tsx` üzerinden geçirilir.
 *
 * ## Bedeli, bilinerek ödeniyor
 *
 * Nonce istek başına değişir; bu yüzden hiçbir sayfa build anında üretilmiş
 * HTML'den servis edilemez — kök layout `headers()` okuduğu için tüm rotalar
 * dinamik render'a geçer. Alternatif (statik sayfalarda `'unsafe-inline'`
 * bırakmak) korumayı tam olarak en çok gerektiği yerde — oturum açma, kayıt,
 * hukuki metinler — kaldırırdı.
 *
 * ## `style-src 'unsafe-inline'` kalan borçtur
 *
 * Next kritik CSS'i ve `next/font` tanımlarını satır içi `<style>` ile
 * gömüyor ve bunlara nonce geçirmenin desteklenen bir yolu yok. Satır içi
 * stil ile ulaşılabilecek saldırı yüzeyi betiğe göre çok sınırlıdır
 * (script çalıştırmaz); bilinçli olarak burada bırakıldı.
 */

/** İhlal raporlarının toplandığı uç (`report-uri` + `report-to`). */
export const CSP_REPORT_PATH = "/api/csp-report";

/** `Reporting-Endpoints` başlığındaki grup adı — `report-to` ile eşleşir. */
export const CSP_REPORT_GROUP = "tenderiq-csp";

/**
 * CSP `connect-src` kaynakları.
 *
 * Tarayıcı iki dış origin'e gider: imzalı nesne depolama URL'i (PDF önizleme
 * baytları doğrudan R2'den indirilir — bkz. `pdf-viewer.tsx`) ve varsa Sentry.
 * İkisi de dağıtıma özgüdür; `NEXT_PUBLIC_*` oldukları için derleme anında
 * gömülür ve middleware (edge) içinde de okunabilirler.
 */
function connectSources(): string[] {
  const sources = ["'self'"];
  const storageOrigin = process.env.NEXT_PUBLIC_STORAGE_ORIGIN;
  if (storageOrigin) sources.push(storageOrigin);
  const sentryDsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (sentryDsn) {
    try {
      sources.push(new URL(sentryDsn).origin);
    } catch {
      // Bozuk DSN politikayı düşürmemeli; Sentry zaten devre dışı kalır.
    }
  }
  return sources;
}

/**
 * Verilen nonce için politika dizesini üretir.
 *
 * `'strict-dynamic'` bilinçli: nonce'lu bir betiğin DOM'a eklediği betikler
 * (Next'in chunk yükleyicisi tam olarak bunu yapar) çalışmaya devam ederken,
 * saldırganın sayfaya yazdığı `<script src="/...">` etiketi — aynı origin'den
 * olsa bile — engellenir. `'strict-dynamic'` varken `'self'` betikler için
 * yok sayılır; bu yüzden `'self'`i script-src'de bırakmak yanıltıcı olurdu.
 *
 * Sondaki `https:`, `'strict-dynamic'`i TANIMAYAN eski tarayıcılar için
 * yedektir; tanıyan tarayıcılar onu yok sayar. `'unsafe-inline'` yedeği
 * bilinçli olarak KONULMADI: eski tarayıcıda politikayı zayıflatmak yerine
 * uygulamanın kırılmasını tercih ediyoruz (BRIEF: hedef ortam güncel Chrome).
 */
export function buildContentSecurityPolicy(nonce: string, isProduction: boolean): string {
  const directives = [
    "default-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    `script-src 'nonce-${nonce}' 'strict-dynamic' https:`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    // PDF.js worker'ı webpack tarafından paketlenir (aynı origin); bazı
    // yapılandırmalarda blob: üzerinden başlatılır.
    "worker-src 'self' blob:",
    `connect-src ${connectSources().join(" ")}`,
    `report-uri ${CSP_REPORT_PATH}`,
    `report-to ${CSP_REPORT_GROUP}`,
  ];
  if (isProduction) directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}

/**
 * `Reporting-Endpoints` başlık değeri — `report-to` yönergesinin karşılığı.
 *
 * `report-uri` kullanımdan kalkıyor ama hâlâ daha geniş destekli; ikisi
 * birlikte yayılır ki hiçbir tarayıcıda rapor kaybı olmasın.
 */
export function reportingEndpointsHeader(): string {
  return `${CSP_REPORT_GROUP}="${CSP_REPORT_PATH}"`;
}

/** Tek kullanımlık nonce (128 bit, base64). */
export function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}
