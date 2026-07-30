"""LLM maliyet ölçümü — fiyat hesabı, sarmalama ve kayıp kayıt sayımı (J.6).

Bu testlerin asıl konusu **belirsizliğin gizlenmemesi**. Maliyet ölçümünde en
tehlikeli arıza çökmek değil, "0 TL" yazmaktır: tavan sessizce sonsuz olur ve
kimse fark etmez. Bu yüzden testlerin çoğu, 0'ın hangi anlama geldiğini
ayırt edip etmediğimize bakıyor.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from tenderiq_core.llm.cost import (
    CostTracer,
    collect_llm_usage,
    drain_buffer,
)
from tenderiq_core.llm.pricing import (
    MICROS_PER_TRY,
    ModelPrice,
    PricingStatus,
    PricingTable,
    load_pricing,
    reset_pricing_cache,
)
from tenderiq_core.llm.tracing import LLMTracer
from tenderiq_core.logging import tenant_id_var

TENANT = uuid.uuid4()


def _table(**overrides: object) -> PricingTable:
    models = {
        "dogrulanmis": ModelPrice(input_per_mtok_usd=3.0, output_per_mtok_usd=15.0, verified=True),
        "dogrulanmamis": ModelPrice(
            input_per_mtok_usd=3.0, output_per_mtok_usd=15.0, verified=False
        ),
        "bedava-yerel": ModelPrice(input_per_mtok_usd=0.0, output_per_mtok_usd=0.0, verified=True),
    }
    return PricingTable(
        models=models,
        usd_try_rate=overrides.get("usd_try_rate", 40.0),  # type: ignore[arg-type]
        source="test",
    )


# ── Fiyat hesabı ────────────────────────────────────────────────────────────


def test_maliyet_hesabi_dogru() -> None:
    """1M girdi + 1M çıktı token = (3 + 15) USD × kur."""
    table = _table()
    micros, status = table.cost_micros_try(
        "dogrulanmis", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert status is PricingStatus.PRICED
    assert micros == round(18.0 * 40.0 * MICROS_PER_TRY)


def test_kismi_token_orantili_hesaplanir() -> None:
    table = _table()
    micros, _ = table.cost_micros_try("dogrulanmis", input_tokens=1_000, output_tokens=0)
    # 1000 token = 1M'in binde biri → 3 USD / 1000 = 0.003 USD
    assert micros == round(0.003 * 40.0 * MICROS_PER_TRY)


def test_dogrulanmamis_fiyat_tutari_hesaplar_ama_isaretler() -> None:
    """Tahmin, hesaplanmamış olmaktan iyidir — ama tahmin olduğu görünmeli."""
    micros, status = _table().cost_micros_try(
        "dogrulanmamis", input_tokens=1_000_000, output_tokens=0
    )
    assert micros > 0
    assert status is PricingStatus.UNVERIFIED


def test_bilinmeyen_model_sessizce_bedava_sayilmaz() -> None:
    micros, status = _table().cost_micros_try("hic-duyulmamis", input_tokens=10, output_tokens=10)
    assert status is PricingStatus.UNKNOWN_MODEL
    assert micros == 0  # tutar yok AMA durum bunu söylüyor


def test_kur_yoksa_maliyet_hesaplanmaz_ve_isaretlenir() -> None:
    micros, status = _table(usd_try_rate=None).cost_micros_try(
        "dogrulanmis", input_tokens=1_000_000, output_tokens=0
    )
    assert status is PricingStatus.NO_FX_RATE
    assert micros == 0


def test_gercekten_bedava_model_priced_isaretlenir() -> None:
    """Yerel Ollama gerçekten 0 TL'dir; bu, 'hesaplanamadı' ile karışmamalı."""
    micros, status = _table().cost_micros_try(
        "bedava-yerel", input_tokens=10**6, output_tokens=10**6
    )
    assert micros == 0
    assert status is PricingStatus.PRICED


def test_fiyat_dosyasi_okunamazsa_bos_tablo_doner(tmp_path: Path) -> None:
    """Arıza görünür olmalı: her kayıt `unknown_model` olur, sessizlik olmaz."""
    from tenderiq_core.config import Settings

    reset_pricing_cache()
    settings = Settings(llm_pricing_path=str(tmp_path / "yok.json"), llm_usd_try_rate=40.0)
    table = load_pricing(settings, refresh=True)
    assert table.models == {}
    _, status = table.cost_micros_try("herhangi", input_tokens=1, output_tokens=1)
    assert status is PricingStatus.UNKNOWN_MODEL


def test_depodaki_fiyat_tablosu_gecerli_json_ve_alanlari_tam() -> None:
    """Commit'lenen tablo bozuksa maliyet ölçümü sessizce ölür."""
    path = Path(__file__).resolve().parents[3] / "config" / "llm-pricing.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["models"], "fiyat tablosunda hiç model yok"
    for name, entry in raw["models"].items():
        assert isinstance(entry["input_per_mtok"], int | float), name
        assert isinstance(entry["output_per_mtok"], int | float), name
        assert isinstance(entry["verified"], bool), name


# ── Tracer sarmalaması ──────────────────────────────────────────────────────


class _SpyTracer(LLMTracer):
    """Delege tracer'ın gerçekten çağrıldığını kanıtlayan casus."""

    def __init__(self) -> None:
        self.records: list[tuple[int | None, int | None]] = []
        self.flushed = False

    from contextlib import contextmanager

    @contextmanager  # type: ignore[misc]
    def generation(self, *, name: str, model: str, system: str, prompt: str):  # type: ignore[no-untyped-def]
        spy = self

        class _Span:
            def record(
                self,
                *,
                output: object = None,
                input_tokens: int | None = None,
                output_tokens: int | None = None,
            ) -> None:
                spy.records.append((input_tokens, output_tokens))

        yield _Span()

    def flush(self) -> None:
        self.flushed = True


def _run_one_call(tracer: LLMTracer, *, model: str = "dogrulanmis") -> None:
    with tracer.generation(name="TestSemasi", model=model, system="s", prompt="p") as span:
        span.record(output=None, input_tokens=1_000_000, output_tokens=0)


def test_sarmalama_langfuse_yolunu_bozmaz() -> None:
    """Ölçüm eklendi diye asıl tracing kaybolmamalı."""
    spy = _SpyTracer()
    tracer = CostTracer(spy, pricing=_table())
    with collect_llm_usage():
        _run_one_call(tracer)
    assert spy.records == [(1_000_000, 0)]
    tracer.flush()
    assert spy.flushed is True


def test_olcum_tampona_yazilir_ve_kiraci_baglami_tasinir() -> None:
    token = tenant_id_var.set(str(TENANT))
    try:
        tracer = CostTracer(_SpyTracer(), pricing=_table())
        with collect_llm_usage() as buffer:
            _run_one_call(tracer)
            calls = drain_buffer(buffer)
    finally:
        tenant_id_var.reset(token)

    assert len(calls) == 1
    call = calls[0]
    assert call.tenant_id == TENANT
    assert call.model == "dogrulanmis"
    assert call.operation == "TestSemasi"
    assert call.input_tokens == 1_000_000
    assert call.cost_micros_try == round(3.0 * 40.0 * MICROS_PER_TRY)
    assert call.pricing_status is PricingStatus.PRICED


def test_kiracisiz_kayit_atilir_ve_sayilir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Atfedilemeyen maliyeti rastgele bir kiracıya yazmak, kotayı yanlış kişiden düşerdi."""
    kayiplar: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "tenderiq_core.llm.cost._count_lost",
        lambda amount, *, reason: kayiplar.append((amount, reason)),
    )
    token = tenant_id_var.set(None)
    try:
        tracer = CostTracer(_SpyTracer(), pricing=_table())
        with collect_llm_usage() as buffer:
            _run_one_call(tracer)
            calls = drain_buffer(buffer)
    finally:
        tenant_id_var.reset(token)

    assert calls == []
    assert kayiplar == [(1, "no_tenant")]


def test_tampon_yoksa_kayit_kaybi_sayilir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tamponsuz çağrı sessizce yutulmamalı — 'maliyet düşük' yanılsaması üretir."""
    kayiplar: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "tenderiq_core.llm.cost._count_lost",
        lambda amount, *, reason: kayiplar.append((amount, reason)),
    )
    tracer = CostTracer(_SpyTracer(), pricing=_table())
    _run_one_call(tracer)  # collect_llm_usage YOK
    assert kayiplar == [(1, "no_buffer")]


def test_token_bildirilmeyen_cagri_olculmez() -> None:
    """Sağlayıcı token bildirmediyse uydurma kayıt üretilmez."""
    tracer = CostTracer(_SpyTracer(), pricing=_table())
    with collect_llm_usage() as buffer:
        with tracer.generation(name="X", model="dogrulanmis", system="s", prompt="p") as span:
            span.record(output=None)
        assert buffer.calls == []
