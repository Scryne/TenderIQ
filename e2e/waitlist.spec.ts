import { expect, test } from "@playwright/test";

import { apiBaseFor, newIdentity, submitRegistration } from "./support/stack";

/**
 * Akış 2: bekleme listesi modu (`SIGNUP_MODE=waitlist`).
 *
 * **Bu mod üretimde hiç koşmadı.** Kapalı beta açılışının tek kapısı olacak ve
 * ilk kez gerçek kullanıcıyla denenmesi, en kötü zamanda arıza bulmak demek.
 *
 * Mod SUNUCU seviyesindedir; bu yüzden spec kendi yığınında koşar (bkz.
 * `playwright.config.ts` → `bekleme-listesi` projesi, :3101/:8101). Modu
 * istemciden taklit etmek, sınamak istediğimiz şeyi — sunucunun kararını —
 * atlardı.
 *
 * Sınanan asıl davranış: **hesap AÇILMAZ.** Bekleme listesi modunda kaydolan
 * biri sessizce hesap sahibi olsaydı mod hiçbir işe yaramazdı.
 */
test("bekleme listesi modunda kayıt hesap açmaz, sıraya alır", async ({
  page,
  request,
  baseURL,
}) => {
  const identity = newIdentity("bekleme");

  await submitRegistration(page, identity);

  // Form yerine sonuç ekranı; kullanıcı panele DÜŞMEZ.
  await expect(page.getByRole("heading", { name: "Sıraya alındınız" })).toBeVisible();
  await expect(page.getByText(identity.email)).toBeVisible();
  await expect(page).not.toHaveURL(/\/panel/);

  // Hesap gerçekten açılmadı: aynı bilgilerle giriş yapılamaz.
  await page.goto("/login");
  await page.getByLabel("E-posta").fill(identity.email);
  await page.getByLabel("Parola").fill(identity.password);
  await page.getByRole("button", { name: "Giriş yap" }).click();
  await expect(page).not.toHaveURL(/\/panel/);

  // Ve API doğrudan sorulduğunda da "waitlisted" diyor (arayüz metnine değil,
  // sunucunun kararına bakan ikinci bir kanıt).
  const apiBase = apiBaseFor(baseURL);
  const direct = await request.post(`${apiBase}/api/v1/auth/register`, {
    data: {
      org_name: `${identity.orgName} 2`,
      org_slug: `${identity.slug}-2`,
      email: `ikinci-${identity.email}`,
      password: identity.password,
    },
  });
  expect(direct.status()).toBe(202);
  expect((await direct.json()).status).toBe("waitlisted");
});
