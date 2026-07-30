"""Derleme-zamanı yapılandırma denetimi — manifesto ↔ dağıtım dosyaları.

## Neden bu dosya var

Tur 11'de `NEXT_PUBLIC_STORAGE_ORIGIN` **hiçbir yerde kurulmuyordu**:
`.env.example`de boş bir satırdı, compose'da yoktu, Dockerfile'da `ARG` yoktu,
CI'da verilmiyordu. Sonuç sessizdi — CSP `connect-src`i aynı-origin'e kilitledi
ve doküman tuvali boş kaldı. Hiçbir test kırılmadı çünkü kod "geçerli"ydi;
eksik olan şey KOD değil, dağıtım yapılandırmasıydı.

Bu denetim o boşluğu kapatır: `apps/web/env-manifest.json` tek kaynaktır ve
oradaki her değişkenin, `wiring` alanında adı geçen HER dosyada gerçekten
bulunduğu doğrulanır. Dördünden biri eksikse test kırılır.

## Neden JSON manifesto, neden Python'dan okunuyor

Manifesto TS'te tanımlansaydı bu testin onu ayrıştırması gerekirdi (kırılgan).
JSON, iki dilin de doğal okuduğu tek biçim: TS tarafı `src/config/env.ts` ile
tipleyerek okur, buradaki denetim aynı dosyayı okur. Tek kaynak, iki tüketici.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "apps" / "web" / "env-manifest.json"

#: `wiring` etiketi → (dosya, o dosyada değişkenin nasıl göründüğünü sınayan kalıp).
#: Kalıplar YAZIM BİÇİMİNE bakar: `.env.example`de `AD=`, compose'da
#: `AD: ${...}`, Dockerfile'da `ARG AD`. "Dosyada adı geçiyor" yeterli değil —
#: yorum satırında geçmesi kurulmuş olduğu anlamına gelmez.
WIRING_TARGETS: dict[str, tuple[str, str]] = {
    "env-example": (".env.example", r"^{name}="),
    "compose-build-arg": ("infra/compose/docker-compose.yml", r"^\s+{name}:\s*\S"),
    "dockerfile-arg": ("infra/docker/web.Dockerfile", r"^ARG\s+{name}\b"),
    "ci-e2e": (".github/workflows/ci.yml", r"^\s+{name}:\s*\S"),
    "ci-a11y": (".github/workflows/ci.yml", r"^\s+{name}:\s*\S"),
    "ci-frontend": (".github/workflows/ci.yml", r"^\s+{name}:\s*\S"),
    # İmaj taraması `docker build` çağırıyor; değişken orada `--build-arg` ile
    # geçer. Tur 12'de CI tam bu iki hedefte düştü: manifesto onları
    # listelemediği için denetim "her şey yolunda" demişti — denetim ancak
    # manifestonun İDDİA ETTİĞİ kadar kapsayıcıdır.
    "ci-image-scan": (".github/workflows/ci.yml", r"--build-arg\s+{name}="),
}


def _manifest() -> list[dict[str, object]]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    variables = data["variables"]
    assert isinstance(variables, list), "manifesto `variables` listesi değil"
    assert variables, "manifesto boş"
    return variables


def _yorumsuz(kaynak: str) -> str:
    """TS kaynağından yorumları ayıklar.

    Gerekli: bu dosyaların yorumlarında `process.env.X` ÖRNEK olarak geçiyor
    (ör. `config/env.ts`, Next'in yalnız statik erişimi gömdüğünü anlatırken).
    Yorumları saymak, var olmayan bir değişkeni "manifestoda eksik" diye
    raporlardı — testin ilk sürümü tam olarak bunu yaptı.

    Dize içindeki `//` dizilerini yanlışlıkla yorum sayabilir; bu denetim için
    kabul edilebilir, çünkü sonuç yalnız FAZLADAN ayıklama olur ve gerçek bir
    `process.env.X` okuması dize içinde yazılmaz.
    """
    kaynak = re.sub(r"/\*.*?\*/", "", kaynak, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", kaynak)


def _file_lines(relative: str) -> list[str]:
    path = REPO_ROOT / relative
    assert path.is_file(), f"dağıtım dosyası bulunamadı: {relative}"
    return path.read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("variable", _manifest(), ids=lambda v: str(v["name"]))
def test_manifestodaki_degisken_dagitim_dosyalarinda_kurulu(variable: dict[str, object]) -> None:
    """`wiring` listesindeki her hedefte değişken GERÇEKTEN tanımlı olmalı."""
    name = str(variable["name"])
    eksik: list[str] = []

    for target in variable["wiring"]:  # type: ignore[union-attr]
        relative, pattern = WIRING_TARGETS[str(target)]
        regex = re.compile(pattern.format(name=re.escape(name)))
        if not any(regex.search(line) for line in _file_lines(relative)):
            eksik.append(f"{target} ({relative})")

    assert not eksik, (
        f"`{name}` manifestoda `{eksik}` hedeflerinde kurulu görünmüyor.\n"
        f"Eksikse ne olur: {variable['failure']}\n"
        "Ya değişkeni o dosyalara ekle ya da manifestodaki `wiring` listesini düzelt."
    )


def test_manifesto_alanlari_eksiksiz() -> None:
    """Her girdi, arızasını TARİF EDEN alanları taşımalı.

    `failure` boş bırakılabilseydi manifesto bir değişken listesine dönerdi;
    değerli olan kısım "eksikse ne kırılır" bilgisi — Tur 11'de eksik olan da
    tam olarak o bilgiydi (kimse `NEXT_PUBLIC_STORAGE_ORIGIN`in ne yaptığını
    yazmamıştı).
    """
    zorunlu_alanlar = {
        "name",
        "buildTime",
        "layers",
        "required",
        "default",
        "wiring",
        "description",
        "failure",
    }
    for variable in _manifest():
        eksik = zorunlu_alanlar - set(variable)
        assert not eksik, f"{variable.get('name')}: eksik alan {sorted(eksik)}"
        assert str(variable["description"]).strip(), f"{variable['name']}: açıklama boş"
        assert str(variable["failure"]).strip(), f"{variable['name']}: `failure` boş"
        assert variable["layers"], f"{variable['name']}: katman listesi boş"
        assert variable["required"] in ("always", "production", False), (
            f"{variable['name']}: `required` beklenmeyen değer {variable['required']!r}"
        )


#: Backend değişkenleri manifestoda değil (`pydantic-settings` çalışma anında
#: okur, derleme anında gömülmez) — ama kurulmaları yine de zorunlu. J.6 maliyet
#: ölçümü tavanın girdisidir: `.env.example`de yoksa operatör varlığından
#: haberdar olmaz ve tavan sessizce ölçümsüz kalır.
J6_BACKEND_VARIABLES = ("LLM_PRICING_PATH", "LLM_USD_TRY_RATE")


@pytest.mark.parametrize("name", J6_BACKEND_VARIABLES)
def test_j6_degiskenleri_env_example_ve_dokumanda(name: str) -> None:
    """J.6 değişkenleri `.env.example`de ve yapılandırma belgesinde olmalı."""
    env_lines = _file_lines(".env.example")
    assert any(re.match(rf"^{re.escape(name)}=", line) for line in env_lines), (
        f"`{name}` .env.example'de yok — operatör varlığını bilemez."
    )
    doc = (REPO_ROOT / "docs" / "ops" / "yapilandirma.md").read_text(encoding="utf-8")
    assert name in doc, f"`{name}` docs/ops/yapilandirma.md'de belgelenmemiş."


def test_fiyat_tablosu_varsayilan_yolda_mevcut() -> None:
    """`LLM_PRICING_PATH` varsayılanı gerçekten var olan bir dosyayı göstermeli.

    Dosya yoksa her kayıt `unknown_model` olur; sistem çalışır ama HİÇBİR
    maliyet hesaplanmaz — tavanın sessizce devre dışı kaldığı hâl budur.
    """
    from tenderiq_core.config import Settings

    varsayilan = Settings.model_fields["llm_pricing_path"].default
    assert (REPO_ROOT / str(varsayilan)).is_file(), f"fiyat tablosu bulunamadı: {varsayilan}"


def test_webde_okunan_her_degisken_manifestoda() -> None:
    """Kodda okunan bir değişken manifestoya YAZILMADAN kalmasın.

    Denetimin asıl açığı buydu: manifesto elle tutulan bir liste olsaydı, yeni
    bir `process.env.X` okuması eklendiğinde kimse listeyi güncellemez ve
    denetim "her şey yolunda" derdi. Bu test kaynağı tarar ve manifestoyu
    kodun gerisinde kalmaya bırakmaz.
    """
    web_src = REPO_ROOT / "apps" / "web" / "src"
    okunanlar: set[str] = set()
    for path in web_src.rglob("*.ts*"):
        kaynak = _yorumsuz(path.read_text(encoding="utf-8"))
        for match in re.finditer(r"process\.env\.([A-Z][A-Z0-9_]*)", kaynak):
            okunanlar.add(match.group(1))

    # `NODE_ENV` Next'in kendi değişkenidir; dağıtımda kurulmaz.
    okunanlar.discard("NODE_ENV")
    manifestodakiler = {str(v["name"]) for v in _manifest()}

    eksik = sorted(okunanlar - manifestodakiler)
    assert not eksik, (
        f"Kodda okunan ama manifestoda olmayan değişken(ler): {eksik}. "
        "`apps/web/env-manifest.json`a ekle (arızasını da yazarak)."
    )
