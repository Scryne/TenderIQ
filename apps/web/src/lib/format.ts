/**
 * Türkçe biçimlendirme — DESIGN.md Ek B.1. **Tek kaynak.**
 *
 * Ekranlarda elle biçimlendirme yasak: `${n.toFixed(2)} ₺`, `toLocaleDateString()`
 * çağrıları ya da şablon içinde nokta/virgül değişimi yapılmaz. Buradaki
 * yardımcılar `Intl.*` üzerine kuruludur ve tek noktadan değiştirilir.
 *
 *   Para   ₺1.234,56        Sayı   184.392       Yüzde  %12,4
 *   Tarih  25.07.2026       Saat   14:32         Büyük  1,2 mn · 184 b
 */

const LOCALE = "tr-TR";

const number = new Intl.NumberFormat(LOCALE);
const number1 = new Intl.NumberFormat(LOCALE, {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
/** En fazla bir hane — tam sayıda kuruş hanesi YAZILMAZ ("500 MB", "2,4 MB"). */
const numberUpTo1 = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 1 });
const currency = new Intl.NumberFormat(LOCALE, {
  style: "currency",
  currency: "TRY",
  maximumFractionDigits: 0,
});
const currencyPrecise = new Intl.NumberFormat(LOCALE, {
  style: "currency",
  currency: "TRY",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const dateShort = new Intl.DateTimeFormat(LOCALE, {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});
const dateLong = new Intl.DateTimeFormat(LOCALE, {
  day: "numeric",
  month: "short",
  year: "numeric",
});
const dateTime = new Intl.DateTimeFormat(LOCALE, {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const relative = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });

/** `184.392` */
export function formatNumber(value: number): string {
  return number.format(value);
}

/** `₺184.392` — sembol sayının solunda, Intl'in tr-TR çıktısı budur. */
export function formatCurrency(value: number): string {
  return currency.format(value);
}

/**
 * `₺8,40` — kuruş görünür. `formatCurrency` tam TL'ye yuvarlar (plan fiyatları
 * için doğru); LLM bütçesi gibi küçük tutarlarda o yuvarlama bilgi kaybıdır —
 * ₺8,40 harcamayı "₺8" göstermek, tavana ne kadar yaklaşıldığını gizler.
 */
export function formatCurrencyPrecise(value: number): string {
  return currencyPrecise.format(value);
}

/**
 * `₺8,40` → `{ symbol: "₺", amount: "8,40" }` — §6.5: para birimi sayıdan
 * **daha küçük ve muted** olur.
 *
 * Ayırma elle yapılmaz, Intl'in kendi parçalarından okunur: sembolün sayının
 * solunda mı sağında mı durduğu ve arada boşluk olup olmadığı locale kararıdır,
 * bizim değil (Ek B.1 "elle biçimlendirme yasak").
 */
export function splitCurrency(value: number): { symbol: string; amount: string } {
  const parts = currencyPrecise.formatToParts(value);
  const symbol = parts
    .filter((part) => part.type === "currency")
    .map((part) => part.value)
    .join("");
  const amount = parts
    .filter((part) => part.type !== "currency" && part.type !== "literal")
    .map((part) => part.value)
    .join("");
  return { symbol, amount };
}

/** `%12,4` — işaret ÖNDE (Ek B.1). Intl'in `style: percent` çıktısı sona koyar. */
export function formatPercent(value: number, fractionDigits: 0 | 1 = 1): string {
  const formatted = fractionDigits === 0 ? number.format(Math.round(value)) : number1.format(value);
  return `%${formatted}`;
}

/** `1,2 mn` · `184 b` — dar sütunlarda (Ek B.1). Eşik altında tam sayı. */
export function formatCompact(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${number1.format(value / 1_000_000)} mn`;
  if (Math.abs(value) >= 10_000) return `${number.format(Math.round(value / 1000))} b`;
  return number.format(value);
}

function toDate(value: string | number | Date): Date {
  return value instanceof Date ? value : new Date(value);
}

/** `25.07.2026` */
export function formatDate(value: string | number | Date): string {
  return dateShort.format(toDate(value));
}

/** `25 Tem 2026` — başlıklarda ve tek satırlık meta bilgilerde okunaklı. */
export function formatDateLong(value: string | number | Date): string {
  return dateLong.format(toDate(value));
}

/** `25.07.2026 14:32` — 24 saat (Ek B.1). `title` niteliklerinde tam değer. */
export function formatDateTime(value: string | number | Date): string {
  return dateTime.format(toDate(value));
}

const RELATIVE_STEPS: [limitSeconds: number, divisor: number, unit: Intl.RelativeTimeFormatUnit][] =
  [
    [60, 1, "second"],
    [3600, 60, "minute"],
    [86_400, 3600, "hour"],
    [604_800, 86_400, "day"],
    [2_629_800, 604_800, "week"],
    [31_557_600, 2_629_800, "month"],
    [Number.POSITIVE_INFINITY, 31_557_600, "year"],
  ];

/**
 * `3 saat önce` · `2 gün sonra`. Tabloda göreli, `title`'da tam tarih (§8.3).
 * Ek uyumu kırılmasın diye Intl'e bırakılır; elle "…'in" eklenmez (Ek B.3).
 */
export function formatRelative(value: string | number | Date, now: Date = new Date()): string {
  const deltaSeconds = (toDate(value).getTime() - now.getTime()) / 1000;
  const magnitude = Math.abs(deltaSeconds);
  for (const [limit, divisor, unit] of RELATIVE_STEPS) {
    if (magnitude < limit) return relative.format(Math.round(deltaSeconds / divisor), unit);
  }
  return formatDate(value);
}

/**
 * Son teklif tarihine kalan gün — ihale alanının en kritik sayısı.
 * Negatif = geçmiş. Takvim günü farkı (saat farkı değil) üzerinden hesaplanır;
 * "yarın saat 09:00" ile "bugün 23:00" arasındaki fark 1 gün görünmelidir.
 */
export function daysUntil(value: string | number | Date, now: Date = new Date()): number {
  const target = toDate(value);
  const a = Date.UTC(target.getFullYear(), target.getMonth(), target.getDate());
  const b = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((a - b) / 86_400_000);
}

/** `3 gün kaldı` · `bugün` · `2 gün geçti` — eksiz kalıp (Ek B.3). */
export function formatDeadline(value: string | number | Date, now: Date = new Date()): string {
  const days = daysUntil(value, now);
  if (days === 0) return "bugün";
  if (days === 1) return "yarın";
  if (days > 0) return `${number.format(days)} gün kaldı`;
  return `${number.format(Math.abs(days))} gün geçti`;
}

const TR_MONTHS: Record<string, number> = {
  ocak: 0,
  şubat: 1,
  subat: 1,
  mart: 2,
  nisan: 3,
  mayıs: 4,
  mayis: 4,
  haziran: 5,
  temmuz: 6,
  ağustos: 7,
  agustos: 7,
  eylül: 8,
  eylul: 8,
  ekim: 9,
  kasım: 10,
  kasim: 10,
  aralık: 11,
  aralik: 11,
};

/**
 * Şartnameden ÇIKARILMIŞ serbest metin tarihini en iyi çabayla ayrıştırır.
 *
 * `TimelineEventResponse.value_text` yapılandırılmış bir tarih değil, dokümandan
 * alınmış metindir ("15.08.2026", "15/08/2026", "15 Ağustos 2026 saat 10:00").
 * Ayrıştırılamayan metin için `null` döner ve arayüz ham metni gösterir —
 * uydurulmuş bir tarihe göre "3 gün kaldı" yazmak, bu üründe en pahalı hata
 * türüdür (§13.4: sahte içerik yok).
 */
export function parseTrDate(text: string): Date | null {
  const trimmed = text.trim();

  const numeric = /(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{4})/.exec(trimmed);
  if (numeric !== null) {
    const [, d, m, y] = numeric;
    const date = new Date(Number(y), Number(m) - 1, Number(d));
    return date.getMonth() === Number(m) - 1 ? date : null;
  }

  const named = /(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})/.exec(trimmed);
  if (named !== null) {
    const [, d, monthWord, y] = named;
    const month = TR_MONTHS[monthWord.toLocaleLowerCase("tr-TR")];
    if (month !== undefined) return new Date(Number(y), month, Number(d));
  }

  return null;
}

/**
 * `2,4 MB` · `500 MB` — dosya boyutu.
 *
 * Ondalık hane **zorunlu değil**: kota gibi yuvarlak değerlerde "500,0 MB"
 * yazmak özensiz durur ve okunurluğu düşürür. Sıfır olmayan hane varsa yazılır.
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${number.format(bytes)} B`;
  if (bytes < 1024 * 1024) return `${numberUpTo1.format(bytes / 1024)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${numberUpTo1.format(bytes / 1024 / 1024)} MB`;
  return `${numberUpTo1.format(bytes / 1024 / 1024 / 1024)} GB`;
}

/**
 * Türkçe sıralama — `ç ğ ı i ö ş ü` varsayılan sıralamada yanlış çıkar (Ek B.3).
 * `array.sort(byLocale)` ya da `array.sort(byLocaleKey(x => x.title))`.
 */
export const byLocale = (a: string, b: string): number => a.localeCompare(b, LOCALE);

export function byLocaleKey<T>(key: (item: T) => string): (a: T, b: T) => number {
  return (a, b) => key(a).localeCompare(key(b), LOCALE);
}
