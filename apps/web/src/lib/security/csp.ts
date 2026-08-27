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
 * ## `style-src 'unsafe-inline'` KALICI borçtur — sebebi ölçüldü (Tur 11)
 *
 * Eski gerekçe ("Next kritik CSS'i satır içi gömüyor") YANLIŞTI: sunucudan
 * gelen HTML'de hiç satır içi `<style>` yok. Sıkılaştırma denendi
 * (`style-src 'self'` + `style-src-attr 'unsafe-inline'`) ve E2E anında
 * kırıldı — her sayfada üç `style-src-elem` ihlali.
 *
 * **Gerçek sebep `sonner` (toast, 2.0.7):** bileşen ÇALIŞMA ANINDA
 * `document.head`e 14,8 KB'lık bir `<style>` bloğu ekliyor. Paket nonce
 * kabul etmiyor (dist'te `nonce` hiç geçmiyor) ve enjeksiyon koşulsuz — ayrı
 * gelen `dist/styles.css`i import etmek onu durdurmuyor. Hash tabanlı izin de
 * çözüm değil: içerik paket sürümüyle değişir, her yükseltmede politika sessizce
 * kırılır.
 *
 * Kalan risk: enjekte edilen bir `<style>` bloğu sayfayı yeniden çizebilir,
 * tıklama hedeflerini kaydırabilir ve `background-image: url(...)` ile veri
 * sızdırabilir. Betik çalıştıramaz — `script-src` nonce'lu kalıyor, yani XSS
 * yolu kapalı. Borç bilinçli: sonner nonce desteklerse ya da değişirse
 * `style-src 'self'` + `style-src-attr 'unsafe-inline'` ikilisine geçilir.
 */

import { sentryDsn, storageOrigin } from "@/config/env";

/** İhlal raporlarının toplandığı uç (`report-uri` + `report-to`). */
export const CSP_REPORT_PATH = "/api/csp-report";

/** `Reporting-Endpoints` başlığındaki grup adı — `report-to` ile eşleşir. */
export const CSP_REPORT_GROUP = "tenderiq-csp";

/**
 * CSP `connect-src` kaynakları.
 *
 * Tarayıcı iki dış origin'e gider: imzalı nesne depolama URL'i (PDF önizleme
 * baytları doğrudan R2'den indirilir — bkz. `pdf-viewer.tsx`) ve varsa Sentry.
 *
 * ## Depolama origin'i DERLEME anında gömülür — çalışma anında değiştirilemez
 *
 * Bu modül `middleware.ts` içinden çağrılıyor ve middleware **edge çalışma
 * zamanında** koşuyor. Orada `process.env` erişimi derleme sırasında sabite
 * çevrilir: imaja gömülmeyen bir değişken çalışma anında GÖRÜNMEZ. Tur 11'de
 * `STORAGE_ORIGIN` çalışma anı değişkeni olarak verilip denendi ve politika
 * `connect-src 'self'` olarak kaldı — yani sessizce hiçbir etkisi olmadı.
 * Bu yüzden değer **derleme anında** verilmelidir (compose'da build arg,
 * CI'da job env'i).
 *
 * ## Neden bu satır kritik
 *
 * Değişken hiçbir yerde KURULMUYORDU (`.env.example`de boş, compose'da yok).
 * Sonuç: `connect-src 'self'` ile kalıyordu ve zorlayıcı CSP altında tarayıcı
 * imzalı R2 URL'ini çekemiyordu — **doküman tuvali sessizce boş kalıyordu.**
 * Ürünün çekirdek vaadi (bulgu ↔ kaynak) tam olarak o tuvale bağlı. Arıza
 * sunucu logunda görünmez, yalnız tarayıcı konsolunda. Tur 11'de
 * `e2e/csp.spec.ts`in kimlikli testi yakaladı; rapor modunda hiçbir şeyi
 * engellemediği için Tur 10'da görünmemişti.
 */
export function connectSources(): string[] {
  const sources = ["'self'"];
  // Değerler manifestodan tipli okunur (`config/env.ts`); orada hangi katmanda
  // okundukları ve eksikliklerinin ne kırdığı yazılıdır.
  const origin = storageOrigin();
  if (origin) sources.push(origin);
  const dsn = sentryDsn();
  if (dsn) {
    try {
      sources.push(new URL(dsn).origin);
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
  // `'unsafe-eval'` YALNIZ geliştirmede. `next dev`in webpack paketi her modülü
  // `eval()` ile sarar; izin verilmezse tek bir istemci betiği bile çalışmaz.
  // Sonuç sessizdir ve "çalışıyor" gibi görünür: SSR HTML'i gelir, hidrasyon hiç
  // olmaz, form gönderimi düz GET'e düşer, veri çeken sayfalar boş kalır — yani
  // dev sunucusunda giriş yapmak imkânsızdır. Üretim politikası DEĞİŞMEZ:
  // `next start` (E2E ve dağıtım) `NODE_ENV=production` ile koştuğu için oraya
  // girmez ve `csp-policy.spec.ts` bunu kapı olarak doğrular.
  const scriptSrc = [`'nonce-${nonce}'`, "'strict-dynamic'", "https:"];
  if (!isProduction) scriptSrc.push("'unsafe-eval'");

  const directives = [
    "default-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    `script-src ${scriptSrc.join(" ")}`,
    // `'unsafe-inline'` KALICI borç — sebebi yukarıda ölçülerek yazıldı (sonner).
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    // PDF.js worker'ı webpack tarafından paketlenir (aynı origin); bazı
    // yapılandırmalarda blob: üzerinden başlatılır.
    "worker-src 'self' blob:",
    // `blob:` — PDF.js'in okuduğu şema. `pdf-viewer.tsx` imzalı URL'in baytlarını
    // BİR KEZ indirip (yukarıdaki depolama origin'i) `URL.createObjectURL` ile
    // sarıyor ve PDF.js'e o `blob:` adresini veriyor; PDF.js de onu `fetch` ile
    // açıyor. `connect-src`te `blob:` yoksa tarayıcı TAM BU adımı keser: R2
    // isteği 200 döner, dosya inmiştir, ama PDF.js "Unexpected server response
    // (0)" der ve **tuval boş kalır** — yani depolama origin'i doğru olsa bile
    // arıza aynen sürer (iki ayrı kusur, aynı belirti). `blob:` yalnız sayfanın
    // kendi ürettiği, aynı-origin ömürlü nesneleri adresler; dışarı veri
    // taşımaz. `img-src` ve `worker-src` zaten aynı sebeple `blob:` taşıyor.
    `connect-src ${connectSources().join(" ")} blob:`,
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
