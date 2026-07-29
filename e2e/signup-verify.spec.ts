import { expect, test } from "@playwright/test";

import {
  apiBaseFor,
  extractLink,
  newIdentity,
  signIn,
  signOut,
  submitRegistration,
  waitForEmail,
} from "./support/stack";

/**
 * Akış 1: kayıt → doğrulama e-postası → doğrulama → yeniden giriş → /panel.
 *
 * Zincirin her halkası ayrı entegrasyon testiyle zaten kapsanıyor; buradaki
 * değer **halkaların birbirine gerçekten bağlandığını** kanıtlamak. Tam olarak
 * bu tür bir kopukluk daha önce yaşandı: uç doğru çalışıyordu ama yanıt zarfı
 * değiştiği için istemci onu okuyamıyordu.
 *
 * Doğrulama bağlantısı e-postanın İÇİNDEN okunur (`/_test/inbox`); token
 * uydurulmaz. Uydurulsaydı "e-posta hiç gönderilmedi" ya da "bağlantı yanlış
 * üretildi" hâlleri sessizce geçerdi — yani testin asıl işi kaçardı.
 */
test("kayıt → doğrulama e-postası → doğrulama → giriş → panel", async ({
  page,
  request,
  baseURL,
}) => {
  const apiBase = apiBaseFor(baseURL);
  const identity = newIdentity("kayit");

  await submitRegistration(page, identity);

  // Açık kayıtta hesap açılır VE oturum aynı bilgilerle hemen kurulur; kullanıcı
  // panele düşer (giriş ekranına geri atılmaz).
  await page.waitForURL(/\/panel/);

  // Doğrulama bağlantısı e-postadan okunur.
  const message = await waitForEmail(request, apiBase, {
    to: identity.email,
    kind: "verify_email",
  });
  expect(message.subject).toContain("TenderIQ");
  const link = extractLink(message.text, "/verify-email");

  // Bağlantı web kökenine taşınır: e-postadaki adres `APP_BASE_URL`den gelir ve
  // E2E yığınının portu farklıdır. Sınanan şey adres değil, TOKEN'ın çalışması.
  const target = new URL(link);
  await page.goto(`/verify-email${target.search}`);
  await expect(page.getByText("E-posta adresiniz doğrulandı.", { exact: false })).toBeVisible();

  // Doğrulanmış hesapla yeniden giriş → panel.
  await signOut(page);
  await signIn(page, identity, /\/panel/);
  await expect(page).toHaveURL(/\/panel/);
});

/**
 * Aynı e-posta ikinci kez kaydolamaz.
 *
 * Sunucu 409'u iki farklı çakışma için ayırıyor (e-posta / kısa ad) ve istemci
 * mesajı EZMEMELİ: kullanıcı hangisini değiştireceğini bilmeli.
 */
test("aynı e-posta ikinci kez kaydolamaz ve sebebi görünür", async ({ page }) => {
  const identity = newIdentity("cakisma");

  await submitRegistration(page, identity);
  await page.waitForURL(/\/panel/);

  // Oturum kapatılmadan `/register`e dönmek panele yönlenir ve form hiç
  // görünmez — test o zaman "hata mesajı yok" der ve sebebini gizler.
  await signOut(page);

  // Aynı e-posta, farklı kısa ad ile yeniden dene.
  await submitRegistration(page, { ...identity, orgName: `${identity.orgName} 2` });
  // Sunucunun metni gösterilir ve istemci onu EZMEZ: kullanıcı hangisini
  // (e-posta mı kısa ad mı) değiştireceğini bilmeli.
  // (Sonner bildirim bölgesi de `role=alert` taşır; form içindeki uyarı seçilir.)
  await expect(page.getByRole("alert").filter({ hasText: "e-posta" })).toBeVisible();
  await expect(page).not.toHaveURL(/\/panel/);
});
