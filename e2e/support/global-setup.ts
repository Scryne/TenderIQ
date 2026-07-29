import { execFileSync } from "node:child_process";

/**
 * Koşu öncesi oran-sınırı sayaçlarını temizler.
 *
 * **Neden gerekli.** Oran-sınırı sayaçları GERÇEK Redis'te TTL'li yaşar
 * (`rl:*`). E2E'nin bütün kayıtları `127.0.0.1`den geliyor, yani
 * `rl:register:ip:127.0.0.1` her koşuda birikiyor. Birkaç koşudan sonra kayıt
 * ucu 429 dönmeye başlıyor ve testler "gezinme zaman aşımı" ile düşüyor —
 * yani arıza, sebebini hiç ele vermeyen bir biçimde görünüyor. (Tam olarak bu
 * yaşandı: aynı testler önce 24 saniyede yeşil, sonraki koşuda 4,8 dakikada
 * üç kırmızı.)
 *
 * Kök `conftest.py` pytest için aynı temizliği zaten yapıyor; bu, onun E2E
 * karşılığı.
 *
 * Python üzerinden yapılıyor çünkü Redis istemcisi zaten Python tarafında var;
 * yalnız bu iş için Node'a yeni bir bağımlılık eklemeye değmez.
 */
const SCRIPT = `
import asyncio
from redis.asyncio import Redis
from tenderiq_core.config import get_settings

async def main() -> None:
    client = Redis.from_url(get_settings().redis_url)
    try:
        keys = [key async for key in client.scan_iter("rl:*")]
        if keys:
            await client.delete(*keys)
        print(f"temizlenen oran-siniri anahtari: {len(keys)}")
    finally:
        await client.aclose()

asyncio.run(main())
`;

export default function globalSetup(): void {
  try {
    const output = execFileSync("uv", ["run", "python", "-c", SCRIPT], {
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    process.stdout.write(`[e2e] ${output.trim()}\n`);
  } catch (error) {
    // Temizlik yapılamadıysa koşuyu DURDURMA: Redis erişilemiyorsa asıl arıza
    // testlerde zaten görünecek. Ama sessiz kalma — sonraki 429'ların sebebi
    // burada yazıyor olsun.
    process.stdout.write(
      `[e2e] UYARI: oran-sınırı sayaçları temizlenemedi; 429 görürsen sebebi bu olabilir.\n` +
        `      ${error instanceof Error ? error.message : String(error)}\n`,
    );
  }

  // Tohum her koşuda çalışır ve veriyi İSTENEN DURUMA getirir — inceleme
  // durumu dâhil. `review-export` spec'i bulguyu onaylıyor ve onay KALICI;
  // onay butonu yalnız incelenmemiş bulguda görünüyor. Sıfırlanmazsa ikinci
  // koşu "öğe bulunamadı" ile düşer ve sebebi görünmez (tam olarak bu yaşandı:
  // birinci koşu yeşil, ikinci ve üçüncü kırmızı).
  //
  // Burada hata YUTULMAZ: tohum yoksa `review-export` zaten anlamsızca düşer ve
  // sebebini aramak zaman kaybıdır.
  execFileSync("uv", ["run", "python", "scripts/seed_e2e.py"], {
    encoding: "utf-8",
    stdio: ["ignore", "pipe", "inherit"],
  });
  process.stdout.write("[e2e] tohum verisi istenen duruma getirildi\n");
}
