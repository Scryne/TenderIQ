import { expect, test } from "@playwright/test";

/**
 * Faz 3 çıkış kapısı — uçtan uca akış: giriş → inceleme → onay → export.
 *
 * Veri `scripts/seed_e2e.py` ile tohumlanır (incelemeye-hazır ihale + kaynağa bağlı
 * bulgular). Akış: bulgu görünür → onayla → Word raporu indir → başarı bildirimi.
 * Backend eşdeğeri `apps/api/tests/integration/test_review_flow.py` ile de doğrulanır
 * (onay/düzelt + kaynak referanslı docx/xlsx içeriği); bu spec tarayıcı katmanını kanıtlar.
 */

const EMAIL = process.env.E2E_EMAIL ?? "e2e@tenderiq.local";
const PASSWORD = process.env.E2E_PASSWORD ?? "e2e-password-123";
const TENDER_TITLE = process.env.E2E_TENDER_TITLE ?? "E2E İnceleme İhalesi";
const REQUIREMENT = "Yüklenici tüm idari maddeleri karşılamalıdır.";

test("incele → onayla → export (citation-first uçtan uca)", async ({ page }) => {
  // 1) Giriş (httpOnly cookie sunucuda yazılır).
  await page.goto("/login");
  await page.getByLabel("E-posta").fill(EMAIL);
  await page.getByLabel("Parola").fill(PASSWORD);
  await page.getByRole("button", { name: "Giriş yap" }).click();
  await page.waitForURL("**/tenders");

  // 2) Tohumlanan ihaleye gir → detay URL'inden id çöz → inceleme ekranı.
  await page.getByText(TENDER_TITLE).click();
  await page.waitForURL(/\/tenders\/[0-9a-f-]+$/);
  await page.goto(`${page.url()}/review`);

  // 3) Bulgular yüklendi (grounded gereksinim metni görünür).
  await expect(page.getByText(REQUIREMENT)).toBeVisible();

  // 4) İlk bulguyu onayla (satır aksiyonu; title="Onayla").
  await page.getByTitle("Onayla").first().click();

  // 5) Raporu dışa aktar: "Rapor indir" → docx (varsayılan) → "İndir".
  await page.getByRole("button", { name: "Rapor indir" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "İndir" }).click();

  // 6) Export başarılı (onaylı bulgudan kaynak-referanslı rapor üretildi).
  await expect(page.getByText("Rapor indirildi.")).toBeVisible();
});
