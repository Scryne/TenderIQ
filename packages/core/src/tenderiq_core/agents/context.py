"""Ajan adları + ajan başına TR ihale-alanı getirim sorguları (§6.7).

Sorgu şablonları TR kamu ihale terminolojisiyle yazılmıştır (idari/teknik
şartname + sözleşme tasarısı dili). Her ajan, dokümandan KENDİ bakış açısının
bağlamını bu sorgularla getirir; şablonlar golden-set kalibrasyonuyla
Sprint 2.4'te gözden geçirilir.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum


class AgentName(StrEnum):
    """Çıkarım ajanları (§6.7). Compliance, CapabilityProfile ile Sprint 2.3'te."""

    REQUIREMENTS = "requirements"  # gereksinim listesi (teknik/idari/mali)
    DELIVERABLES = "deliverables"  # sunulacak belge/sertifika/teminat
    RISKS = "risks"  # cezai şart, olağandışı/riskli maddeler
    TIMELINE = "timeline"  # ihale/teslim/garanti takvimi


AGENT_QUERY_TEMPLATES: Mapping[AgentName, tuple[str, ...]] = {
    AgentName.REQUIREMENTS: (
        "teknik gereksinimler ve asgari şartlar",
        "idari şartlar ve yeterlik kriterleri",
        "mali ve ekonomik yeterlik kriterleri",
        "isteklinin taşıması gereken zorunlu şartlar",
    ),
    AgentName.DELIVERABLES: (
        "teklif kapsamında sunulacak belgeler",
        "geçici teminat ve kesin teminat tutarı",
        "iş deneyim belgesi ve iş bitirme belgesi",
        "istenen sertifikalar ve kalite belgeleri",
    ),
    AgentName.RISKS: (
        "cezai şart ve gecikme cezası oranı",
        "sözleşmenin feshi ve yasaklılık halleri",
        "garanti yükümlülükleri ve bakım süresi",
        "fiyat farkı verilmeyecek haller",
    ),
    AgentName.TIMELINE: (
        "ihale tarihi ve tekliflerin sunulacağı tarih",
        "işin süresi ve teslim programı",
        "teklif geçerlilik süresi",
        "işe başlama ve iş bitirme tarihi",
    ),
}
