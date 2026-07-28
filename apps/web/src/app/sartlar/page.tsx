import type { Metadata } from "next";
import Link from "next/link";

import {
  Fill,
  LegalList,
  LegalPage,
  LegalTable,
} from "@/components/marketing/legal-shell";
import type { LegalSectionData } from "@/components/marketing/legal-shell";

export const metadata: Metadata = {
  title: "Kullanım şartları — TenderIQ",
  description:
    "TenderIQ hizmetinin kullanım koşulları: hesap, planlar ve ödeme, kabul edilebilir kullanım, fikri mülkiyet, sorumluluk sınırları ve hizmet seviyesi.",
};

const SECTIONS: LegalSectionData[] = [
  {
    id: "taraflar",
    title: "1. Taraflar ve tanımlar",
    body: (
      <>
        <p>
          Bu sözleşme <Fill>[Şirket ticaret unvanı]</Fill> (&quot;TenderIQ&quot;) ile hizmeti
          kullanan tüzel veya gerçek kişi (&quot;Müşteri&quot;) arasındadır.{" "}
          <strong className="font-medium text-ink-1">Müşteri İçeriği</strong>, Müşteri&apos;nin
          platforma yüklediği şartname ve ekleri ile bunlardan üretilen çözümleme sonuçlarını ifade
          eder.
        </p>
      </>
    ),
  },
  {
    id: "hesap",
    title: "2. Hesap ve organizasyon",
    body: (
      <>
        <LegalList
          items={[
            "Hesap açan kişi, temsil ettiği organizasyon adına sözleşme kurma yetkisine sahip olduğunu beyan eder.",
            "Organizasyon yöneticisi üye davet edebilir, rolleri değiştirebilir ve hesabı kapatabilir. Yöneticinin işlemleri organizasyonu bağlar.",
            "Hesap bilgilerinizin ve parolanızın gizliliğinden siz sorumlusunuz. Yetkisiz erişim şüphesinde derhal bildirin.",
            "E-posta adresinizin doğruluğundan siz sorumlusunuz; hizmete ilişkin bildirimler bu adrese yapılır.",
          ]}
        />
      </>
    ),
  },
  {
    id: "planlar",
    title: "3. Planlar, kota ve ödeme",
    body: (
      <>
        <p>
          Hizmet aylık abonelik esasıyla sunulur. Güncel plan ve kotalar{" "}
          <Link
            href="/#fiyatlandirma"
            className="text-ink-1 underline decoration-border-strong underline-offset-4"
          >
            fiyatlandırma bölümünde
          </Link>{" "}
          yayımlanır.
        </p>
        <LegalList
          items={[
            "Kota dönem başına doküman ve sayfa sayısıyla ölçülür. Kota dolduğunda yeni yükleme reddedilir; mevcut verileriniz etkilenmez.",
            "Ücretler KDV hariç belirtilir; fatura, mevzuata uygun olarak e-Arşiv/e-Fatura biçiminde düzenlenir.",
            "Abonelik, iptal edilene kadar dönem sonunda otomatik yenilenir. İptal, içinde bulunulan dönemin sonunda geçerli olur.",
            "Plan yükseltmeleri anında etkinleşir; düşürmeler dönem sonunda uygulanır.",
          ]}
        />
        <p>
          İptal ve iade koşulları: <Fill>[cayma hakkı süresi ve iade politikası]</Fill>. Tüketici
          sıfatını haiz kullanıcıların mevzuattan doğan cayma hakları saklıdır.
        </p>
      </>
    ),
  },
  {
    id: "kullanim",
    title: "4. Kabul edilebilir kullanım",
    body: (
      <>
        <p>Hizmeti kullanırken şunları yapmamayı kabul edersiniz:</p>
        <LegalList
          items={[
            "Yükleme yetkiniz olmayan, gizlilik yükümlülüğü altındaki veya üçüncü kişilerin haklarını ihlal eden belgeleri yüklemek.",
            "Platformu tersine mühendislik yapmak, otomatik araçlarla aşırı yük bindirmek veya kota sınırlarını dolanmak.",
            "Erişim bilgilerinizi organizasyonunuz dışındaki kişilerle paylaşmak.",
            "Hizmeti, yürürlükteki mevzuata veya kamu düzenine aykırı amaçlarla kullanmak.",
          ]}
        />
        <p>
          Bu kuralların ağır ihlali hâlinde hesap askıya alınabilir. Askıya alma öncesinde, güvenlik
          gerektirmedikçe, durumu düzeltmeniz için makul süre verilir.
        </p>
      </>
    ),
  },
  {
    id: "mulkiyet",
    title: "5. Fikri mülkiyet ve veriniz üzerindeki haklar",
    body: (
      <>
        <LegalList
          items={[
            <>
              <strong className="font-medium text-ink-1">Müşteri İçeriği size aittir.</strong>{" "}
              TenderIQ, içeriğiniz üzerinde yalnızca hizmeti sunmak için gereken sınırlı işleme
              hakkına sahiptir.
            </>,
            <>
              <strong className="font-medium text-ink-1">
                İçeriğiniz model eğitiminde kullanılmaz.
              </strong>{" "}
              Yapay zekâ sağlayıcılarıyla sıfır saklama ve eğitimde kullanmama yapılandırması
              sözleşmeseldir.
            </>,
            "Platformun yazılımı, arayüzü ve markası TenderIQ'ya aittir; hizmeti kullanma hakkınız devredilemez ve münhasır değildir.",
            "Hizmeti geliştirmek için gönderdiğiniz geri bildirimleri TenderIQ serbestçe kullanabilir.",
          ]}
        />
      </>
    ),
  },
  {
    id: "cikti",
    title: "6. Yapay zekâ çıktısının niteliği",
    body: (
      <>
        <p>
          <strong className="font-medium text-ink-1">
            TenderIQ hukuki danışmanlık vermez ve teklif kararınızın yerine geçmez.
          </strong>{" "}
          Ürün, şartnamedeki maddeleri çıkarır ve her bulguyu kaynağındaki sayfa ve maddeye bağlar;
          amacı kararı sizin adınıza vermek değil, kararı{" "}
          <strong className="font-medium text-ink-1">denetlenebilir</strong> kılmaktır.
        </p>
        <p>
          Çıkarım eksik veya hatalı olabilir. Bu nedenle her bulgunun kaynağı gösterilir ve
          incelemeden geçirilmesi beklenir. Teklif verme, fiyatlama ve uygunluk kararlarının
          sorumluluğu Müşteri&apos;dedir.
        </p>
      </>
    ),
  },
  {
    id: "hizmet-seviyesi",
    title: "7. Hizmet seviyesi ve kesintiler",
    body: (
      <>
        <p>
          Hedeflenen hizmet seviyeleri aşağıdadır. Bunlar{" "}
          <Fill>[beta / GA — taahhüt niteliği]</Fill> olup, kurumsal planlarda ayrı bir hizmet
          seviyesi taahhüdü (SLA) sözleşmeyle düzenlenir.
        </p>
        <LegalTable
          headers={["Ölçüt", "Hedef"]}
          rows={[
            ["Hizmet erişilebilirliği (aylık)", "≥ %99,5"],
            ["Arayüz yanıt süresi (p95)", "< 500 ms"],
            ["100 sayfalık dijital dokümanın işlenmesi", "< 10 dakika"],
            ["İşleme başarı oranı", "≥ %98"],
          ]}
        />
        <p>
          Planlı bakımlar önceden duyurulur. Yapay zekâ sağlayıcısı kaynaklı kesintilerde çözümleme
          gecikebilir; bu durumda dokümanlarınız kuyrukta korunur ve hizmet döndüğünde işlenir.
        </p>
      </>
    ),
  },
  {
    id: "sorumluluk",
    title: "8. Sorumluluğun sınırlandırılması",
    body: (
      <>
        <p>
          TenderIQ&apos;nun toplam sorumluluğu, talebin doğduğu olaydan önceki{" "}
          <strong className="font-medium text-ink-1">12 ayda</strong> ödediğiniz abonelik bedeliyle
          sınırlıdır. Kâr kaybı, iş kaybı, ihale kaybı veya dolaylı zararlardan sorumluluk kabul
          edilmez. Kasıt ve ağır ihmal hâlleri ile mevzuatın sınırlamaya izin vermediği durumlar
          saklıdır.
        </p>
      </>
    ),
  },
  {
    id: "fesih",
    title: "9. Sözleşmenin sona ermesi",
    body: (
      <>
        <p>
          Hesabınızı dilediğiniz zaman kapatabilirsiniz. Kapatma sonrası içeriğiniz ve dosyalarınız{" "}
          <strong className="font-medium text-ink-1">30 gün</strong> içinde kalıcı olarak silinir;
          fatura kayıtları vergi mevzuatı gereği saklanır. Ayrıntı için{" "}
          <Link
            href="/kvkk#saklama"
            className="text-ink-1 underline decoration-border-strong underline-offset-4"
          >
            aydınlatma metnine
          </Link>{" "}
          bakın. Kapatmadan önce verilerinizi dışa aktarmanız önerilir.
        </p>
      </>
    ),
  },
  {
    id: "uygulanacak-hukuk",
    title: "10. Uygulanacak hukuk ve yetki",
    body: (
      <>
        <p>
          Bu sözleşmeye Türkiye Cumhuriyeti hukuku uygulanır. Uyuşmazlıklarda{" "}
          <Fill>[yetkili mahkeme ve icra daireleri]</Fill> yetkilidir. Tüketici sıfatını haiz
          kullanıcılar bakımından tüketici hakem heyetlerinin yetkisi saklıdır.
        </p>
      </>
    ),
  },
  {
    id: "degisiklik",
    title: "11. Değişiklikler",
    body: (
      <>
        <p>
          Koşullar güncellenebilir. Aleyhinize esaslı değişikliklerde en az{" "}
          <strong className="font-medium text-ink-1">30 gün</strong> önce e-posta ile bildirim
          yapılır; bu süre içinde aboneliğinizi ücretsiz sonlandırabilirsiniz.
        </p>
      </>
    ),
  },
];

export default function TermsPage() {
  return (
    <LegalPage
      title="Kullanım şartları"
      intro="TenderIQ'yu kullanarak bu koşulları kabul etmiş olursunuz. Metin, hizmetin ne yaptığını ve ne yapmadığını açıkça yazar — özellikle yapay zekâ çıktısının hukuki niteliği konusunda."
      updated="28.07.2026"
      sections={SECTIONS}
    />
  );
}
