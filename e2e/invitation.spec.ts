import { expect, test } from "@playwright/test";

import {
  apiBaseFor,
  extractLink,
  newIdentity,
  submitRegistration,
  waitForEmail,
} from "./support/stack";

/**
 * Akış 3: davet ile katılma.
 *
 * İki ayrı kişi, iki ayrı tarayıcı bağlamı: yönetici davet eder, davetli kendi
 * parolasını belirleyip katılır. Aynı bağlamda yapılsaydı davetlinin oturumu
 * yöneticinin çerezine binerdi ve test "katılım çalışıyor" derken aslında
 * yöneticinin oturumunu ölçerdi.
 *
 * Davet bağlantısı e-postadan okunur — token uydurulmaz.
 */
test("yönetici davet eder → davetli katılır → panele girer", async ({
  page,
  request,
  baseURL,
  browser,
}) => {
  const apiBase = apiBaseFor(baseURL);
  const admin = newIdentity("davet-yonetici");
  const invitee = newIdentity("davet-uye");

  // 1) Yönetici hesabı açılır (açık kayıt modunda oturum hemen kurulur).
  await submitRegistration(page, admin);
  await page.waitForURL(/\/panel/);

  // 2) Ayarlar → "Davetler" sekmesi → davet formu. Sekme sekmedir: form
  //    varsayılan sekmede DEĞİL, açılması gerekiyor.
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Davetler" }).click();
  const inviteEmail = page.getByLabel("E-posta", { exact: false });
  await expect(inviteEmail).toBeVisible();
  await inviteEmail.fill(invitee.email);
  await page.getByRole("button", { name: "Davet et" }).click();
  await expect(page.getByText("Davet gönderildi.")).toBeVisible();

  // 3) Davet bağlantısı e-postadan okunur.
  const message = await waitForEmail(request, apiBase, {
    to: invitee.email,
    kind: "invitation",
  });
  const link = extractLink(message.text, "/accept-invitation");
  const target = new URL(link);

  // 4) Davetli TEMİZ bir bağlamda katılır (yöneticinin oturumu taşınmasın).
  const guestContext = await browser.newContext();
  const guest = await guestContext.newPage();
  try {
    await guest.goto(`${baseURL}/accept-invitation${target.search}`);
    await expect(guest.getByText("Organizasyona katıl")).toBeVisible();

    await guest.getByLabel("Ad soyad").fill("Ayşe Demir");
    await guest.getByLabel(/Parola/).fill(invitee.password);
    await guest.getByRole("button", { name: "Daveti kabul et" }).click();

    // Katılım oturumu kurar; davetli ürünün içindedir.
    await guest.waitForURL(/\/panel|\/tenders/);
  } finally {
    await guestContext.close();
  }

  // 5) Davet tüketildi: bekleyen davetler listesinde artık yok.
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Davetler" }).click();
  await expect(page.getByText(invitee.email)).toHaveCount(0);

  // 6) Ve davetli gerçekten ÜYE oldu. Satıra göre aranır: e-posta hem hücrede
  //    hem içindeki öğede geçiyor ve düz `getByText` iki eşleşme buluyor.
  await page.getByRole("tab", { name: "Üyeler" }).click();
  const memberRow = page.getByRole("row").filter({ hasText: invitee.email });
  await expect(memberRow).toHaveCount(1);
  await expect(memberRow).toContainText("Ayşe Demir");
});
