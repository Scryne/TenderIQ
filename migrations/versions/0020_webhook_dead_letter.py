"""olu mektup kuyrugu: uygulanamayan odeme olaylari

Webhook, yetkilendirmeyi degistiren TEK mekanizmadir (ADR-0014). Dogrulamasi
gecip UYGULANAMAYAN bir olay bu migration'a kadar kayboluyordu: log'a bir satir
dusuyor, olayin kendisi gidiyordu. Bedeli somut: musteri odemesini yapmis, plani
acilmamis ve elimizde olayi yeniden uygulayacak hicbir sey yok.

`tenant_id` NULLABLE ve YABANCI ANAHTARSIZ. Kalici hatalarin en sik turu zaten
"taninmayan kiraci"dir; FK koysaydik saklamak istedigimiz olayin ta kendisi
saklanamazdi. RLS politikasi tenant_id eslesmesine bakar, dolayisiyla NULL
kiracili satirlar HICBIR kiraciya gorunmez — atfedemedigimiz bir olayi rastgele
birine gostermek sizintinin ta kendisi olurdu.

Revision ID: 0020_webhook_dead_letter
Revises: 0019_subscription_lifecycle
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_webhook_dead_letter"
down_revision: str | None = "0019_subscription_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook_dead_letter",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # FK YOK — bilerek (bkz. modul docstring'i).
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("TRANSIENT", "PERMANENT", name="deadletterkind", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RESOLVED",
                "DISCARDED",
                name="deadletterstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_body_text", sa.Text(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_dead_letter")),
        # Ayni olay tekrar tekrar teslim edilir (saglayici retry'i). Her teslim
        # yeni satir acsaydi kuyruk ayni arizanin kopyalariyla dolardi.
        sa.UniqueConstraint("provider", "event_id", name="uq_webhook_dead_letter_event"),
    )
    op.create_index(op.f("ix_webhook_dead_letter_tenant_id"), "webhook_dead_letter", ["tenant_id"])
    # Bekleyen satirlarin taranmasi (liste ucu + metrik) sik; kismi indeks
    # yalnizca onlari kapsar.
    op.create_index(
        "ix_webhook_dead_letter_pending",
        "webhook_dead_letter",
        ["tenant_id", "last_attempt_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    # --- RLS: kiraci izolasyonu (ADR-0003) ---
    #
    # Bu tabloda OKUMA ile YAZMA bilerek farkli kurallara tabidir.
    #
    # SELECT kiraciya kapalidir ve korunmasi gereken sey budur: bir kiracinin
    # yoneticisi baska kiracinin olay govdesini gormemeli. NULL tenant_id ile
    # karsilastirma NULL uretir (yani FALSE): atfedilemeyen satirlar HICBIR
    # kiraciya gorunmez. Operator onlari /ops/metrics ve log uzerinden izler.
    #
    # INSERT/UPDATE kosulsuzdur cunku yazan yol KIMLIKSIZDIR: webhook ucu kiraci
    # baglami kurmadan calisir ve kiracisi BILINMEYEN olaylari da yazabilmelidir
    # — tam olarak o olaylari saklamak icin var bu tablo. Kosullu yapmak, kayit
    # altina alinmasi en kritik olan olayin (atfedilemeyen odeme) sessizce
    # dusmesi demekti. Yazma yuzeyi yalnizca kendi servis kodumuzdur ve bir
    # yazma islemi baska kiracinin verisini disari cikaramaz; sizinti riski
    # okumadadir, o da kapali.
    #
    # DELETE politikasi YOK — kuyruk kaydi silinemez, en fazla "discarded".
    op.execute("ALTER TABLE webhook_dead_letter ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE webhook_dead_letter FORCE ROW LEVEL SECURITY")
    # NULLIF ZORUNLU. `current_setting(..., true)` ayar HIC TANIMLANMAMISSA NULL
    # doner; ama ayni baglantida daha once bir istek onu transaction-local olarak
    # kurduysa, transaction bittikten sonra ayar BOS DIZEYE (`''`) doner — NULL'a
    # degil. Baglanti havuzunda bu kacinilmazdir. `''::uuid` bir hata firlatir
    # (invalid input syntax for type uuid) ve politika "false" uretmek yerine
    # sorguyu ÇÖKERTIR. Bu, kimliksiz webhook yolunun kuyruga hic yazamamasina
    # ve ucun 503 dondurmesine yol aciyordu — testler tespit edemedi, cunku
    # testlerdeki taze baglantilarda ayar hic tanimlanmamis oluyor.
    op.execute(
        "CREATE POLICY webhook_dead_letter_tenant_select ON webhook_dead_letter FOR SELECT "
        "USING (tenant_id = nullif(current_setting('app.current_tenant', true), '')::uuid)"
    )
    # "Servis" politikasi: kiraci baglami KURULMAMIS oturumlar. Webhook ucu
    # kimliksizdir ve kiracisi bilinmeyen olaylari da yazmak/saymak zorundadir;
    # ayrica INSERT ... RETURNING, donen satir icin SELECT izni ister.
    #
    # TAKAS ACIKCA: baglamsiz bir oturum bu tablonun TAMAMINI okuyabilir. Kabul
    # edilebilir, cunku korunmasi gereken ozellik "bir kiracinin yoneticisi
    # baskasinin olayini goremesin"dir ve o ozellik bozulmaz: kiraci yuzeyi her
    # zaman TenantSessionDep ile calisir, yani baglam kuruludur ve yalnizca
    # yukaridaki kiraci politikasi gecerli olur. Riziko, ileride birinin
    # baglamsiz bir oturumdan bu tabloyu okuyup kullaniciya donmesidir — bu,
    # unutulmus bir WHERE'den cok daha gorunur bir hatadir.
    op.execute(
        "CREATE POLICY webhook_dead_letter_service_select ON webhook_dead_letter FOR SELECT "
        "USING (coalesce(current_setting('app.current_tenant', true), '') = '')"
    )
    op.execute(
        "CREATE POLICY webhook_dead_letter_service_insert ON webhook_dead_letter FOR INSERT "
        "WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY webhook_dead_letter_service_update ON webhook_dead_letter FOR UPDATE "
        "USING (true) WITH CHECK (true)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS webhook_dead_letter_service_update ON webhook_dead_letter")
    op.execute("DROP POLICY IF EXISTS webhook_dead_letter_service_select ON webhook_dead_letter")
    op.execute("DROP POLICY IF EXISTS webhook_dead_letter_service_insert ON webhook_dead_letter")
    op.execute("DROP POLICY IF EXISTS webhook_dead_letter_tenant_select ON webhook_dead_letter")
    op.drop_index("ix_webhook_dead_letter_pending", table_name="webhook_dead_letter")
    op.drop_index(op.f("ix_webhook_dead_letter_tenant_id"), table_name="webhook_dead_letter")
    op.drop_table("webhook_dead_letter")
