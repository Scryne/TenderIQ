/**
 * Hukuki metinlerin **tek gerçek kaynağı**.
 *
 * Buradaki alanlar iki sınıfa ayrılır:
 *
 * - **A grubu (`undefined` başlar):** yalnız şirket sahibinde bulunan gerçek
 *   veriler — ticaret unvanı, VKN, KEP… Bunlar **asla örnek değerle
 *   doldurulmaz**: bir aydınlatma metninde uydurma bir VKN, boş bırakmaktan
 *   daha ağır bir hatadır çünkü doğru görünür. Eksikken sayfa amber uyarı
 *   gösterir ve taslak bandı otomatik açık kalır.
 * - **B grubu (dolu gelir):** ürün kararı olan ve burada sabitlenen değerler
 *   (cayma süresi, ihlal bildirim süresi…). Bunlar metinde de tekrarlanmaz,
 *   buradan okunur.
 *
 * Doldurulacakların ne olduğu ve nereden alınacağı: kökteki `LEGAL_TODO.md`.
 */

/** VERBİS kayıt durumu — yükümlülük eşiği çalışan sayısı/mali bilançoya bağlıdır. */
export type VerbisStatus = "kayitli" | "muaf" | "belirlenmedi";

/** Bir alt işleyenin işleme bölgesi; yapılandırmaya bağlı olanlar buradan okunur. */
export type Region = string;

export type LegalCompany = {
  /** Ticaret sicilindeki tam unvan. */
  tradeName?: string;
  /** Tebligata elverişli açık adres. */
  address?: string;
  /** Yetkili mahkeme ve icra daireleri bu şehirden TÜRETİLİR — metne sabit yazılmaz. */
  city?: string;
  /** Vergi kimlik numarası. */
  taxId?: string;
  /** Mersis numarası. */
  mersis?: string;
  /** Kayıtlı elektronik posta adresi. */
  kep?: string;
  /** Genel iletişim. */
  contactEmail?: string;
  /** KVKK md. 11 başvurularının yapılacağı adres. */
  privacyEmail?: string;
  /** Güvenlik açığı bildirimleri. */
  securityEmail?: string;
  /** Kurumsal/satış iletişimi. */
  salesEmail?: string;
};

export type LegalRegions = {
  /** Uygulama ve veritabanının barındırıldığı bölge. */
  hosting?: Region;
  /** Yüklenen dosyaların tutulduğu bölge. */
  objectStorage?: Region;
  /** Çözümleme sağlayıcısının işleme bölgesi. */
  llm?: Region;
  /** İşlemsel e-posta sağlayıcısının bölgesi. */
  email?: Region;
};

/**
 * Alt işleyen — **kodda gerçekten kullanılan** sağlayıcılardan türetilir,
 * tahmin edilmez. Kaynaklar: `packages/core/pyproject.toml` (boto3, sentry-sdk,
 * anthropic/openai/ollama, langfuse), `apps/web/package.json` (@sentry/nextjs),
 * `.env.example` (OBJECT_STORAGE_ENDPOINT_URL, *_PROVIDER anahtarları).
 */
export type SubProcessor = {
  /** Sağlayıcı adı; yapılandırmaya bağlıysa `undefined` (dağıtımda belirlenir). */
  name?: string;
  purpose: string;
  dataCategory: string;
  /** Bölge alanının `LegalRegions` içindeki karşılığı. */
  regionKey?: keyof LegalRegions;
  /** Sağlayıcı seçimi ortam değişkeniyle değişiyorsa hangi değişken. */
  configuredBy?: string;
};

export const SUB_PROCESSORS: SubProcessor[] = [
  {
    purpose: "Uygulama ve veritabanı barındırma",
    dataCategory: "Hesap verileri, doküman üstverisi, çıkarılan bulgular",
    regionKey: "hosting",
  },
  {
    name: "Cloudflare R2",
    purpose: "Yüklenen dosyaların saklanması",
    dataCategory: "Doküman dosyaları (şifreli)",
    regionKey: "objectStorage",
  },
  {
    purpose: "Doküman çözümlemesi (yapay zekâ)",
    dataCategory: "Doküman parçaları — sıfır saklama, model eğitiminde kullanılmaz",
    regionKey: "llm",
    configuredBy: "LLM_PROVIDER",
  },
  {
    purpose: "İşlemsel e-posta gönderimi",
    dataCategory: "Ad soyad ve e-posta adresi",
    regionKey: "email",
    configuredBy: "EMAIL_PROVIDER",
  },
  {
    purpose: "Abonelik tahsilatı",
    dataCategory: "Fatura bilgileri — kart verisi TenderIQ'ya hiç gelmez",
    configuredBy: "BILLING_PROVIDER",
  },
  {
    name: "Sentry",
    purpose: "Hata izleme ve arıza teşhisi",
    dataCategory: "Hata kayıtları — kişisel veri maskelenir, doküman içeriği gönderilmez",
  },
  {
    name: "Langfuse",
    purpose: "Yapay zekâ çağrılarının teknik ölçümü (opsiyonel)",
    dataCategory: "Model adı, gecikme, jeton sayısı — istem/çıktı gönderilmez",
  },
];

/** Ürün kararı olan, burada sabitlenen koşullar (§1B). Metinlerde tekrarlanmaz. */
export const LEGAL_TERMS = {
  /** Cayma hakkı — mevzuat B2B'de zorunlu kılmasa da ticari olarak veriliyor. */
  withdrawalDays: 14,
  /** Veri ihlalinin veri sorumlusuna bildirim süresi (DPA). */
  breachNotificationHours: 24,
  /** Alt işleyen değişikliğinin önceden bildirim süresi. */
  subProcessorNoticeDays: 30,
  /** Aleyhe esaslı sözleşme değişikliğinin bildirim süresi. */
  termsChangeNoticeDays: 30,
  /** Denetim sıklığı (yılda kaç kez) ve önceden bildirim süresi. */
  auditPerYear: 1,
  auditNoticeDays: 30,
  /** Sorumluluk tavanının hesaplandığı geçmiş dönem. */
  liabilityMonths: 12,
  /** Silme sonrası kalıcı imha penceresi — DATA_RETENTION_DAYS ile aynı olmalı. */
  retentionDays: 30,
  /** Fatura/defter kayıtlarının kanuni saklama süresi (VUK). */
  fiscalRetentionYears: 10,
} as const;

export const LEGAL_CONFIG: {
  company: LegalCompany;
  regions: LegalRegions;
  verbisStatus: VerbisStatus;
  /** Metinlerin hukuk onayından geçip geçmediği — onay alınınca `true`. */
  reviewedByCounsel: boolean;
  lastUpdated: string;
} = {
  // ── A GRUBU ── Doldurulacak: bkz. LEGAL_TODO.md. Örnek değer YAZMA.
  company: {
    tradeName: undefined,
    address: undefined,
    city: undefined,
    taxId: undefined,
    mersis: undefined,
    kep: undefined,
    contactEmail: undefined,
    privacyEmail: undefined,
    securityEmail: undefined,
    salesEmail: undefined,
  },
  regions: {
    hosting: undefined,
    objectStorage: undefined,
    llm: undefined,
    email: undefined,
  },
  verbisStatus: "belirlenmedi",
  reviewedByCounsel: false,
  lastUpdated: "29.07.2026",
};

/**
 * Taslak bandının görünmesi için gereken A-grubu alanlar.
 *
 * Liste bilinçli olarak dar: metnin **hukuken eksik** sayılacağı alanlar.
 * `mersis`, `securityEmail`, `salesEmail` gibi alanlar eksikse metin yine
 * yayımlanabilir (ilgili cümle o alanı atlar).
 */
const REQUIRED_COMPANY_FIELDS = [
  "tradeName",
  "address",
  "city",
  "taxId",
  "kep",
  "contactEmail",
  "privacyEmail",
] as const satisfies readonly (keyof LegalCompany)[];

const REQUIRED_REGION_FIELDS = [
  "hosting",
  "objectStorage",
  "llm",
] as const satisfies readonly (keyof LegalRegions)[];

/** Eksik zorunlu alanların anahtarları — taslak uyarısında sayılır. */
export function missingLegalFields(): string[] {
  const missing: string[] = [];
  for (const field of REQUIRED_COMPANY_FIELDS) {
    if (!LEGAL_CONFIG.company[field]) missing.push(`company.${field}`);
  }
  for (const field of REQUIRED_REGION_FIELDS) {
    if (!LEGAL_CONFIG.regions[field]) missing.push(`regions.${field}`);
  }
  if (LEGAL_CONFIG.verbisStatus === "belirlenmedi") missing.push("verbisStatus");
  if (!LEGAL_CONFIG.reviewedByCounsel) missing.push("reviewedByCounsel");
  return missing;
}

/**
 * Metin hâlâ taslak mı — **elle ayarlanmaz, türetilir**.
 *
 * `draft={false}` yazılabilseydi, bir alan eksikken de yayına alınabilirdi ve
 * uyarı sessizce kaybolurdu. Eksik alan geri geldiğinde bandın kendiliğinden
 * dönmesi için tek yol, kararı veriden türetmektir.
 */
export function isLegalDraft(): boolean {
  return missingLegalFields().length > 0;
}

/** Yetkili mahkeme ifadesi — şehir yoksa `undefined` (metin uyarıya düşer). */
export function competentCourts(): string | undefined {
  const city = LEGAL_CONFIG.company.city;
  return city === undefined ? undefined : `${city} mahkemeleri ve icra daireleri`;
}
