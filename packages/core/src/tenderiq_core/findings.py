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


class GroundingResolution(StrEnum):
    """Bulgunun kaynağa bağlanma düzeyi (§6.9, ADR-0006)."""

    ELEMENT = "element"  # tek ParsedElement'te doğrulandı (en keskin bağ)
    CHUNK = "chunk"  # chunk'ta doğrulandı; öğe sınırı aşan alıntı → aralık başı
    UNGROUNDED = "ungrounded"  # kaynakta doğrulanamadı — düşük güven, gösterilmez
