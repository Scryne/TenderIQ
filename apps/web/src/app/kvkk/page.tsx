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
  title: "Aydınlatma metni — TenderIQ",
  description:
    "TenderIQ'nun KVKK kapsamında işlediği kişisel veriler, işleme amaçları, aktarımlar, saklama süreleri ve veri sahibi hakları.",
};

const SECTIONS: LegalSectionData[] = [
  {
    id: "veri-sorumlusu",
    title: "1. Veri sorumlusu",
    body: (
      <>
        <p>
          Veri sorumlusu <Fill>[Şirket ticaret unvanı]</Fill> olup, adresi{" "}
          <Fill>[Şirket adresi]</Fill>, Mersis/VKN bilgisi <Fill>[VKN]</Fill>&apos;dir. Başvuru ve
          iletişim: <Fill>[KEP adresi]</Fill> · <Fill>[iletişim e-postası]</Fill>.
        </p>
        <p>
          VERBİS kayıt yükümlülüğü <Fill>[değerlendirildi / gerekli değil / kayıt no]</Fill>.
        </p>
      </>
    ),
  },
  {
    id: "veriler",
    title: "2. İşlenen kişisel veriler",
    body: (
      <>
        <p>
          TenderIQ iki farklı veri kümesiyle çalışır ve bunları birbirinden ayrı tutar: sizin{" "}
          <strong className="font-medium text-ink-1">hesap verileriniz</strong> ve platforma
          yüklediğiniz <strong className="font-medium text-ink-1">doküman içeriği</strong>.
        </p>
        <LegalList
          items={[
            <>
              <strong className="font-medium text-ink-1">Kimlik ve iletişim:</strong> ad soyad,
              e-posta adresi, çalıştığınız organizasyonun unvanı ve içindeki rolünüz.
            </>,
            <>
              <strong className="font-medium text-ink-1">Hesap güvenliği:</strong> parolanızın geri
              döndürülemez özeti (Argon2), oturum kayıtları, e-posta doğrulama durumu.
            </>,
            <>
              <strong className="font-medium text-ink-1">İşlem güvenliği:</strong> giriş denemeleri,
              IP adresi (yalnız kötüye kullanım sınırlaması için, kısa süreli), denetim kayıtları
              (kim, ne zaman, hangi kaydı değiştirdi).
            </>,
            <>
              <strong className="font-medium text-ink-1">Yüklediğiniz doküman içeriği:</strong>{" "}
              şartname ve ekleri. Bu belgeler kural olarak kurumsal içeriktir; ancak imza sirküleri,
              özgeçmiş veya referans mektubu gibi eklerde kişisel veri bulunabilir. Bu içeriğin
              kapsamını <strong className="font-medium text-ink-1">siz belirlersiniz</strong>.
            </>,
            <>
              <strong className="font-medium text-ink-1">Kullanım ve faturalama:</strong> işlenen
              doküman/sayfa sayısı, plan bilgisi, fatura kayıtları.
            </>,
          ]}
        />
      </>
    ),
  },
  {
    id: "amac",
    title: "3. İşleme amaçları ve hukuki sebepleri",
    body: (
      <>
        <LegalTable
          headers={["Amaç", "Hukuki sebep (KVKK md. 5)"]}
          rows={[
            [
              "Hesabınızı oluşturmak, hizmeti sunmak, dokümanlarınızı çözümlemek",
              "Sözleşmenin kurulması ve ifası (md. 5/2-c)",
            ],
            [
              "Faturalandırma, ödeme ve muhasebe kayıtlarının tutulması",
              "Kanuni yükümlülük (md. 5/2-a) — VUK, TTK",
            ],
            [
              "Hesap güvenliği, kötüye kullanım ve dolandırıcılığın engellenmesi",
              "Meşru menfaat (md. 5/2-f)",
            ],
            [
              "Hizmet kalitesinin ölçülmesi, hata ayıklama, kapasite planlaması",
              "Meşru menfaat (md. 5/2-f)",
            ],
            [
              "Talebiniz hâlinde destek sağlanması ve iletişim kurulması",
              "Sözleşmenin ifası (md. 5/2-c)",
            ],
          ]}
        />
      </>
    ),
  },
  {
    id: "aktarim",
    title: "4. Aktarımlar ve yurt dışına aktarım",
    body: (
      <>
        <p>
          Hizmetin sunulabilmesi için sınırlı sayıda alt işleyenden yararlanılır. Güncel liste,
          hizmet yeri ve amacıyla birlikte{" "}
          <Link
            href="/trust"
            className="text-ink-1 underline decoration-border-strong underline-offset-4"
          >
            güven merkezinde
          </Link>{" "}
          yayımlanır.
        </p>
        <p>
          <strong className="font-medium text-ink-1">
            Yüklediğiniz doküman içeriği, çözümleme sırasında bir yapay zekâ sağlayıcısına iletilir.
          </strong>{" "}
          Sağlayıcı ile <em>sıfır saklama</em> (zero-retention) ve{" "}
          <em>model eğitiminde kullanmama</em> yapılandırması sözleşmeseldir: içerik sağlayıcı
          tarafında kalıcı olarak saklanmaz ve model eğitimine girmez.
        </p>
        <p>
          Seçili sağlayıcı yurt dışında bulunuyorsa bu bir{" "}
          <strong className="font-medium text-ink-1">yurt dışına aktarımdır</strong> ve KVKK md. 9
          kapsamında <Fill>[açık rıza / standart sözleşme / taahhütname — seçilen yol]</Fill>{" "}
          mekanizmasına dayanır. Yürürlükteki sağlayıcı ve veri işleme yeri:{" "}
          <Fill>[LLM sağlayıcısı ve bölge]</Fill>.
        </p>
        <p>
          Yüklediğiniz dosyalar nesne depolamada şifreli olarak tutulur; depolama bölgesi{" "}
          <Fill>[veri ikametgâhı bölgesi]</Fill>&apos;dir.
        </p>
      </>
    ),
  },
  {
    id: "toplama",
    title: "5. Toplama yöntemi",
    body: (
      <>
        <p>
          Kişisel verileriniz; kayıt formu, davet bağlantısı, platform üzerindeki eylemleriniz ve
          yüklediğiniz dosyalar aracılığıyla <strong className="font-medium text-ink-1">
            elektronik ortamda
          </strong>{" "}
          ve doğrudan sizden toplanır. Üçüncü kaynaklardan veri zenginleştirmesi yapılmaz.
        </p>
      </>
    ),
  },
  {
    id: "saklama",
    title: "6. Saklama süreleri ve silme",
    body: (
      <>
        <p>
          Sildiğiniz içerik önce tüm görüntüleme yollarından düşer, ardından saklama penceresi
          dolduğunda dosyalarıyla birlikte kalıcı olarak silinir. Hesabınızı{" "}
          <strong className="font-medium text-ink-1">Ayarlar → Verilerim</strong> ekranından
          kapatabilirsiniz.
        </p>
        <LegalTable
          headers={["Veri", "Saklama"]}
          rows={[
            ["İhale, doküman, çıkarılan bulgular ve yüklenen dosyalar", "Silinene kadar; silme sonrası 30 gün"],
            ["Hesap ve üyelik bilgileri", "Hesap kapatılana kadar; kapatmada silinir"],
            [
              "Fatura ve kullanım kayıtları",
              "Vergi mevzuatı (VUK) gereği 10 yıl — hesabınızı kapatsanız da saklanır",
            ],
            ["Denetim kayıtları", "En az 1 yıl (güvenlik ve kanıt amacıyla)"],
            ["Oturum ve tek kullanımlık bağlantı kayıtları", "Kısa ömürlü; süresi dolunca otomatik silinir"],
            ["Yapay zekâ sağlayıcısına iletilen içerik", "Sıfır saklama — sağlayıcıda tutulmaz"],
          ]}
        />
        <p>
          <strong className="font-medium text-ink-1">
            Hesabınızı kapatsanız da fatura kayıtlarınız vergi mevzuatı gereği 10 yıl saklanır.
          </strong>{" "}
          Bu, KVKK md. 7&apos;nin kanuni saklama yükümlülüğü istisnasıdır. Bu kayıtların bağlı
          olduğu organizasyon kaydı, adı ve kısa adı anonimleştirilmiş hâlde tutulur.
        </p>
      </>
    ),
  },
  {
    id: "haklar",
    title: "7. Haklarınız (KVKK md. 11)",
    body: (
      <>
        <LegalList
          items={[
            "Kişisel verilerinizin işlenip işlenmediğini öğrenme ve işlenmişse buna ilişkin bilgi talep etme.",
            "İşleme amacını ve amacına uygun kullanılıp kullanılmadığını öğrenme.",
            "Yurt içinde veya yurt dışında verilerin aktarıldığı üçüncü kişileri bilme.",
            "Eksik veya yanlış işlenmiş verilerin düzeltilmesini isteme.",
            "Kanundaki şartlar çerçevesinde silinmesini veya yok edilmesini isteme.",
            "İşlemenin münhasıran otomatik sistemlerle analiz edilmesi suretiyle aleyhinize bir sonuç çıkmasına itiraz etme.",
            "Kanuna aykırı işleme nedeniyle zarara uğramanız hâlinde zararın giderilmesini talep etme.",
          ]}
        />
        <p>
          Erişim hakkınızı (md. 11/1-a-b) platformdan doğrudan kullanabilirsiniz:{" "}
          <strong className="font-medium text-ink-1">Ayarlar → Verilerim → Verilerimi indir</strong>{" "}
          bağlantısı hesabınızın makine okunur (JSON) kopyasını üretir. Diğer talepleriniz için{" "}
          <Fill>[başvuru e-postası / KEP]</Fill> adresine yazabilirsiniz; başvurular en geç{" "}
          <strong className="font-medium text-ink-1">30 gün</strong> içinde sonuçlandırılır.
        </p>
      </>
    ),
  },
  {
    id: "cerezler",
    title: "8. Çerez politikası",
    body: (
      <>
        <p>
          TenderIQ yalnızca <strong className="font-medium text-ink-1">zorunlu çerezler</strong>{" "}
          kullanır. Reklam, profilleme veya üçüncü taraf takip çerezi kullanılmaz; bu nedenle rıza
          bandı gösterilmez.
        </p>
        <LegalTable
          headers={["Çerez", "Amacı ve süresi"]}
          rows={[
            [
              "Oturum çerezi",
              "Giriş yaptığınızı hatırlar. Tarayıcı JavaScript'ine kapalıdır (httpOnly) ve yalnız aynı siteye gönderilir.",
            ],
            [
              "Oturum yenileme çerezi",
              "Sık sık yeniden giriş yapmanızı önler; her kullanımda yenilenir, çıkışta iptal edilir.",
            ],
            [
              "Tema tercihi",
              "Açık/koyu tema seçiminizi tarayıcınızda saklar; sunucuya gönderilmez.",
            ],
          ]}
        />
      </>
    ),
  },
  {
    id: "degisiklik",
    title: "9. Değişiklikler",
    body: (
      <>
        <p>
          Bu metin, hizmet veya mevzuat değiştiğinde güncellenir. Esaslı değişikliklerde hesap
          e-posta adresinize bildirim gönderilir; güncel sürüm her zaman bu sayfada yayımlanır.
        </p>
      </>
    ),
  },
];

export default function KvkkPage() {
  return (
    <LegalPage
      title="Kişisel verilerin korunması hakkında aydınlatma metni"
      intro="6698 sayılı Kişisel Verilerin Korunması Kanunu'nun 10. maddesi uyarınca, TenderIQ hizmetini kullanırken hangi kişisel verilerinizin, hangi amaçla ve ne kadar süreyle işlendiğini açıklar."
      updated="28.07.2026"
      sections={SECTIONS}
    />
  );
}
