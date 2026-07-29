import type { Metadata } from "next";
import Link from "next/link";

import {
  LegalList,
  LegalPage,
  LegalTable,
  Value,
} from "@/components/marketing/legal-shell";
import type { LegalSectionData } from "@/components/marketing/legal-shell";
import { LEGAL_CONFIG, LEGAL_TERMS } from "@/config/legal.config";

export const metadata: Metadata = {
  title: "Veri işleme sözleşmesi (DPA) — TenderIQ",
  description:
    "Kurumsal müşteriler için veri işleyen sıfatıyla yükümlülükler: işleme konusu, güvenlik önlemleri, alt işleyenler, ihlal bildirimi ve iade/imha.",
};

const SECTIONS: LegalSectionData[] = [
  {
    id: "taraflar",
    title: "1. Taraflar ve sıfatlar",
    body: (
      <>
        <p>
          Müşteri, platforma yüklediği içerik bakımından{" "}
          <strong className="font-medium text-ink-1">veri sorumlusudur</strong>;{" "}
          <Value value={LEGAL_CONFIG.company.tradeName} field="company.tradeName" /> ise bu içeriği Müşteri&apos;nin talimatları
          doğrultusunda işleyen <strong className="font-medium text-ink-1">veri işleyendir</strong>.
        </p>
        <p>
          TenderIQ&apos;nun kendi müşteri ilişkisi kapsamında topladığı hesap ve fatura verileri
          bakımından ise TenderIQ veri sorumlusudur; bu işleme{" "}
          <Link
            href="/kvkk"
            className="text-ink-1 underline decoration-border-strong underline-offset-4"
          >
            aydınlatma metninde
          </Link>{" "}
          açıklanır.
        </p>
      </>
    ),
  },
  {
    id: "konu",
    title: "2. İşlemenin konusu, süresi ve kapsamı",
    body: (
      <>
        <LegalTable
          headers={["Başlık", "İçerik"]}
          rows={[
            ["Konu", "İhale/şartname dosyalarının çözümlenmesi ve bulguların kaynağına bağlanması"],
            ["Süre", "Abonelik süresi boyunca; sona ermeden sonra saklama penceresi (30 gün)"],
            ["İşleme türleri", "Saklama, ayrıştırma, dizinleme, çözümleme, görüntüleme, dışa aktarma, silme"],
            [
              "Veri kategorileri",
              "Kural olarak kurumsal içerik; eklerde yer alabilecek kimlik/iletişim/özgeçmiş verileri",
            ],
            [
              "İlgili kişi grupları",
              "Müşteri çalışanları ve yetkilileri; belgelerde adı geçen üçüncü kişiler",
            ],
          ]}
        />
      </>
    ),
  },
  {
    id: "talimat",
    title: "3. Talimatla işleme",
    body: (
      <>
        <p>
          Veri işleyen, kişisel verileri yalnızca Müşteri&apos;nin{" "}
          <strong className="font-medium text-ink-1">belgelendirilmiş talimatları</strong>{" "}
          doğrultusunda işler. Platform üzerinde yaptığınız işlemler (yükleme, çözümleme başlatma,
          dışa aktarma, silme) bu talimatı oluşturur. Kanuni bir yükümlülük nedeniyle talimat dışına
          çıkılması gerekirse, yasak olmadıkça Müşteri önceden bilgilendirilir.
        </p>
      </>
    ),
  },
  {
    id: "gizlilik",
    title: "4. Gizlilik",
    body: (
      <>
        <p>
          Veriye erişebilen personel, gizlilik yükümlülüğü altındadır ve erişim{" "}
          <strong className="font-medium text-ink-1">yalnız görevin gerektirdiği ölçüde</strong>{" "}
          verilir. Üretim verisine erişim kayıt altına alınır.
        </p>
      </>
    ),
  },
  {
    id: "onlemler",
    title: "5. Teknik ve idari tedbirler",
    body: (
      <>
        <p>
          Uygulanan tedbirlerin ayrıntısı{" "}
          <Link
            href="/trust"
            className="text-ink-1 underline decoration-border-strong underline-offset-4"
          >
            güven merkezinde
          </Link>{" "}
          yayımlanır ve bu sözleşmenin ayrılmaz ekidir. Başlıcaları:
        </p>
        <LegalList
          items={[
            "Kiracı izolasyonu veritabanı seviyesinde satır bazlı güvenlik politikalarıyla zorlanır.",
            "Aktarımda ve beklemede şifreleme; dosyalara yalnız süreli ve imzalı bağlantılarla erişim.",
            "Parolaların geri döndürülemez özetlenmesi; kısa ömürlü ve yenilenen oturumlar.",
            "Rol bazlı yetkilendirme ve kritik işlemlerin denetim kaydı.",
            "Kayıtlarda kişisel veri yerine korelasyon kimliği kullanılması.",
            "Bağımlılık, imaj ve gizli anahtar taramalarının her değişiklikte bloke edici çalışması.",
            "Düzenli güvenlik öz denetimi ve bulguların kayıt altına alınması.",
          ]}
        />
      </>
    ),
  },
  {
    id: "alt-isleyen",
    title: "6. Alt işleyenler",
    body: (
      <>
        <p>
          Müşteri, güven merkezinde listelenen alt işleyenlerin kullanımına genel izin verir. Listeye
          yeni bir alt işleyen eklenmesi hâlinde Müşteri en az{" "}
          {LEGAL_TERMS.subProcessorNoticeDays} gün önce bilgilendirilir ve makul gerekçeyle itiraz
          edebilir. İtiraz hâlinde taraflar makul bir çözüm arar; çözüm bulunamazsa Müşteri
          aboneliğini <strong className="font-medium text-ink-1">cezasız olarak feshedebilir</strong>{" "}
          ve kullanılmamış döneme düşen bedel iade edilir. Veri işleyen, alt işleyenlerine bu
          sözleşmedekiyle{" "}
          <strong className="font-medium text-ink-1">eşdeğer yükümlülükler</strong> getirir ve
          onların fiillerinden sorumludur.
        </p>
      </>
    ),
  },
  {
    id: "aktarim",
    title: "7. Yurt dışına aktarım",
    body: (
      <>
        <p>
          Çözümleme sağlayıcısının yurt dışında bulunması hâlinde aktarım, KVKK md. 9/3 uyarınca
          taraflar arasında imzalanan ve Kurum&apos;a bildirilen{" "}
          <strong className="font-medium text-ink-1">standart sözleşme</strong>ye dayanır. Açık rıza
          yoluna dayanılmaz: bu yol arızi aktarımlar içindir, doküman içeriğinin her çözümlemede
          iletilmesi ise süreklilik arz eder. Standart sözleşmenin imzalı nüshası bu ekin ayrılmaz
          parçasıdır.
        </p>
        <p>
          Aktarılan veri en aza indirilir (tüm doküman değil, yalnız ilgili parçalar) ve sağlayıcıda
          saklanmaz. Müşteri talep ederse, çözümleme sağlayıcısı yurt içi veya AB bölgesindeki bir
          sağlayıcıyla değiştirilebilir; bu değişiklik yapılandırmayla yapılır ve{" "}
          <strong className="font-medium text-ink-1">aktarımı tümüyle ortadan kaldırır</strong>.
          Yürürlükteki sağlayıcı ve bölge güven merkezinde yayımlanır.
        </p>
      </>
    ),
  },
  {
    id: "ihlal",
    title: "8. Veri ihlali bildirimi",
    body: (
      <>
        <p>
          Veri işleyen, bir kişisel veri ihlalinden haberdar olduğunda Müşteri&apos;yi{" "}
          <strong className="font-medium text-ink-1">gecikmeksizin</strong> ve en geç{" "}
          {LEGAL_TERMS.breachNotificationHours} saat içinde bilgilendirir. Bildirim; ihlalin
          niteliğini, etkilenen veri kategorilerini, olası sonuçlarını ve alınan/alınacak önlemleri
          içerir. Müşteri&apos;nin Kurul&apos;a ve ilgili kişilere yapacağı bildirimlerde makul destek
          sağlanır.
        </p>
      </>
    ),
  },
  {
    id: "haklar",
    title: "9. İlgili kişi taleplerine destek",
    body: (
      <>
        <p>
          Erişim, düzeltme ve silme talepleri platform üzerinden doğrudan karşılanabilir: dışa aktarma
          ve silme uçları Müşteri yöneticisinin kullanımına açıktır. Platformdan karşılanamayan
          taleplerde veri işleyen, Müşteri&apos;ye makul teknik destek verir.
        </p>
      </>
    ),
  },
  {
    id: "denetim",
    title: "10. Denetim",
    body: (
      <>
        <p>
          Müşteri, bu sözleşmeye uyumu denetleme hakkına sahiptir. Yerinde denetim{" "}
          <strong className="font-medium text-ink-1">
            yılda {LEGAL_TERMS.auditPerYear} kez
          </strong>
          , en az {LEGAL_TERMS.auditNoticeDays} gün önceden yazılı bildirimle ve operasyonu
          aksatmayacak biçimde yapılır. Denetim, veri işleyenin sunacağı{" "}
          <strong className="font-medium text-ink-1">bağımsız denetim raporuyla</strong> (varsa)
          ikame edilebilir; rapor talebi karşılıyorsa yerinde denetim hakkı o dönem için
          kullanılmış sayılır. Makul olmayan sıklıktaki taleplerin masrafı talep edene aittir.
        </p>
      </>
    ),
  },
  {
    id: "iade",
    title: "11. İade ve imha",
    body: (
      <>
        <p>
          Sözleşme sona erdiğinde Müşteri, verilerini dışa aktarma ucuyla makine okunur biçimde
          alabilir. Saklama penceresi (
          <strong className="font-medium text-ink-1">30 gün</strong>) dolduğunda içerik ve dosyalar
          kalıcı olarak silinir. Kanuni saklama yükümlülüğü bulunan fatura ve denetim kayıtları
          istisnadır; bunlar süresi dolana dek erişimi kısıtlı biçimde saklanır.
        </p>
      </>
    ),
  },
  {
    id: "imza",
    title: "12. Yürürlük",
    body: (
      <>
        <p>
          Bu ek, Müşteri ile imzalanan hizmet sözleşmesinin ayrılmaz parçasıdır ve çelişki hâlinde
          kişisel verilerin korunmasına ilişkin hükümler bakımından{" "}
          <strong className="font-medium text-ink-1">öncelikle uygulanır</strong>. İmzalı nüsha talebi
          için: <Value value={LEGAL_CONFIG.company.salesEmail} field="company.salesEmail" />.
        </p>
      </>
    ),
  },
];

export default function DpaPage() {
  return (
    <LegalPage
      title="Veri işleme sözleşmesi (DPA)"
      intro="Kurumsal müşteriler için hazırlanan sözleşme ekidir. TenderIQ'nun veri işleyen sıfatıyla yükümlülüklerini, uygulanan güvenlik önlemlerini ve sözleşme sonunda verinin akıbetini düzenler."
      sections={SECTIONS}
    />
  );
}
