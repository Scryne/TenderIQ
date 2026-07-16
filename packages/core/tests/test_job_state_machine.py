"""Job durum makinesi birim testleri (§5.5)."""

from __future__ import annotations

import pytest

from tenderiq_core.models import (
    JOB_TRANSITIONS,
    TERMINAL_JOB_STATUSES,
    InvalidJobTransitionError,
    Job,
    JobStatus,
)


def _job(status: JobStatus) -> Job:
    return Job(status=status, attempts=0)


def test_mutlu_yol_gecisleri() -> None:
    job = _job(JobStatus.QUEUED)
    for target in (
        JobStatus.PARSING,
        JobStatus.INDEXING,
        JobStatus.EXTRACTING,
        JobStatus.REVIEW_READY,
    ):
        job.transition_to(target)
        assert job.status is target
    assert job.is_terminal


@pytest.mark.parametrize(
    "current",
    [JobStatus.QUEUED, JobStatus.PARSING, JobStatus.INDEXING, JobStatus.EXTRACTING],
)
def test_her_ara_durumdan_failed_gecilebilir(current: JobStatus) -> None:
    job = _job(current)
    job.transition_to(JobStatus.FAILED)
    assert job.is_terminal


def test_failed_yeniden_kuyruklanabilir() -> None:
    job = _job(JobStatus.FAILED)
    job.transition_to(JobStatus.QUEUED)
    assert job.status is JobStatus.QUEUED


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobStatus.QUEUED, JobStatus.INDEXING),  # faz atlama yok
        (JobStatus.PARSING, JobStatus.REVIEW_READY),
        (JobStatus.REVIEW_READY, JobStatus.QUEUED),  # nihai başarıdan dönüş yok
        (JobStatus.REVIEW_READY, JobStatus.FAILED),
        (JobStatus.EXTRACTING, JobStatus.PARSING),  # geri gitmek yok
    ],
)
def test_tanimsiz_gecis_hata_firlatir(current: JobStatus, target: JobStatus) -> None:
    job = _job(current)
    with pytest.raises(InvalidJobTransitionError):
        job.transition_to(target)
    assert job.status is current  # durum değişmedi


def test_gecis_tablosu_tum_durumlari_kapsar() -> None:
    assert set(JOB_TRANSITIONS) == set(JobStatus)
    assert {JobStatus.REVIEW_READY, JobStatus.FAILED} == TERMINAL_JOB_STATUSES
