// Giriş sayfası — "zaten girişli misin" kontrolü BURADA yapılır, middleware'de değil.
//
// Eski davranış: middleware, oturum cookie'si VARSA /login'i koşulsuz /tenders'a
// yönlendiriyordu. Middleware cookie'nin geçerliliğini göremez; token bayat ya da
// bozuksa kullanıcı kilitleniyordu — giriş sayfasına ulaşılamıyor, /tenders ise
// 401 alıp boş kalıyordu. Kurtuluş yalnızca istemci JS'inin 401'i görüp cookie'leri
// temizlemesine bağlıydı; hidrasyon çalışmadığında (ya da sayfa veri çekmeden hata
// verdiğinde) çıkış yolu hiç kalmıyordu.
//
// Burası Node çalışma zamanıdır: `API_URL` çalışma anında okunabilir (edge
// middleware'de okunamaz) ve oturumun yaşayıp yaşamadığı backend'e sorulur.
// Doğrulanamıyorsa giriş formu gösterilir — yanlış tarafa düşmek serbest
// bırakmaktır, kilitlemek değil.

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { API_URL, SESSION_COOKIE } from "@/lib/server/backend";

import { LoginForm } from "./login-form";

/**
 * Oturumun GERÇEKTEN geçerli olup olmadığını backend'e sorar.
 *
 * Erişim token'ı kısa ömürlüdür (≤1 saat) ve refresh cookie'siyle yenilenebilir;
 * burada yenileme DENENMEZ, çünkü rotasyon eski refresh'i yakar ve sunucu bileşeni
 * yeni token'ları cookie'ye yazamaz (Next 15). Süresi dolmuş erişim token'ıyla
 * gelen girişli kullanıcı bu yüzden formu görür — maliyeti bir kez daha parola
 * girmektir, kilitlenme değil.
 */
async function hasLiveSession(): Promise<boolean> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (token === undefined) return false;
  try {
    const response = await fetch(`${API_URL}/api/v1/auth/me`, {
      headers: { authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    return response.ok;
  } catch {
    // Kimlik servisine ulaşılamıyor: yönlendirme yerine form. Aksi hâlde backend
    // kesintisi giriş sayfasını da götürürdü.
    return false;
  }
}

export default async function LoginPage() {
  if (await hasLiveSession()) redirect("/tenders");

  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
