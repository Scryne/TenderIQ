import { expect, test } from "@playwright/test";

import {
  apiBaseFor,
  extractLink,
  newIdentity,
  registerViaApi,
  signIn,
  submitRegistration,
  waitForEmail,
} from "./support/stack";

/**
 * Akış 5: `/usage` — bütçe/depolama görünürlüğü ve yönetici teşhisinin kapsamı.
 *
 * **Neden E2E:** teşhis verisinin (harcama, rezerve, `unpriced_calls`, kur
 * durumu) yalnız kiracı yöneticisine açık olduğu uç seviyesinde
 * `test_usage_flow.py` ile kilitlendi. Burada kanıtlanan şey farklı ve
 * tarayıcıya özgü: **arayüz o kapıyı kendi tarafında da tutuyor mu.** Üye
 * sayfayı açtığında teşhis kartını hiç görmemeli — 403 alıp boş bir kart
 * çizmemeli, kartı hiç istememeli. "Sunucu nasılsa reddeder" düşünmek, üyeye
 * yönetici verisi vaat eden bir kutu göstermeye yeter.
 */

/**
 * Yeni kiracının gördüğü hâl: dört boyut da sıfır olduğu için ekran boş
 * durumdadır (§10.1) — ama kullanıcının HAKKI (kota · bütçe · depolama ·
 * yenilenme tarihi) yine de yazılıdır. Boş durumun bilgiyi de sakladığı bir
 * regresyon, bu ekranı işlevsiz bırakırdı.
 */
async function expectEntitlementsVisible(page: import("@playwright/test").Page): Promise<void> {
  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "Bu dönem" })).toBeVisible();
  await expect(main.getByText("Bu dönemde henüz analiz yapılmadı")).toBeVisible();
  await expect(main.getByText(/analiz bütçesi ₺/)).toBeVisible();
  await expect(main.getByText(/Depolama kotası/)).toBeVisible();
}

test("kullanıcı /usage'da bütçe ve depolama görür; yönetici ayrıca teşhisi görür", async ({
  page,
}) => {
  const admin = newIdentity("kullanim-yonetici");

  await submitRegistration(page, admin);
  await page.waitForURL(/\/panel/);

  await page.goto("/usage");
  await expect(page.getByRole("heading", { name: "Kullanım ve abonelik" })).toBeVisible();

  // Yeni kiracı hiç analiz yapmadı: §10.1 boş durumu bir DAVETTİR, eylem taşır.
  const main = page.getByRole("main");
  await expectEntitlementsVisible(page);
  await expect(main.getByRole("link", { name: "İhalelere git" })).toBeVisible();

  // Yönetici teşhisi görünür ve "yalnız yönetici" olduğu ekranda yazıyor.
  await expect(main.getByRole("heading", { name: "Yönetici teşhisi" })).toBeVisible();
  await expect(main.getByText("Yalnız yönetici")).toBeVisible();
  await expect(main.getByText("Tutarı hesaplanamayan")).toBeVisible();
});

test("üye /usage'ı açar ama yönetici teşhisini GÖRMEZ", async ({
  page,
  request,
  baseURL,
  browser,
}) => {
  const apiBase = apiBaseFor(baseURL);
  const admin = newIdentity("kullanim-sizinti");
  const member = newIdentity("kullanim-uye");

  await registerViaApi(request, apiBase, admin);
  await signIn(page, admin, /\/panel/);

  // Üye davet edilir (rol seçici varsayılanı "Üye").
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Davetler" }).click();
  const inviteEmail = page.getByLabel("E-posta", { exact: false });
  await expect(inviteEmail).toBeVisible();
  await inviteEmail.fill(member.email);
  await page.getByRole("button", { name: "Davet et" }).click();
  await expect(page.getByText("Davet gönderildi.")).toBeVisible();

  const message = await waitForEmail(request, apiBase, {
    to: member.email,
    kind: "invitation",
  });
  const target = new URL(extractLink(message.text, "/accept-invitation"));

  // Üye TEMİZ bir bağlamda katılır — yöneticinin oturumu taşınmamalı, yoksa
  // test rol ayrımını değil aynı kullanıcıyı iki kez ölçer.
  const memberContext = await browser.newContext();
  const memberPage = await memberContext.newPage();
  try {
    await memberPage.goto(`${baseURL}/accept-invitation${target.search}`);
    await memberPage.getByLabel("Ad soyad").fill("Ayşe Demir");
    await memberPage.getByLabel(/Parola/).fill(member.password);
    await memberPage.getByRole("button", { name: "Daveti kabul et" }).click();
    await memberPage.waitForURL(/\/panel|\/tenders/);

    await memberPage.goto("/usage");
    // Üye kendi kullanımını görür…
    await expectEntitlementsVisible(memberPage);

    // …teşhis kartı ise HİÇ çizilmez: ne başlığı, ne rozeti, ne de sayıları.
    const memberMain = memberPage.getByRole("main");
    await expect(memberMain.getByRole("heading", { name: "Yönetici teşhisi" })).toHaveCount(0);
    await expect(memberMain.getByText("Yalnız yönetici")).toHaveCount(0);
    await expect(memberMain.getByText("Tutarı hesaplanamayan")).toHaveCount(0);
    // Boş bir "yetkiniz yok" kartı da bırakılmamalı — kart hiç istenmiyor.
    await expect(memberMain.getByText("Teşhis bilgisi alınamadı.")).toHaveCount(0);

    // Ve asıl kapı sunucuda: üye ucu SAYFANIN İÇİNDEN çağırsa da veri alamaz.
    //
    // `page.request` kullanılmıyor: o bağlam oturum çerezini taşımıyor ve
    // isteği kimliksiz gönderiyor (401) — yani "üye reddedildi" değil, "kimse
    // reddedildi" ölçülürdü, ki bu hiçbir şey kanıtlamaz. `evaluate` içindeki
    // `fetch` sayfanın kendi origin'inde ve kendi çerezleriyle koşar; ölçülen
    // şey gerçekten ÜYENİN aldığı yanıt olur.
    const status = await memberPage.evaluate(async () => {
      const response = await fetch("/api/v1/usage/admin");
      return response.status;
    });
    expect(status).toBe(403);
  } finally {
    await memberContext.close();
  }
});
