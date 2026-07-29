"""/_test/inbox — E2E'nin doğrulama bağlantısını okuduğu gelen kutusu.

**Neden bir uç var.** Tarayıcı E2E'si gerçek bir kayıt akışını sınıyor: kaydol →
doğrulama e-postasındaki bağlantıya git → giriş yap. Bu zincirin ortasındaki
bağlantı e-postanın İÇİNDEDİR. Testin onu okuyabilmesi için ya gerçek bir posta
kutusuna çıkmak (dış servis — yasak) ya da sunucunun gönderdiğini yerelden
okuyabilmek gerekir. İkincisi seçildi.

**Nasıl kapalı tutuluyor.** Uç yalnızca ``EMAIL_PROVIDER=memory`` iken ve
production DIŞINDA yanıt verir; aksi hâlde **404** — kapalı bir kurulumda ucun
varlığı bile sızmaz (``/ops/metrics`` ile aynı kalıp). Üstüne, ``memory``
sağlayıcısı production'da açılışta zaten reddedilir (``config``), yani bu ucun
production'da açık kalması için iki ayrı kapının birden aşılması gerekir.

``include_in_schema=False``: müşteri sözleşmesine ve üretilen istemciye girmez.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from tenderiq_api.errors import NotFoundError
from tenderiq_core.config import Environment, get_settings
from tenderiq_core.email.provider import MemoryEmailProvider

router = APIRouter(prefix="/_test", tags=["test"], include_in_schema=False)


class InboxMessage(BaseModel):
    """Gönderilmiş tek bir e-posta (düz metin gövdesiyle)."""

    kind: str
    to: str
    subject: str
    text: str


def _inbox(request: Request) -> MemoryEmailProvider:
    """Bellek sağlayıcısını döndürür; koşullar sağlanmıyorsa ucu yok sayar."""
    settings = get_settings()
    if settings.environment is Environment.PRODUCTION or settings.email_provider != "memory":
        raise NotFoundError("Bulunamadı.")
    provider = getattr(request.app.state, "email_provider", None)
    if not isinstance(provider, MemoryEmailProvider):
        raise NotFoundError("Bulunamadı.")
    return provider


@router.get("/inbox", response_model=list[InboxMessage])
def list_inbox(
    request: Request,
    to: Annotated[str | None, Query(description="Alıcıya göre süz")] = None,
    kind: Annotated[str | None, Query(description="Mesaj türüne göre süz")] = None,
) -> list[InboxMessage]:
    """Gönderilmiş e-postaları döndürür (en yeni sonda).

    Süzgeçler testin *kendi* mesajını bulmasını sağlar: aynı sunucuda paralel
    koşan başka bir senaryo da posta göndermiş olabilir ve "son mesajı al"
    varsayımı sessizce yanlış mesajı seçerdi.
    """
    provider = _inbox(request)
    messages = [
        InboxMessage(kind=m.kind.value, to=m.to, subject=m.subject, text=m.text)
        for m in provider.sent
        if (to is None or m.to.lower() == to.lower()) and (kind is None or m.kind.value == kind)
    ]
    return messages


@router.delete("/inbox", status_code=204)
def clear_inbox(request: Request) -> None:
    """Gelen kutusunu boşaltır — senaryolar arası yalıtım için."""
    _inbox(request).sent.clear()
