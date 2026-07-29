"""RLS kiraci ifadesi tek fonksiyona indirildi (bos-dize tuzagi)

## Sorun

Tum RLS politikalari `tenant_id = current_setting('app.current_tenant', true)::uuid`
yaziyordu. `current_setting(..., true)` ayar HIC TANIMLANMAMISSA `NULL` doner —
politika "false" uretir, satir donmez, fail-closed calisir. Ama ayni baglantida
daha once bir istek ayari transaction-local kurduysa (`set_config(..., true)`),
transaction bittikten sonra ayar **bos dizeye** (`''`) doner, NULL'a DEGIL.
Baglanti havuzunda bu kacinilmazdir.

`''::uuid` bir hata firlatir (`invalid input syntax for type uuid`). Yani
politika satir filtrelemek yerine **sorguyu comple cokertir**. Tur 8'de bu,
kimliksiz webhook yolunun olu mektup kuyruguna hic yazamamasina ve ucun 503
dondurmesine yol acti; ayni tuzak `tender`, `document`, `job` dahil 17 tabloda
daha duruyordu.

Uretilebilir kanit (ayni baglanti):
    BEGIN; SELECT set_config('app.current_tenant', '<uuid>', true); COMMIT;
    SELECT count(*) FROM tender;   -- ERROR: invalid input syntax for type uuid: ""

## Cozum

Ifade tek bir fonksiyona indirildi: `app_current_tenant()`. Politikalar artik
onu cagiriyor, dolayisiyla kalip **tekrar sapamaz** — 33 ayri yerde dogru
yazilmasi gereken bir ifade yerine tek tanim var.

Fonksiyon `STABLE` + `PARALLEL SAFE` ve govdesinde SET yan tumcesi YOK: bu
sayede planlayici onu satir ici acabiliyor (inline). `SET search_path` eklemek
guvenlik acisindan cazipti ama inline'i engelliyor ve RLS ifadesi SATIR BASINA
degerlendigi icin bu gercek bir maliyet olurdu; yerine `current_setting`
dogrudan `pg_catalog` ile nitelendi.

Revision ID: 0021_rls_null_safe_tenant
Revises: 0020_webhook_dead_letter
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0021_rls_null_safe_tenant"
down_revision: str | None = "0020_webhook_dead_letter"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: `<tablo>_tenant_isolation` adinda tek bir ALL politikasi tasiyan tablolar.
#: Hepsinde kural ayni: satir yalnizca aktif kiracininsa gorunur/yazilabilir.
_ISOLATED_TABLES: tuple[str, ...] = (
    "capability_profile",
    "chunk",
    "compliance_result",
    "deliverable",
    "document",
    "embedding",
    "finding_comment",
    "job",
    "parsed_element",
    "requirement",
    "risk_flag",
    "subscription",
    "tender",
    "timeline_event",
    "usage_record",
)

_OLD_EXPR = "current_setting('app.current_tenant', true)::uuid"
_NEW_EXPR = "app_current_tenant()"


def _recreate_isolation_policies(expr: str) -> None:
    """Tum `*_tenant_isolation` politikalarini verilen ifadeyle yeniden kurar."""
    for table in _ISOLATED_TABLES:
        policy = f"{table}_tenant_isolation"
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(
            f"CREATE POLICY {policy} ON {table} "
            f"USING (tenant_id = {expr}) WITH CHECK (tenant_id = {expr})"
        )


def _recreate_audit_log_policies(expr: str) -> None:
    """audit_log append-only'dir: yalniz SELECT + INSERT politikasi vardir.

    UPDATE/DELETE politikasi TANIMLI DEGIL; uygulama rolu denetim kaydini
    degistiremez/silemez. Bu migration o ozelligi korur.
    """
    op.execute("DROP POLICY IF EXISTS audit_log_tenant_select ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_tenant_insert ON audit_log")
    op.execute(
        f"CREATE POLICY audit_log_tenant_select ON audit_log FOR SELECT USING (tenant_id = {expr})"
    )
    op.execute(
        f"CREATE POLICY audit_log_tenant_insert ON audit_log FOR INSERT "
        f"WITH CHECK (tenant_id = {expr})"
    )


def upgrade() -> None:
    # Tek tanim noktasi. `nullif(..., '')` bos dizeyi NULL'a cevirir; NULL ile
    # karsilastirma NULL uretir, yani politika FALSE sayar ve satir dondurmez —
    # cokme yerine fail-closed davranis.
    op.execute(
        "CREATE OR REPLACE FUNCTION app_current_tenant() RETURNS uuid "
        "LANGUAGE sql STABLE PARALLEL SAFE AS "
        "$$ SELECT nullif(pg_catalog.current_setting('app.current_tenant', true), '')::uuid $$"
    )
    op.execute(
        "COMMENT ON FUNCTION app_current_tenant() IS "
        "'Aktif RLS kiracisi; ayar yoksa ya da bos dizeyse NULL (fail-closed). "
        "RLS politikalari bu fonksiyonu cagirir — ifade kopyalanmaz.'"
    )

    _recreate_isolation_policies(_NEW_EXPR)
    _recreate_audit_log_policies(_NEW_EXPR)

    # 0020'de zaten nullif'liydi; fonksiyona gecirmek kalibi tekillestirir.
    op.execute("DROP POLICY IF EXISTS webhook_dead_letter_tenant_select ON webhook_dead_letter")
    op.execute(
        f"CREATE POLICY webhook_dead_letter_tenant_select ON webhook_dead_letter FOR SELECT "
        f"USING (tenant_id = {_NEW_EXPR})"
    )
    # "Servis" politikasi da ayni fonksiyonu kullansin. `COALESCE(...) = ''`
    # cokemezdi (metin karsilastirmasi), ama boylece HICBIR politikada ham
    # `current_setting` kalmiyor ve bu, testle zorlanabilir bir degismez olur:
    # kaliptan sapan yeni bir politika CI'da yakalanir.
    op.execute("DROP POLICY IF EXISTS webhook_dead_letter_service_select ON webhook_dead_letter")
    op.execute(
        f"CREATE POLICY webhook_dead_letter_service_select ON webhook_dead_letter FOR SELECT "
        f"USING ({_NEW_EXPR} IS NULL)"
    )


def downgrade() -> None:
    _recreate_isolation_policies(_OLD_EXPR)
    _recreate_audit_log_policies(_OLD_EXPR)
    op.execute("DROP POLICY IF EXISTS webhook_dead_letter_tenant_select ON webhook_dead_letter")
    op.execute(
        "CREATE POLICY webhook_dead_letter_tenant_select ON webhook_dead_letter FOR SELECT "
        "USING (tenant_id = nullif(current_setting('app.current_tenant', true), '')::uuid)"
    )
    op.execute("DROP POLICY IF EXISTS webhook_dead_letter_service_select ON webhook_dead_letter")
    op.execute(
        "CREATE POLICY webhook_dead_letter_service_select ON webhook_dead_letter FOR SELECT "
        "USING (coalesce(current_setting('app.current_tenant', true), '') = '')"
    )
    op.execute("DROP FUNCTION IF EXISTS app_current_tenant()")
