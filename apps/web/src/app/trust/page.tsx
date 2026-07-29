import { KeyRound, Layers, Lock, ShieldCheck, Trash2, type LucideIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import {
  LegalList,
  LegalPage,
  SubProcessorTable,
  Value,
} from "@/components/marketing/legal-shell";
import type { LegalSectionData } from "@/components/marketing/legal-shell";
import { LEGAL_CONFIG } from "@/config/legal.config";

export const metadata: Metadata = {
  title: "Güven merkezi — TenderIQ",
  description:
    "Verinizin TenderIQ içinde izlediği yol, sıfır saklama yapay zekâ yapılandırması, alt işleyen listesi, veri konumu ve güvenlik önlemleri.",
};

/** Verinin ürün içinde izlediği yol — güven, soyut vaatle değil akışla kurulur. */
const FLOW: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: Lock,
    title: "1. Yükleme",
    body: "Dosya tarayıcınızdan doğrudan nesne depolamaya, süreli ve imzalı bir bağlantıyla gider. Bağlantı yalnız o dosya için ve kısa süreliğine geçerlidir.",
  },
  {
    icon: Layers,
    title: "2. Ayrıştırma",
    body: "Doküman sayfa ve madde düzeyinde parçalanır. Her parça hangi sayfanın hangi koordinatından geldiğini taşır — kaynak gösterimi buradan doğar.",
  },
  {
    icon: KeyRound,
    title: "3. Çözümleme",
    body: "Yalnız ilgili parçalar yapay zekâ sağlayıcısına gönderilir; tüm doküman değil. Sağlayıcı içeriği saklamaz ve model eğitiminde kullanmaz.",
  },
  {
    icon: ShieldCheck,
    title: "4. İnceleme",
    body: "Bulgular kaynağına bağlı olarak size döner. Kaynağı gösterilemeyen bir bulgu ekrana çıkmaz.",
  },
  {
    icon: Trash2,
    title: "5. Silme",
    body: "Sildiğinizde kayıt anında görünmez olur; saklama penceresi dolunca önce depolamadaki dosya, sonra veritabanı satırı kalıcı olarak silinir.",
  },
];

const SECTIONS: LegalSectionData[] = [
  {
    id: "akis",
    title: "Verinizin izlediği yol",
    body: (
      <>
        <div className="flex flex-col gap-4">
          {FLOW.map((step) => (
            <div key={step.title} className="flex gap-3.5">
              <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-sm border border-border bg-surface">
                <step.icon aria-hidden className="size-[18px] text-ink-2" strokeWidth={1.75} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink-1">{step.title}</p>
                <p className="mt-1 text-sm leading-6 text-ink-2">{step.body}</p>
              </div>
            </div>
          ))}
        </div>
      </>
    ),
  },
  {
    id: "zero-retention",
    title: "Sıfır saklama yapay zekâ yapılandırması",
    body: (
      <>
        <p>
          Çözümleme için kullanılan dil modeli sağlayıcısıyla iki şey sözleşmeseldir:{" "}
          <strong className="font-medium text-ink-1">içerik saklanmaz</strong> (zero-retention) ve{" "}
          <strong className="font-medium text-ink-1">model eğitiminde kullanılmaz</strong>. Bu,
          ürünün mimari kararlarından biridir ve sağlayıcı değişse dahi korunması zorunludur.
        </p>
        <p>
          Ayrıca gönderilen veri en aza indirilir: sağlayıcıya tüm doküman değil, yalnız o soruyla
          ilgili parçalar iletilir. Gözlemleme (izleme/hata ayıklama) araçlarına doküman içeriği
          <strong className="font-medium text-ink-1"> varsayılan olarak gönderilmez</strong>; yalnız
          model adı, gecikme ve jeton sayısı gibi teknik ölçüler gider.
        </p>
      </>
    ),
  },
  {
    id: "alt-isleyenler",
    title: "Alt işleyenler",
    body: (
      <>
        <p>
          Hizmetin sunulması için aşağıdaki sağlayıcılardan yararlanılır. Bu liste değiştiğinde
          güncellenir; kurumsal müşterilere önceden bildirim yapılır.
        </p>
        <SubProcessorTable />
      </>
    ),
  },
  {
    id: "izolasyon",
    title: "Kiracı izolasyonu",
    body: (
      <>
        <p>
          Her organizasyonun verisi veritabanı seviyesinde ayrılır: satır bazlı güvenlik (RLS)
          politikaları, uygulama bir hata yapsa dahi başka bir organizasyonun satırının
          okunmasına <strong className="font-medium text-ink-1">veritabanı tarafından</strong> izin
          vermez. Uygulama, güvenlik politikalarını atlayabilen ayrıcalıklı bir veritabanı rolüyle
          hiçbir zaman bağlanmaz. Bu izolasyon, her sürümde gerçek bir veritabanına karşı otomatik
          testlerle doğrulanır.
        </p>
      </>
    ),
  },
  {
    id: "guvenlik",
    title: "Güvenlik önlemleri",
    body: (
      <>
        <LegalList
          items={[
            "Parolalar geri döndürülemez biçimde (Argon2) özetlenir; hiçbir yerde düz metin tutulmaz.",
            "Oturumlar kısa ömürlüdür ve her kullanımda yenilenir; çalınan bir oturum bileti tekrar kullanılırsa oturum ailesi tümüyle iptal edilir.",
            "Dosyalara yalnız süreli, imzalı bağlantılarla erişilir; depolama alanı doğrudan erişime kapalıdır.",
            "Yüklenen dosyalar tür ve imza (magic byte) doğrulamasından geçer; doğrulamayı geçemeyen dosya silinir.",
            "Kritik işlemler (yükleme, dışa aktarma, silme, rol değişimi) denetim kaydına yazılır.",
            "Kayıtlarda kişisel veri yerine korelasyon kimlikleri tutulur; bu kural otomatik bir denetimle her sürümde sınanır.",
            "Bağımlılık ve imaj taramaları ile gizli anahtar taraması, her değişiklikte bloke edici olarak çalışır.",
          ]}
        />
        <p>
          Güvenlik öz denetimi düzenli olarak tekrarlanır; bulgular ve kabul edilen riskler kayıt
          altına alınır. Bir güvenlik açığı fark ederseniz{" "}
          <Value value={LEGAL_CONFIG.company.securityEmail} field="company.securityEmail" /> adresine bildirin — bildirimlere{" "}
          5 iş günü içinde dönülür.
        </p>
      </>
    ),
  },
  {
    id: "dayaniklilik",
    title: "Yedekleme ve süreklilik",
    body: (
      <>
        <p>
          Veritabanı düzenli olarak yedeklenir ve yedekler ayrı bir konumda şifreli tutulur. Hedefler:{" "}
          24 saat veri kaybı toleransı, 4 saat geri dönüş süresi. Geri
          yükleme yalnız yapılandırılmakla kalmaz, aylık tatbikatla
          doğrulanır.
        </p>
      </>
    ),
  },
  {
    id: "belgeler",
    title: "İlgili belgeler",
    body: (
      <>
        <LegalList
          items={[
            <>
              <Link
                href="/kvkk"
                className="text-ink-1 underline decoration-border-strong underline-offset-4"
              >
                Aydınlatma metni
              </Link>{" "}
              — hangi veri, hangi amaçla, ne kadar süre.
            </>,
            <>
              <Link
                href="/dpa"
                className="text-ink-1 underline decoration-border-strong underline-offset-4"
              >
                Veri işleme sözleşmesi (DPA)
              </Link>{" "}
              — kurumsal müşteriler için sözleşme eki.
            </>,
            <>
              <Link
                href="/sartlar"
                className="text-ink-1 underline decoration-border-strong underline-offset-4"
              >
                Kullanım şartları
              </Link>{" "}
              — hizmet seviyesi ve sorumluluk sınırları.
            </>,
          ]}
        />
      </>
    ),
  },
];

export default function TrustPage() {
  return (
    <LegalPage
      title="Güven merkezi"
      intro="İhale dosyanız ticari sırrınızdır. Bu sayfa, o dosyanın TenderIQ içinde nereye gittiğini, kimin eline geçtiğini ve ne zaman silindiğini pazarlama diliyle değil, teknik ayrıntısıyla anlatır."
      sections={SECTIONS}
    />
  );
}
