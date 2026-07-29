import { expect, test } from "@playwright/test";

import {
  activateSubscription,
  apiBaseFor,
  newIdentity,
  registerViaApi,
  signIn,
} from "./support/stack";

/**
 * Akış 4: abonelik → iptal → onay adımı → "erişim şu tarihe kadar" → geri alma.
 *
 * **Bu akış yayın engeliydi** (Tur 7): `/sartlar` 14 gün koşulsuz cayma
 * taahhüt ediyor ve kullanıcının kendi iptal edebildiği bir yol olmadan GA
 * yoktu. Backend tarafı entegrasyon testleriyle kapsandı; burada kanıtlanan
 * şey, o taahhüdün **tarayıcıda gerçekten tıklanabilir** olduğu.
 *
 * Plan `BILLING_PROVIDER=fake` ile checkout'tan AÇILMAZ (gerçek sağlayıcı gibi
 * davranır: ödeme formuna yönlendirir, etkinleşme webhook'la gelir). Bu yüzden
 * abonelik imzalı bir webhook'la etkinleştirilir — dış servise çıkılmaz ve
 * yetkilendirmeyi açan TEK mekanizma da yolun içinde sınanmış olur.
 */
test("abonelik → iptal → onay → erişim tarihi → geri alma", async ({ page, request, baseURL }) => {
  const apiBase = apiBaseFor(baseURL);
  const identity = newIdentity("abonelik");

  // Kiracı API'den açılır (kimliği webhook gövdesi taşımak zorunda); tarayıcı
  // tarafı kayıt akışı `signup-verify.spec.ts`te kapsanıyor.
  const tenantId = await registerViaApi(request, apiBase, identity);
  await signIn(page, identity, /\/panel/);

  // Ücretsiz planda iptal edilecek bir şey yok.
  await page.goto("/usage");
  await expect(page.getByRole("heading", { name: "Kullanım ve abonelik" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Aboneliği iptal et" })).toHaveCount(0);

  // Sağlayıcı olayı planı açar.
  await activateSubscription(request, apiBase, tenantId, "pro");

  await page.goto("/usage");
  await expect(page.getByText("Sıradaki tahsilat")).toBeVisible();
  const cancelButton = page.getByRole("button", { name: "Aboneliği iptal et" }).first();
  await expect(cancelButton).toBeVisible();

  // ── İptal: onay adımı VAR ama karanlık desen YOK ───────────────────────────
  await cancelButton.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  // Onay kutusu geri alınabilirliği açıkça söylüyor (caydırma değil, bilgi).
  await expect(dialog.getByText(/geri alabilirsiniz/i)).toBeVisible();
  await dialog.getByRole("button", { name: "Aboneliği iptal et" }).click();

  // ── İptal sonrası: erişimin ne zamana kadar sürdüğü YAZILI ────────────────
  //
  // Sayfa gövdesine bakılır, bildirime (toast) DEĞİL: başarı bildirimi aynı
  // cümleyi taşıyor ve kapsam daraltılmazsa iki eşleşme çıkıyor. Üstelik toast
  // birkaç saniyede kayboluyor — kapsamsız bir beklenti, koşuya göre bazen
  // geçen bazen düşen bir test üretir (ilk koşuda geçti, ikincisinde düştü).
  // Asıl iddia zaten kalıcı olan: KARTTA yazıyor mu.
  const content = page.getByRole("main");
  await expect(content.getByText(/erişiminiz/i)).toBeVisible();
  await expect(content.getByText(/tarihine kadar sürüyor/i)).toBeVisible();
  // Sayfanın en görünür işareti de gerçeği söylüyor ("Etkin" demiyor).
  await expect(content.getByText("Dönem sonunda bitiyor")).toBeVisible();
  // İptal edene "sıradaki tahsilat" gösterilmez.
  await expect(content.getByText("Sıradaki tahsilat")).toHaveCount(0);

  // ── Geri alma: iptal, başlatmak kadar kolay geri alınır ───────────────────
  const resumeButton = page.getByRole("button", { name: "İptali geri al" });
  await expect(resumeButton).toBeVisible();
  await resumeButton.click();

  await expect(content.getByText("Sıradaki tahsilat")).toBeVisible();
  await expect(content.getByText("Dönem sonunda bitiyor")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Aboneliği iptal et" }).first()).toBeVisible();
});

/**
 * İptal, plana geçmekle **aynı derinlikte** olmalı: bir tık + bir onay.
 *
 * `/sartlar` koşulsuz cayma hakkı veriyor; bir hakkı arayüzde sürtünmeyle
 * zorlaştırmak onu fiilen geri almaktır. Bu test sürtünmeyi sayar — onay
 * kutusunda yazı yazdırma (metin girişi) ya da ek adım olmamalı.
 */
test("iptal onayında yazı yazdırma ya da ek adım yok", async ({ page, request, baseURL }) => {
  const apiBase = apiBaseFor(baseURL);
  const identity = newIdentity("iptal-surtunme");

  const tenantId = await registerViaApi(request, apiBase, identity);
  await signIn(page, identity, /\/panel/);
  await activateSubscription(request, apiBase, tenantId, "pro");

  await page.goto("/usage");
  await page.getByRole("button", { name: "Aboneliği iptal et" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  // Onay kutusunda hiçbir metin girişi olmamalı (hesap KAPATMADA vardır ve
  // orada yerindedir — iptal geri alınabilir, hesap kapatma değil).
  await expect(dialog.locator("input[type=text], input:not([type])")).toHaveCount(0);
  // Ve onaydan sonra iptal TAMAMLANIR (ikinci bir "emin misiniz" yok).
  await dialog.getByRole("button", { name: "Aboneliği iptal et" }).click();
  await expect(page.getByRole("main").getByText(/tarihine kadar sürüyor/i)).toBeVisible();
});
