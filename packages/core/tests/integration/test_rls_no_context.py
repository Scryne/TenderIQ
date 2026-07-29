"""Kiracı bağlamı YOKKEN RLS: çökmemeli, satır döndürmemeli — sınıfın tamamı.

**Bu dosya bir hata sınıfını kapatır, tek bir hatayı değil.**

Tur 8'de şu keşfedildi: politikalar `current_setting('app.current_tenant', true)::uuid`
yazıyordu. Ayar hiç tanımlanmamışsa `NULL` döner ve politika doğru çalışır; ama
aynı bağlantıda daha önce bir istek onu **transaction-local** kurduysa, transaction
bittikten sonra ayar **boş dizeye** döner. `''::uuid` hata fırlatır — yani politika
satır süzmek yerine sorguyu ÇÖKERTİR.

Mevcut izolasyon testi (`test_rls_isolation.py`) bunu göremezdi ve göremez:
``NullPool`` kullanıyor, yani her oturum **taze bağlantı** alıyor ve ayar hiç
tanımlanmamış oluyor. Üretimde ise bağlantı havuzludur. Bu dosyanın tek işi o
farkı üretmek: **aynı bağlantıyı yeniden kullanmak.**

Üç kapı:

1. ``test_baglam_birakilmis_baglantida_hicbir_tablo_cokmez`` — davranış kapısı.
   Tablo listesi ``pg_policies``ten TÜRETİLİR; yeni bir RLS tablosu eklendiğinde
   kimse listeyi güncellemese de otomatik kapsanır.
2. ``test_hicbir_politika_ham_current_setting_kullanmaz`` — yapısal kapı. Kalıptan
   sapan yeni bir politika, davranış testini kırmasa bile burada yakalanır.
3. ``test_app_current_tenant_bos_dizeyi_null_yapar`` — yardımcının sözleşmesi.

**"Hata verdi, demek ki güvenli" kabul edilmez.** Çökme bir izolasyon garantisi
değildir: kimin ne göreceğini belirlemez, yalnız isteği düşürür. Test bu yüzden
satır sayısının **sıfır** olduğunu da doğrular.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import QueuePool

pytestmark = pytest.mark.integration

#: Bağlam bırakıldıktan sonra sorgulanacak tabloları veren sorgu. RLS açık olan
#: HER tablo kapsanır; liste elle tutulmaz.
_RLS_TABLES_SQL = text(
    """
    SELECT DISTINCT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relrowsecurity AND n.nspname = 'public'
    ORDER BY 1
    """
)

_POLICY_EXPR_SQL = text(
    """
    SELECT tablename, policyname,
           coalesce(qual, '') || ' ' || coalesce(with_check, '') AS expr
    FROM pg_policies
    WHERE schemaname = 'public'
    """
)


def _pooled_engine(url: str):
    """Bağlantıyı GERÇEKTEN yeniden kullanan motor.

    ``QueuePool`` + ``pool_size=1`` + ``max_overflow=0``: art arda açılan iki
    bağlantı aynı fiziksel bağlantıdır. Hatanın ortaya çıkması için şart olan
    tek şey bu — ``NullPool`` ile bu sınıf hata görünmez.
    """
    return create_engine(url, poolclass=QueuePool, pool_size=1, max_overflow=0)


def test_baglam_birakilmis_baglantida_hicbir_tablo_cokmez(app_database_url: str) -> None:
    """Bağlam kurulup bırakıldıktan sonra her RLS tablosu 0 satır döndürmeli."""
    engine = _pooled_engine(app_database_url)
    try:
        with engine.connect() as connection:
            # Her okuma açık bir transaction içinde: SQLAlchemy 2.0 ilk
            # `execute`ta kendiliğinden transaction başlatır ve sonraki
            # `begin()` çağrısı hata verir.
            with connection.begin():
                tables = list(connection.execute(_RLS_TABLES_SQL).scalars().all())
            assert tables, "RLS açık tablo bulunamadı — sorgu ya da şema bozuk."

            # 1) Kiracı bağlamını transaction-local kur ve transaction'ı bitir.
            #    Ayar bu noktadan sonra NULL değil, BOŞ DİZEdir.
            with connection.begin():
                connection.execute(
                    text("SELECT set_config('app.current_tenant', :t, true)"),
                    {"t": str(uuid.uuid4())},
                )

            with connection.begin():
                leftover = connection.execute(
                    text("SELECT current_setting('app.current_tenant', true)")
                ).scalar()
            # Tuzağın ön koşulu: testin gerçekten doğru durumu ürettiğini kanıtla.
            # Bu satır olmadan test "yeşil ama boş" olabilir.
            assert leftover == "", f"beklenen boş dize, gelen: {leftover!r}"

            # 2) Aynı bağlantıda her RLS tablosunu sorgula.
            crashed: list[tuple[str, str]] = []
            leaked: list[tuple[str, int]] = []
            for table in tables:
                with connection.begin():
                    try:
                        count = connection.execute(
                            text(f'SELECT count(*) FROM "{table}"')  # noqa: S608 - katalogdan
                        ).scalar_one()
                    except DBAPIError as exc:
                        crashed.append((table, type(exc.orig).__name__))
                        continue
                if count:
                    leaked.append((table, int(count)))

            assert not crashed, (
                "Kiracı bağlamı bırakılmış bağlantıda RLS politikası ÇÖKTÜ "
                f"(satır süzmek yerine sorguyu düşürdü): {crashed}"
            )
            # Çökmemek yetmez: fail-closed davranış satır DÖNDÜRMEMEKtir.
            assert not leaked, f"Bağlam yokken satır döndü (izolasyon ihlali): {leaked}"
    finally:
        engine.dispose()


def test_hicbir_politika_ham_current_setting_kullanmaz(app_database_url: str) -> None:
    """Yapısal kapı: kiracı ifadesi tek fonksiyondan (``app_current_tenant()``) gelir.

    Ham ``current_setting(...)::uuid`` yazan yeni bir politika, bağlam yokken
    sorguyu çökertir. Davranış testi onu ancak tablo RLS açıksa yakalar; bu test
    kalıptan sapmanın kendisini yakalar ve gerekçesini tek yerde tutar.
    """
    engine = create_engine(app_database_url)
    try:
        with engine.connect() as connection, connection.begin():
            rows = connection.execute(_POLICY_EXPR_SQL).all()
    finally:
        engine.dispose()

    assert rows, "Hiç politika bulunamadı — şema beklenenden farklı."
    offenders = [
        (table, policy)
        for table, policy, expr in rows
        if "current_setting" in expr and "app_current_tenant" not in expr
    ]
    assert not offenders, (
        "Politika ham `current_setting` kullanıyor; `app_current_tenant()` çağırmalı "
        f"(bkz. migration 0021): {offenders}"
    )


@pytest.mark.parametrize(
    ("setting", "beklenen_null"),
    [
        (None, True),  # ayar hiç tanımlanmamış
        ("", True),  # transaction bitti, ayar boş dizeye döndü ← ASIL TUZAK
        ("11111111-1111-1111-1111-111111111111", False),
    ],
)
def test_app_current_tenant_bos_dizeyi_null_yapar(
    app_database_url: str, setting: str | None, beklenen_null: bool
) -> None:
    """Yardımcının sözleşmesi: ayar yok ya da boşsa NULL — hata değil."""
    engine = create_engine(app_database_url)
    try:
        with engine.connect() as connection, connection.begin():
            if setting is not None:
                connection.execute(
                    text("SELECT set_config('app.current_tenant', :t, true)"), {"t": setting}
                )
            value = connection.execute(text("SELECT app_current_tenant()")).scalar()
    finally:
        engine.dispose()

    assert (value is None) is beklenen_null, f"setting={setting!r} → {value!r}"
