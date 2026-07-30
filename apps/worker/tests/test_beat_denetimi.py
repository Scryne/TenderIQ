"""Zamanlanmış görev denetimi — tanımlı ama zamanlayıcıya bağlanmamış task.

## Neden bu dosya var

Tur 10'da bulunan kusur sınıfının worker karşılığı: **artefakt var, kayıt yok.**
Bir bakım task'ı yazılıp `beat_schedule`a eklenmezse hiçbir test kırılmaz —
task'ın kendi birim testi geçmeye devam eder, çünkü test onu doğrudan çağırır.
Üretimde ise hiç koşmaz. Bu, en pahalı sessiz arıza türlerinden biri:

- `reconcile_subscriptions` koşmazsa "ödeme alındı, erişim açılmadı" hâli
  KALICI olur (kayıp webhook'un tek yedeği odur).
- `apply_due_subscription_changes` koşmazsa iptal etmiş kiracı ücretsiz plana
  hiç düşmez — yani `/sartlar` §3'te verilen söz tutulmaz.
- `purge_deleted` koşmazsa KVKK saklama süresi dolan veri silinmez.

Denetim iki yönlü çalışır; tek yön yeterli değil:

1. **İleri:** periyodik olması gereken her task adı `beat_schedule`da olmalı.
2. **Geri:** `beat_schedule`daki her giriş GERÇEKTEN var olan bir task'a
   işaret etmeli. Ada göre yayın yapıldığı için bir harf hatası sessizce
   "hiç koşmayan zamanlanmış görev" üretir — beat her seferinde bilinmeyen
   task'ı yayınlar, hiçbir worker onu tanımaz.
"""

from __future__ import annotations

from tenderiq_core import queueing
from tenderiq_worker.celery_app import celery_app

#: Bilinçli olarak ZAMANLANMAYAN task'lar (ad → gerekçe). Olay güdümlüdür:
#: bir istek ya da elle çağrı tetikler.
OLAY_GUDUMLU: dict[str, str] = {
    queueing.TASK_PROCESS_DOCUMENT: (
        "Doküman yükleme tamamlandığında API `send_task` ile yayınlar; "
        "zamanlanmış koşumu anlamsız olurdu (işlenecek doküman yoksa boş tarama)."
    ),
    "system.ping": "Sağlık/duman kontrolü; elle çağrılır.",
}


def _tanimli_task_adlari() -> set[str]:
    """`queueing` sözleşmesindeki tüm task adları (tek kaynak)."""
    return {
        value
        for name, value in vars(queueing).items()
        if name.startswith("TASK_") and isinstance(value, str)
    }


def _beat_task_adlari() -> set[str]:
    return {entry["task"] for entry in celery_app.conf.beat_schedule.values()}


def test_periyodik_olmasi_gereken_her_task_zamanlanmis() -> None:
    """`queueing`de tanımlı her task ya zamanlanmış ya OLAY_GUDUMLU olmalı.

    Yeni bir bakım task'ı eklendiğinde bu test onu ZORLA bir karara sokar:
    ya `beat_schedule`a eklenir ya da gerekçesiyle olay güdümlü ilan edilir.
    Sessizce hiç koşmayan bir üçüncü hâl bırakmıyor.
    """
    zamanlanmis = _beat_task_adlari()
    baglanmamis = sorted(_tanimli_task_adlari() - zamanlanmis - set(OLAY_GUDUMLU))

    assert not baglanmamis, (
        "Task tanımlı ama hiçbir zamanlayıcıya kayıtlı değil — üretimde HİÇ "
        "koşmaz. Olay güdümlüyse OLAY_GUDUMLU'ya gerekçesiyle ekle:\n  " + "\n  ".join(baglanmamis)
    )


def test_beat_girisleri_var_olan_taska_isaret_ediyor() -> None:
    """Ters yön: `beat_schedule`daki her ad gerçekten kayıtlı bir task olmalı.

    Celery ADA göre yayınlar. Şemadaki bir harf hatası hata vermez; beat her
    periyotta bilinmeyen bir task yayınlar, worker onu tanımaz ve iş sessizce
    hiç yapılmaz.
    """
    # Task'lar `include` listesindeki modüller import edilince kaydolur.
    celery_app.loader.import_default_modules()
    kayitli = set(celery_app.tasks)

    hayalet = sorted(_beat_task_adlari() - kayitli)
    assert not hayalet, (
        "beat_schedule var olmayan task'a işaret ediyor (yayınlanır, hiçbir "
        f"worker tanımaz): {hayalet}"
    )


def test_olay_gudumlu_istisnalari_gerekcesiz_olamaz() -> None:
    gerekcesiz = [name for name, reason in OLAY_GUDUMLU.items() if not reason.strip()]
    assert not gerekcesiz, f"gerekçesiz istisna: {gerekcesiz}"


def test_zamanlanmis_gorev_araliklari_makul() -> None:
    """Periyot değerleri gözden kaçan birim hatalarına karşı sınırlanır.

    `schedule` saniye cinsindendir. 3600 yerine 3600*24*365 yazmak ya da 1
    yazmak testte görünmezdi: ilki görevi pratikte durdurur, ikincisi
    veritabanını boş taramayla döver.
    """
    for name, entry in celery_app.conf.beat_schedule.items():
        schedule = entry["schedule"]
        assert isinstance(schedule, int | float), f"{name}: beklenmeyen tip {type(schedule)}"
        assert 60 <= schedule <= 7 * 24 * 3600, (
            f"{name}: periyot {schedule} sn — 1 dakika ile 1 hafta arasında olmalı "
            "(birim saniye; gün/saat ile karıştırılmış olabilir)."
        )
