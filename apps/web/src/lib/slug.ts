/**
 * Organizasyon kısa adı (slug) türetme — Türkçe farkındalıklı.
 *
 * Slug, kiracının kalıcı kimliğidir: hesap kapatma onayında kullanıcıdan
 * **birebir yazması** istenir ve backend `^[a-z0-9-]+$` dışını reddeder. Bu
 * yüzden türetme kullanıcıdan gizlenmez, ekranda canlı gösterilir.
 *
 * Türkçe tuzağı: `"İ".toLowerCase()` JS'te `i` + birleşen nokta üretir,
 * `toLocaleLowerCase("tr")` ise `I` harfini `ı`ya çevirir. İkisi de küçük harfe
 * çevirdikten SONRA eşleme yapmayı güvenilmez kılar — bu yüzden Türkçe harfler
 * **önce** açıkça eşlenir, küçültme sonra yapılır.
 */

/** Küçültmeden ÖNCE uygulanan açık eşleme (büyük ve küçük biçimler ayrı). */
const TURKISH_MAP: Record<string, string> = {
  İ: "i",
  I: "i",
  ı: "i",
  Ş: "s",
  ş: "s",
  Ğ: "g",
  ğ: "g",
  Ü: "u",
  ü: "u",
  Ö: "o",
  ö: "o",
  Ç: "c",
  ç: "c",
};

/** Backend `max_length=255` kabul eder; okunabilirlik için daha kısa tutulur. */
const MAX_LENGTH = 48;

export function slugify(value: string): string {
  const mapped = [...value].map((char) => TURKISH_MAP[char] ?? char).join("");
  return (
    mapped
      .toLowerCase()
      // Kalan aksanlı harfler (é, ñ, â…) ayrıştırılıp birleşen işaretleri atılır.
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      // İzinli küme dışındaki her dizi tek tireye iner (boşluk, nokta, &, / …).
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, MAX_LENGTH)
      // Kırpma sondaki tireyi açıkta bırakabilir.
      .replace(/-+$/g, "")
  );
}

/** Slug backend sözleşmesine uyuyor mu (boş değil ve yalnız izinli karakterler). */
export function isValidSlug(value: string): boolean {
  return /^[a-z0-9-]+$/.test(value);
}
