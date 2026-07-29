"""WebhookDeadLetter — uygulanamayan ödeme olaylarının ölü mektup kuyruğu.

**Neden var.** Webhook, yetkilendirmeyi değiştiren TEK mekanizmadır (ADR-0014).
Doğrulaması geçip **uygulanamayan** bir olay Tur 8'e kadar kayboluyordu: log'a
bir satır düşüyor, olayın kendisi gidiyordu. Bunun bedeli somuttur — müşteri
ödemesini yapmış, planı açılmamış ve elimizde olayı yeniden uygulayacak hiçbir
şey yok. Kuyruk, o olayın gövdesini saklar ki insan bakıp yeniden işleyebilsin.

**Kiracıya ait ama kiracısı OLMAYABİLİR.** Kalıcı hataların en sık türü zaten
"tanınmayan kiracı"dır; bu yüzden ``tenant_id`` hem ``nullable`` hem de
**yabancı anahtarsızdır**. FK koysaydık, saklamak istediğimiz olayın ta kendisi
saklanamazdı. RLS politikası ``tenant_id`` eşleşmesine bakar, dolayısıyla
``NULL`` kiracılı satırlar hiçbir kiracıya görünmez — atfedemediğimiz bir olayı
rastgele birine göstermek, sızıntının ta kendisi olurdu. Bu satırlar operatör
yüzeyinden (log + ``/ops/metrics``) izlenir.

**Gövde redaktedir** (``tenderiq_core.redaction``): sağlayıcı gövdesini olduğu
gibi saklamak, "kart verisi bize gelmez" varsayımı yanlışsa PCI kapsamına
girmek demektir.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import UUIDPKMixin


class DeadLetterKind(StrEnum):
    """Hatanın yeniden denemeyle geçip geçmeyeceği.

    Ayrım, ucun döndüreceği yanıtı belirler: ``TRANSIENT`` sağlayıcının kendi yeniden
    denemesiyle düzelebilir (503 döndürürüz), ``PERMANENT`` asla düzelmez —
    sağlayıcıyı yeniden denemeye çağırmak sadece gürültü üretir (400 döndürürüz).
    """

    #: Yeniden deneme DÜZELTEBİLİR: veritabanı/Redis kesintisi, kilit çakışması.
    TRANSIENT = "transient"
    #: Yeniden deneme ASLA düzeltmez: tanınmayan kiracı, eşlenmemiş durum,
    #: ayrıştırılamayan gövde, geçersiz imza.
    PERMANENT = "permanent"


class DeadLetterStatus(StrEnum):
    """Kuyruk satırının yaşam döngüsü."""

    #: İnsan müdahalesi bekliyor (metriğe sayılan tek durum).
    PENDING = "pending"
    #: Yeniden işlendi ve uygulandı.
    RESOLVED = "resolved"
    #: İncelendi, uygulanmayacak (ör. gerçekten bize ait olmayan olay).
    DISCARDED = "discarded"


class WebhookDeadLetter(UUIDPKMixin, TimestampMixin, Base):
    """Uygulanamamış tek bir ödeme sağlayıcısı olayı."""

    __tablename__ = "webhook_dead_letter"
    __table_args__ = (
        # Aynı olay tekrar tekrar teslim edilir (sağlayıcı retry'ı). Her teslim
        # yeni satır açsaydı kuyruk aynı arızanın kopyalarıyla dolar ve
        # "kaç olay bekliyor" sorusu anlamını yitirirdi; bunun yerine mevcut
        # satırın ``attempts``ı artar.
        UniqueConstraint("provider", "event_id", name="uq_webhook_dead_letter_event"),
    )

    #: Olayın ait olduğu kiracı — atfedilemiyorsa ``NULL`` (bkz. modül docstring'i).
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    #: Sağlayıcının olay kimliği. Yeniden işlemede idempotency anahtarı olarak
    #: BU kullanılır — gövdeden yeniden türetilmez, çünkü gövde redaktedir ve
    #: bazı sağlayıcılarda kimlik redakte edilen bir alandan (``token``) türer.
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)

    #: İmza doğrulamasını geçti mi. Geçmeyen olaylar da saklanır: imza BİÇİMİ
    #: hâlâ doğrulanmamış bir varsayım (bkz. `billing/signature.py`) ve biçim
    #: yanlışsa gerçek olayların hepsi burada birikir — teşhisin tek yolu budur.
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)

    kind: Mapped[DeadLetterKind] = mapped_column(
        SAEnum(DeadLetterKind, native_enum=False, length=20), nullable=False
    )
    status: Mapped[DeadLetterStatus] = mapped_column(
        SAEnum(DeadLetterStatus, native_enum=False, length=20),
        nullable=False,
        default=DeadLetterStatus.PENDING,
    )
    #: Kullanıcıya/operatöre gösterilecek hata sebebi (sağlayıcı gövdesi DEĞİL).
    error: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    #: Redakte edilmiş olay gövdesi. JSON olarak ayrıştırılamadıysa ``NULL``
    #: kalır ve ham metin ``raw_body_text``e kırpılarak yazılır.
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    raw_body_text: Mapped[str | None] = mapped_column(Text)

    last_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
