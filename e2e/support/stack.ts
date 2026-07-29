import { createHmac, randomUUID } from "node:crypto";

import { expect, type APIRequestContext, type Page } from "@playwright/test";

/**
 * E2E yardımcıları — kimlik üretimi, gelen kutusu, imzalı webhook.
 *
 * Buradaki her şeyin tek amacı testleri **belirleyici** kılmak: benzersiz
 * kimlikler (ikinci koşu "e-posta zaten kayıtlı" ile düşmesin), gelen kutusunun
 * sunucudan okunması (sabit `sleep` yerine gerçek sinyal) ve ödeme akışının dış
 * servise çıkmadan etkinleştirilmesi.
 */

/** Playwright config'teki eşleme: web :3100 → API :8100, web :3101 → :8101. */
const API_BY_WEB: Record<string, string> = {
  "3100": process.env.E2E_API_OPEN ?? "http://127.0.0.1:8100",
  "3101": process.env.E2E_API_WAITLIST ?? "http://127.0.0.1:8101",
};

/** Webhook sırrı — `playwright.config.ts`teki `apiEnv` ile aynı olmak ZORUNDA. */
const WEBHOOK_SECRET = process.env.BILLING_WEBHOOK_SECRET ?? "e2e-webhook-secret";

/**
 * Testin bağlı olduğu web sunucusunun API adresi.
 *
 * `/_test/inbox` web proxy'sinin (yalnız `/api/v1/*`) arkasında DEĞİL, bu yüzden
 * API'ye doğrudan gidilir. Adres baseURL'den türetilir; test hangi projede
 * koştuğunu bilmek zorunda kalmaz.
 */
export function apiBaseFor(baseURL: string | undefined): string {
  const port = new URL(baseURL ?? "http://127.0.0.1:3100").port;
  const api = API_BY_WEB[port];
  if (api === undefined) throw new Error(`Bilinmeyen web portu: ${port}`);
  return api;
}

export type Identity = {
  slug: string;
  orgName: string;
  email: string;
  password: string;
};

/**
 * Her çağrıda benzersiz bir kimlik.
 *
 * Sabit e-posta kullanan bir E2E yalnız İLK koşuda geçer; ikincisinde "bu adres
 * kayıtlı" hatası alır ve testi yazan kişi bunu "flaky" sanır. Benzersizlik
 * burada bir kolaylık değil, doğruluk şartı.
 */
export function newIdentity(prefix: string): Identity {
  const suffix = randomUUID().slice(0, 8);
  const slug = `${prefix}-${suffix}`;
  return {
    slug,
    orgName: `${prefix} Test A.S. ${suffix}`,
    email: `${slug}@tenderiq-e2e.com`,
    password: "e2e-parola-12345",
  };
}

export type InboxMessage = {
  kind: string;
  to: string;
  subject: string;
  text: string;
};

/**
 * Bir alıcıya giden mesajları döndürür — **belirleyici bekleme ile**.
 *
 * E-posta gönderimi isteğin ardından tetiklenir; `expect.poll` mesaj gerçekten
 * görünene kadar bekler. Sabit bir `sleep` ya hızlı makinede erken ölçer ya da
 * yavaş makinede boşuna bekler.
 */
export async function waitForEmail(
  request: APIRequestContext,
  apiBase: string,
  options: { to: string; kind?: string },
): Promise<InboxMessage> {
  const query = new URLSearchParams({ to: options.to });
  if (options.kind !== undefined) query.set("kind", options.kind);
  const url = `${apiBase}/_test/inbox?${query.toString()}`;

  await expect
    .poll(
      async () => {
        const response = await request.get(url);
        if (!response.ok()) return 0;
        return ((await response.json()) as InboxMessage[]).length;
      },
      {
        message: `${options.to} adresine ${options.kind ?? "herhangi bir"} e-posta gelmedi`,
        timeout: 20_000,
      },
    )
    .toBeGreaterThan(0);

  const messages = (await (await request.get(url)).json()) as InboxMessage[];
  return messages[messages.length - 1];
}

/** Düz metin gövdedeki ilk bağlantıyı çıkarır (şablonlar bağlantıyı tam yazar). */
export function extractLink(text: string, mustContain: string): string {
  const match = text.match(/https?:\/\/\S+/g)?.find((url) => url.includes(mustContain));
  if (match === undefined) {
    throw new Error(`Gövdede '${mustContain}' içeren bağlantı yok:\n${text}`);
  }
  return match.replace(/[).,]+$/, "");
}

/** Kayıt formunu doldurup gönderir (açık kayıt ve bekleme listesi için ortak). */
export async function submitRegistration(page: Page, identity: Identity): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Firma unvanı").fill(identity.orgName);
  await page.getByLabel("E-posta").fill(identity.email);
  await page.getByLabel("Parola").fill(identity.password);
  await page.getByRole("button", { name: "Hesap oluştur" }).click();
}

/**
 * Hesabı API üzerinden açar ve kiracı kimliğini döndürür.
 *
 * Kiracı kimliği tarayıcıdan okunamıyor: `page.request` çerez kavanozunu web
 * proxy'sine taşımıyor ve kimlik DOM'da hiçbir yerde yazmıyor. Kayıt akışının
 * TARAYICI tarafı zaten `signup-verify.spec.ts`te kapsanıyor; burada gereken
 * tek şey, abonelik senaryosunun üzerine kurulacağı deterministik bir kiracı.
 */
export async function registerViaApi(
  request: APIRequestContext,
  apiBase: string,
  identity: Identity,
): Promise<string> {
  const response = await request.post(`${apiBase}/api/v1/auth/register`, {
    data: {
      org_name: identity.orgName,
      org_slug: identity.slug,
      email: identity.email,
      password: identity.password,
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  const body = await response.json();
  return body.user.tenant_id as string;
}

/**
 * Oturumu kapatır — uygulamanın kendi yolundan (`DELETE /api/session`).
 *
 * Yalnızca çerezleri silmek daha kolay olurdu ama sunucudaki refresh-token
 * ailesini iptal etmezdi; test o zaman ürünün gerçekte yaptığı şeyi değil,
 * tarayıcının yaptığı şeyi ölçerdi.
 */
export async function signOut(page: Page): Promise<void> {
  const response = await page.request.delete("/api/session");
  expect(response.ok(), await response.text()).toBeTruthy();
}

/** Giriş yapar ve hedef rotaya varıldığını doğrular. */
export async function signIn(page: Page, identity: Identity, expectUrl: RegExp): Promise<void> {
  await page.goto("/login");
  // Giriş formu gerçekten açık mı: oturum kapanmamışsa `/login` panele
  // yönlenir ve alanlar hiç görünmez — hata mesajı "alan bulunamadı" olur ve
  // asıl sebebi (hâlâ oturum açık) gizler.
  await expect(page.getByLabel("E-posta")).toBeVisible();
  await page.getByLabel("E-posta").fill(identity.email);
  await page.getByLabel("Parola").fill(identity.password);
  await page.getByRole("button", { name: "Giriş yap" }).click();
  await page.waitForURL(expectUrl);
}

/**
 * Aboneliği **gerçek yoldan** etkinleştirir: imzalı bir sağlayıcı webhook'u.
 *
 * `BILLING_PROVIDER=fake` checkout'ta planı AÇMAZ (gerçek sağlayıcı gibi
 * davranır: ödeme formuna yönlendirir, etkinleşme webhook'la gelir). Bu yüzden
 * E2E'nin ücretli plana geçmesinin dürüst yolu webhook göndermektir — üstelik
 * bu, ürünün yetkilendirmeyi açan TEK mekanizmasını da sınamış olur.
 */
export async function activateSubscription(
  request: APIRequestContext,
  apiBase: string,
  tenantId: string,
  plan: "pro" | "enterprise" = "pro",
): Promise<void> {
  const body = JSON.stringify({
    event_id: `e2e_${randomUUID()}`,
    event_type: "subscription.activated",
    tenant_id: tenantId,
    plan,
    status: "active",
    occurred_at: new Date().toISOString(),
  });
  const signature = createHmac("sha256", WEBHOOK_SECRET).update(body).digest("hex");
  const response = await request.post(`${apiBase}/api/v1/billing/webhook`, {
    headers: { "content-type": "application/json", "x-tenderiq-signature": signature },
    data: body,
  });
  expect(response.status(), await response.text()).toBe(200);
  expect((await response.json()).status).toBe("applied");
}
