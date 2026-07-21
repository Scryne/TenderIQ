"""Bulgu sözleşme tipleri (Sprint 2.2) — ajan şemaları ile ORM'nin ortak enum'ları.

``parsing.types`` deseniyle aynı: enum'lar tek kaynaktır ve bağımlılık yönü
gereği (models ← agents, B.2) nötr bir modülde yaşar — ORM modelleri ``agents``
paketini import etmeden bu tipleri kullanır (döngüsel import kırılır). Ajan
şemaları (``agents.schemas``) ve grounding (``agents.grounding``) bu tipleri
yeniden dışa aktarır; ajan sözleşmesi ile DB şeması ayrışamaz.
"""

from __future__ import annotations

from enum import StrEnum


class RequirementKind(StrEnum):
    """Gereksinim tipi (§8.1 ``Requirement``)."""

    TECHNICAL = "technical"  # teknik şartlar (ürün/hizmet nitelikleri, SLA...)
    ADMINISTRATIVE = "administrative"  # idari şartlar (yeterlik, usul, süreler...)
    FINANCIAL = "financial"  # mali/ekonomik şartlar (ciro, bilanço, teminat oranı...)


class DeliverableKind(StrEnum):
    """Sunulacak belge tipi (§8.1 ``Deliverable``)."""

    DOCUMENT = "document"  # idari/teknik belge (iş deneyim belgesi, taahhütname...)
    CERTIFICATE = "certificate"  # sertifika/kalite belgesi (ISO, TSE, CE...)
    GUARANTEE = "guarantee"  # teminat (geçici/kesin teminat mektubu...)
    OTHER = "other"


class RiskSeverity(StrEnum):
    """Risk maddesinin önem derecesi (Sprint 2.3, §8.2 ``RiskFlag``)."""

    LOW = "low"  # olağan/standart; farkındalık yeterli
    MEDIUM = "medium"  # dikkat gerektirir (ör. yüksek gecikme cezası oranı)
    HIGH = "high"  # tekliften önce mutlaka değerlendirilmeli (ör. sınırsız sorumluluk)


class RiskCategory(StrEnum):
    """Risk maddesinin türü (TR ihale alanı; getirim şablonlarıyla hizalı)."""

    PENALTY = "penalty"  # cezai şart / gecikme cezası
    TERMINATION = "termination"  # sözleşmenin feshi / yasaklılık halleri
    WARRANTY = "warranty"  # garanti / bakım yükümlülükleri
    PAYMENT = "payment"  # ödeme koşulları / fiyat farkı verilmemesi
    OTHER = "other"  # yukarıdakilere uymayan olağandışı/riskli madde


class TimelineKind(StrEnum):
    """Takvim öğesinin türü (Sprint 2.3, §8.2 ``TimelineEvent``)."""

    TENDER_DATE = "tender_date"  # ihale (açılış) tarihi
    BID_DEADLINE = "bid_deadline"  # son teklif verme tarihi/saati
    DELIVERY = "delivery"  # işin süresi / teslim programı
    WARRANTY = "warranty"  # garanti/bakım süresi
    OTHER = "other"  # diğer tarih/süre (ör. teklif geçerlilik süresi)


class ComplianceStatus(StrEnum):
    """Gereksinimin firma yetkinlik profiline göre karşılanma durumu (§6.7)."""

    MET = "met"  # profil gereksinimi tam karşılıyor
    PARTIAL = "partial"  # kısmen karşılanıyor / belirsiz — insan incelemesi gerek
    UNMET = "unmet"  # profil gereksinimi karşılamıyor (kapanması gereken boşluk)


class GroundingResolution(StrEnum):
    """Bulgunun kaynağa bağlanma düzeyi (§6.9, ADR-0006)."""

    ELEMENT = "element"  # tek ParsedElement'te doğrulandı (en keskin bağ)
    CHUNK = "chunk"  # chunk'ta doğrulandı; öğe sınırı aşan alıntı → aralık başı
    UNGROUNDED = "ungrounded"  # kaynakta doğrulanamadı — düşük güven, gösterilmez


class ReviewStatus(StrEnum):
    """Bulgunun insan-döngüde inceleme durumu (Sprint 3.2, §4.3).

    Çıkarım sonrası her bulgu PENDING doğar; insan onaylar, düzeltir (içerik
    değişikliği) veya reddeder. EDITED onaylı sayılır (düzeltilmiş hâliyle);
    REJECTED bulgular export'a girmez. Yeniden çıkarım (delete+insert) inceleme
    durumunu bilinçli sıfırlar — yeni çıkarım yeni inceleme gerektirir.
    """

    PENDING = "pending"  # onay bekliyor (varsayılan)
    APPROVED = "approved"  # insan onayladı
    EDITED = "edited"  # insan içeriği düzeltti (onaylı sayılır)
    REJECTED = "rejected"  # insan reddetti (hatalı/geçersiz bulgu)


class FindingKind(StrEnum):
    """Bulgu koleksiyonlarının ortak adresleme anahtarı (yorum/geçmiş uçları).

    Değerler AuditLog ``resource_type`` alanında ve API yollarında kullanılır;
    inceleme UI'sindeki beş sekmeyle birebir eşleşir.
    """

    REQUIREMENT = "requirement"
    DELIVERABLE = "deliverable"
    RISK = "risk"
    TIMELINE = "timeline"
    COMPLIANCE = "compliance"
