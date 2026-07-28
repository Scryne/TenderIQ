"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { AuthLayout } from "@/components/auth/auth-layout";
import { InlineError } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { isValidSlug, slugify } from "@/lib/slug";

/** Backend sözleşmesi: `password: Field(min_length=8, max_length=128)`. */
const MIN_PASSWORD_LENGTH = 8;

type ApiError = { error?: { code?: string; message?: string } };

/**
 * Kayıt ekranı — DESIGN.md §9.6 (giriş ekranıyla AYNI iskelet).
 *
 * Bu ekranın tek işi: firmayı ürüne sokmak. Ama kayıt sırasında geri
 * alınamayan **tek** karar var — organizasyon kısa adı (slug). Hesap kapatma
 * onayında kullanıcıdan birebir yazması istenir ve backend Türkçe harf kabul
 * etmez. Bu yüzden slug gizli bir alan değil, **ekranın imza öğesi**: firma
 * adından canlı türetilir, kullanıcı görür ve isterse düzeltir.
 */
/** Zorunlu alan yıldızı — ekran okuyucuya da duyurulur (§12). */
function Required() {
  return (
    <span className="text-danger" aria-hidden>
      *
    </span>
  );
}

function RegisterForm() {
  const router = useRouter();
  const [orgName, setOrgName] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [slugInput, setSlugInput] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Kullanıcı slug'a dokunmadıysa firma adını izler; dokunduysa kendi değeri
  // korunur (yazdığı şeyi ad değişince altından çekmek en sinir bozucu form
  // davranışıdır).
  const slug = useMemo(
    () => (slugTouched ? slugify(slugInput) : slugify(orgName)),
    [slugTouched, slugInput, orgName],
  );
  const slugReady = isValidSlug(slug);

  const register = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/v1/auth/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          org_name: orgName.trim(),
          org_slug: slug,
          email: email.trim(),
          password,
          full_name: fullName.trim() === "" ? null : fullName.trim(),
        }),
      });
      if (!response.ok) {
        if (response.status === 429) {
          throw new Error("Çok fazla deneme yapıldı. Birkaç dakika bekleyip yeniden deneyin.");
        }
        const body = (await response.json().catch(() => null)) as ApiError | null;
        const message = body?.error?.message;
        if (response.status === 409) {
          // Backend iki farklı çakışmayı ayırıyor; kullanıcı hangisini
          // değiştireceğini bilmeli.
          throw new Error(message ?? "Bu e-posta veya kısa ad zaten kayıtlı.");
        }
        throw new Error(message ?? "Hesap oluşturulamadı. Biraz sonra yeniden deneyin.");
      }

      // Kayıt token döndürmez; kullanıcıyı giriş ekranına atmak yerine aynı
      // bilgilerle oturum açılır (cookie'ler sunucuda yazılır).
      const session = await fetch("/api/session", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      return session.ok;
    },
    onSuccess: (signedIn) => {
      router.push(signedIn ? "/panel" : "/login");
      router.refresh();
    },
  });

  return (
    <AuthLayout
      title="Hesap oluştur"
      description="Ücretsiz planla başlayın: ayda 5 doküman, kredi kartı istenmez."
      footer={
        <span>
          Hesabınız var mı?{" "}
          <Link
            href="/login"
            className="text-ink-2 underline decoration-border-strong underline-offset-4 hover:decoration-ink-1"
          >
            Giriş yapın
          </Link>
          .
        </span>
      }
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          // Birincil butonu boş formda DEVRE DIŞI bırakmıyoruz: ölü bir buton
          // neyin eksik olduğunu söylemez. Zorunlu alanları tarayıcı doğrulaması
          // gösterir; tek türetilmiş alan (kısa ad) burada kontrol edilir ve
          // sorun varsa alan açılıp odaklanır — kullanıcı düzeltecek yeri görür.
          if (!slugReady) {
            setSlugInput(slug);
            setSlugTouched(true);
            queueMicrotask(() => document.getElementById("org-slug")?.focus());
            return;
          }
          register.mutate();
        }}
      >
        {/* Hata form ÜSTÜNDE tek blok, alan altında değil (§9.6). */}
        {register.isError && <InlineError message={register.error.message} />}

        <p className="text-xs text-ink-3">
          <Required /> işaretli alanlar zorunludur.
        </p>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="org-name">
            Firma unvanı <Required />
          </Label>
          <Input
            id="org-name"
            required
            autoFocus
            autoComplete="organization"
            value={orgName}
            onChange={(event) => setOrgName(event.target.value)}
            placeholder="Örn. Yılmaz Mühendislik San. Tic. Ltd. Şti."
            aria-describedby="org-slug-hint"
          />
          {/* Türetilen kısa ad ile onu değiştirme eylemi AYNI satırda durur:
              alan altında iki ayrı yardım satırı, formun dikey ritmini yalnız
              bu grupta bozuyordu (tur 1 kritiği). */}
          <div className="flex items-baseline justify-between gap-3 text-xs text-ink-3">
            <p id="org-slug-hint" className="min-w-0">
              {slugReady ? (
                <>
                  Çalışma alanı: <span className="font-mono text-ink-2">{slug}</span>
                </>
              ) : (
                "Çalışma alanı kısa adı unvandan türetilir."
              )}
            </p>
            {!slugTouched && (
              <button
                type="button"
                onClick={() => {
                  setSlugInput(slug);
                  setSlugTouched(true);
                }}
                className="shrink-0 underline decoration-border-strong underline-offset-4 hover:text-ink-1 hover:decoration-ink-1"
              >
                Değiştir
              </button>
            )}
          </div>
        </div>

        {/* Türetilen kısa ad kalıcı kimliktir (hesap kapatma onayında birebir
            yazılır) — düzeltme yolu kapalı olmamalı, ama alanı baştan açmak
            formu gereksiz uzatır. */}
        {slugTouched && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="org-slug">
              Çalışma alanı kısa adı <Required />
            </Label>
            <Input
              id="org-slug"
              required
              value={slugInput}
              onChange={(event) => setSlugInput(event.target.value)}
              placeholder="yilmaz-muhendislik"
              aria-invalid={!slugReady || undefined}
              aria-describedby="org-slug-help"
            />
            <p id="org-slug-help" className="text-xs text-ink-3">
              Yalnız küçük harf, rakam ve tire. Hesabı kapatırken bu adı yazmanız istenir.
            </p>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="full-name">
            Ad soyad <span className="text-xs font-normal text-ink-3">(isteğe bağlı)</span>
          </Label>
          <Input
            id="full-name"
            autoComplete="name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            placeholder="Ayşe Demir"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">
            İş e-postası <Required />
          </Label>
          <Input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="ad.soyad@firma.com.tr"
            aria-invalid={register.isError || undefined}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password">
            Parola <Required />
          </Label>
          <Input
            id="password"
            type="password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-describedby="password-help"
          />
          <p id="password-help" className="text-xs text-ink-3">
            En az {MIN_PASSWORD_LENGTH} karakter.
          </p>
        </div>

        <Button type="submit" className="mt-1 w-full" loading={register.isPending}>
          Hesap oluştur
        </Button>

        <p className="text-xs leading-5 text-ink-3">
          Hesap oluşturarak{" "}
          <Link href="/sartlar" className="underline decoration-border-strong underline-offset-4">
            kullanım şartlarını
          </Link>{" "}
          ve{" "}
          <Link href="/kvkk" className="underline decoration-border-strong underline-offset-4">
            aydınlatma metnini
          </Link>{" "}
          kabul etmiş olursunuz.
        </p>
      </form>
    </AuthLayout>
  );
}

export default function RegisterPage() {
  return <RegisterForm />;
}
