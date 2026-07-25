"""Yumuşak silinmiş satırların TÜM okuma yollarından otomatik düşürülmesi.

Neden olay tabanlı, neden her sorguya elle ``where`` değil:
``Tender`` ve ``Document`` uygulama genelinde 25'ten fazla yerde sorgulanıyor
(API router'ları, worker'ın parse/index/extract fazları, export, panel). Bunların
her birine elle filtre koymak, TEK bir unutmanın silinmiş veriyi kullanıcıya geri
göstermesi demektir — KVKK bağlamında bu bir hata değil, ihlaldir. Bu yüzden
varsayılan **güvenli** tarafta olmalı: filtre otomatik uygulanır, görmek isteyen
açıkça talep eder.

Kullanım:
    # normal — silinmiş satırlar görünmez
    session.execute(select(Tender))

    # kalıcı silme işi / yönetimsel yol — silinmişler DE gelsin
    session.execute(select(Tender).execution_options(include_deleted=True))

SQLAlchemy'nin ``do_orm_execute`` olayı + ``with_loader_criteria`` deseni
kullanılır; kriter join'lenen ve alias'lanan tüm örneklere de uygulanır
(``include_aliases=True``), yani ``select(Document).join(Tender)`` gibi bir sorgu
silinmiş ihalenin dokümanını da getirmez.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from tenderiq_core.db.mixins import SoftDeleteMixin

__all__ = ["INCLUDE_DELETED", "register_soft_delete_filter"]

#: ``execution_options`` anahtarı: ``True`` verilirse filtre uygulanmaz.
INCLUDE_DELETED = "include_deleted"


def _apply(state: ORMExecuteState) -> None:
    """Okuma sorgularına ``deleted_at IS NULL`` kriterini ekler."""
    # Yalnız SELECT'ler. UPDATE/DELETE ifadeleri (ör. yumuşak silmenin kendisi ve
    # kalıcı silme) dokunulmadan geçer; aksi hâlde silinmiş bir satır artık
    # güncellenemez ve "geri al" imkânsız olurdu.
    if not state.is_select:
        return
    # Lazy/selectin yükleme gibi ilişki yüklemelerinde üst sorgunun kriteri zaten
    # uygulanmıştır; tekrar eklemek gereksiz ama zararsızdır. Asıl atlanması
    # gereken, açık opt-out'tur.
    if state.execution_options.get(INCLUDE_DELETED, False):
        return

    state.statement = state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.deleted_at.is_(None),
            include_aliases=True,
        )
    )


def register_soft_delete_filter(target: Any = Session) -> None:
    """Bir ``Session`` sınıfına/örneğine yumuşak silme filtresini bağlar.

    Varsayılan hedef ``Session`` sınıfıdır; bu, hem senkron (worker) hem de
    ``AsyncSession``'ın altında yatan senkron oturumu kapsar — yani tek kayıt
    tüm uygulamayı korur.
    """
    if not event.contains(target, "do_orm_execute", _apply):
        event.listen(target, "do_orm_execute", _apply)
