"""``tenderiq_core.services.deletion`` birim testleri — süpürme sırası ve kararları.

Asıl sınanan davranış: nesne depolamadaki dosya silinemezse DB satırı BIRAKILIR.
Bu ters çevrilirse depoda kime ait olduğu bilinmeyen bir dosya kalır ve "sildim"
beyanı yanlış olur (KVKK).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tenderiq_core.services.deletion import PurgeResult, purge_cutoff


def test_purge_cutoff_saklama_suresini_geriye_sayar() -> None:
    now = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
    assert purge_cutoff(30, now=now) == now - timedelta(days=30)


def test_purge_cutoff_sifir_gun_ani_silme_demektir() -> None:
    """0 gün = "geri alma penceresi yok"; yumuşak silme aynı gün kalıcılaşır."""
    now = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
    assert purge_cutoff(0, now=now) == now


def test_purge_result_bos_ise_anything_false() -> None:
    assert PurgeResult().anything is False


def test_purge_result_yalniz_nesne_silinse_bile_anything_true() -> None:
    """Satır silinmese de dosya silindiyse rapor edilmeli (denetim izi için)."""
    assert PurgeResult(objects_deleted=1).anything is True


def test_purge_result_basarisiz_nesne_anything_saymaz() -> None:
    """Hiçbir şey silinemediyse "iş yapıldı" denmemeli."""
    assert PurgeResult(objects_failed=3).anything is False
